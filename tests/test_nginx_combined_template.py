"""Offline validation of deployment/nginx-combined.conf.template (the PROD front door).

The template is rendered by deployment/docker-entrypoint.sh at container start.
These tests render it the same way and run `nginx -t` in an ephemeral nginx
container, so a template that cannot load never reaches a deploy. They skip
silently without Docker, like test_local_nginx_config.py.

They also pin the one invariant the template's header explains at length: every
bond-mcps upstream reaches proxy_pass through a VARIABLE, never a literal.
nginx resolves a literal proxy_pass hostname once at load and keeps the
addresses for the worker's life; the *.mcps.* ALB addresses move, and on
2026-09-09 every proxied path hung against addresses cached nine days earlier.
A variable makes nginx resolve per request through `resolver`, which is why a
future edit that reintroduces `proxy_pass https://...mcps...;` must fail here.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "deployment" / "nginx-combined.conf.template"
ENTRYPOINT = REPO_ROOT / "deployment" / "docker-entrypoint.sh"
# Debian-based (bash + envsubst), the same family Dockerfile.combined installs
# nginx from; the alpine image the local-conf test uses has no bash for the
# entrypoint.
NGINX_IMAGE = "nginx:1.26.3"

PROVIDERS = ("AUTH", "MICROSOFT", "ATLASSIAN", "GITHUB", "DATABRICKS")
# The locations the front door proxies to bond-mcps: discovery, three provider
# callbacks, and the /connect/<p>/ prefix + exact pair for four providers.
PROXIED_LOCATIONS = (
    ("= /connections/discovery", "mcps_auth"),
    ("= /connections/microsoft/callback", "mcps_microsoft"),
    ("= /connections/github/callback", "mcps_github"),
    ("= /connections/atlassian/callback", "mcps_atlassian"),
    ("/connect/microsoft/", "mcps_microsoft"),
    ("= /connect/microsoft", "mcps_microsoft"),
    ("/connect/github/", "mcps_github"),
    ("= /connect/github", "mcps_github"),
    ("/connect/atlassian/", "mcps_atlassian"),
    ("= /connect/atlassian", "mcps_atlassian"),
    ("/connect/databricks/", "mcps_databricks"),
    ("= /connect/databricks", "mcps_databricks"),
)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode == 0


def _template() -> str:
    return TEMPLATE.read_text()


def _location_blocks(text: str) -> dict[str, str]:
    """Map each `location <match>` to its body (the template nests nothing)."""
    blocks = {}
    for m in re.finditer(r"location\s+(.+?)\s*\{(.*?)\n\s*\}", text, re.S):
        blocks[m.group(1).strip()] = m.group(2)
    return blocks


# ── Pure text invariants (no Docker) ────────────────────────────────────────


def test_template_exists():
    assert TEMPLATE.is_file(), f"missing template: {TEMPLATE}"
    assert ENTRYPOINT.is_file(), f"missing entrypoint: {ENTRYPOINT}"


def test_every_mcps_upstream_is_set_into_a_variable_once():
    text = _template()
    for name in PROVIDERS:
        pattern = rf"^\s*set \$mcps_{name.lower()}\s+\$\{{BOND_MCPS_{name}_UPSTREAM\}};\s*$"
        assert len(re.findall(pattern, text, re.M)) == 1, f"expected one `set $mcps_{name.lower()}` line"


def test_no_mcps_upstream_reaches_proxy_pass_as_a_literal():
    text = _template()
    literal = re.findall(r"proxy_pass\s+\$\{BOND_MCPS_\w+_UPSTREAM\}", text)
    assert literal == [], f"literal upstream in proxy_pass (nginx would cache its address at load): {literal}"
    hardcoded = re.findall(r"proxy_pass\s+https?://[^$][^;]*mcps[^;]*;", text)
    assert hardcoded == [], f"hard-coded mcps host in proxy_pass: {hardcoded}"


def test_each_proxied_location_uses_its_provider_variable():
    blocks = _location_blocks(_template())
    for match, var in PROXIED_LOCATIONS:
        assert match in blocks, f"location `{match}` missing"
        body = blocks[match]
        assert re.search(rf"proxy_pass\s+\${var};", body), f"location `{match}` must `proxy_pass ${var};`"
        # Host must stay the upstream's own name (ALB routes by Host), so no
        # override to the front-door host in these blocks.
        assert "proxy_set_header Host" not in body, f"location `{match}` must not override Host"


def test_resolver_is_declared_with_a_bounded_ttl():
    text = _template()
    m = re.search(r"^\s*resolver\s+\$\{NGINX_RESOLVER\}\s+(.*);\s*$", text, re.M)
    assert m, "server block must declare `resolver ${NGINX_RESOLVER} ...;`"
    params = m.group(1).split()
    valid = [p for p in params if p.startswith("valid=")]
    assert valid, "resolver needs `valid=` so a moved address is re-read on a schedule"
    seconds = int(valid[0].removeprefix("valid=").rstrip("s"))
    assert 5 <= seconds <= 120, f"valid={seconds}s: too short hammers DNS, too long re-creates the 2026-09-09 hang"
    assert "ipv6=off" in params
    assert re.search(r"^\s*resolver_timeout\s+\d+s;", text, re.M)


def test_entrypoint_substitutes_the_resolver_placeholder():
    script = ENTRYPOINT.read_text()
    whitelist = re.search(r"envsubst '([^']+)'", script)
    assert whitelist, "entrypoint must call envsubst with an explicit whitelist"
    names = set(re.findall(r"\$\{(\w+)\}", whitelist.group(1)))
    assert names == {f"BOND_MCPS_{p}_UPSTREAM" for p in PROVIDERS} | {"NGINX_RESOLVER"}, names
    assert "/etc/resolv.conf" in script, "the resolver must be lifted from the pod's own resolv.conf"


# ── Rendered config loads (Docker) ──────────────────────────────────────────

docker_only = pytest.mark.skipif(not _docker_available(), reason="Docker not available — skipping nginx -t")


def _render_in_container(extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the REAL entrypoint in the nginx image and print what it rendered."""
    cmd = ["docker", "run", "--rm"]
    for k, v in (extra_env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [
        "-v", f"{TEMPLATE}:/etc/nginx/templates/nginx-combined.conf.template:ro",
        "-v", f"{ENTRYPOINT}:/usr/local/bin/docker-entrypoint.sh:ro",
        "--entrypoint", "/usr/local/bin/docker-entrypoint.sh",
        NGINX_IMAGE,
        "sh", "-c", "nginx -t && cat /etc/nginx/conf.d/default.conf",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


@docker_only
def test_rendered_template_passes_nginx_t_with_default_upstreams():
    result = _render_in_container()
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "syntax is ok" in result.stderr
    rendered = result.stdout
    # Whatever nameserver /etc/resolv.conf names inside the container (Docker's
    # embedded DNS, or Docker Desktop's host resolver) — an address, not a
    # placeholder.
    assert re.search(r"^\s*resolver \d+\.\d+\.\d+\.\d+ valid=", rendered, re.M), rendered
    assert "set $mcps_microsoft  https://ms-graph.mcps.ai.southbayequity.cloud;" in rendered
    directives = [line for line in rendered.splitlines() if not line.lstrip().startswith("#")]
    assert not [line for line in directives if "${" in line], "an unsubstituted placeholder survived rendering"


@docker_only
def test_rendered_template_honours_upstream_and_resolver_overrides():
    result = _render_in_container({
        "BOND_MCPS_AUTH_UPSTREAM": "http://auth-server.bond-mcps.svc.cluster.local:8001",
        "NGINX_RESOLVER": "172.20.0.10",
    })
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    rendered = result.stdout
    assert re.search(r"^\s*resolver 172\.20\.0\.10 valid=", rendered, re.M)
    assert "set $mcps_auth       http://auth-server.bond-mcps.svc.cluster.local:8001;" in rendered
    # nginx's own runtime variables must survive envsubst's whitelist.
    assert "proxy_set_header X-Forwarded-Host $http_host;" in rendered
    assert "proxy_pass $mcps_auth;" in rendered
