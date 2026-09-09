"""Validation of deployment/nginx-combined.conf.template (the PROD front door)
and deployment/docker-entrypoint.sh, which renders it at container start.

Three layers, each skipping what it cannot run:

1. Text invariants (always run): every bond-mcps upstream reaches proxy_pass
   through a VARIABLE and never as a literal; the resolver carries a bounded
   `valid=`; every proxied block bounds its connect timeout; the entrypoint's
   envsubst whitelist is exactly the six placeholders.
2. Entrypoint rendering (Docker): the REAL entrypoint runs in nginx:1.26.3 (the
   Debian family Dockerfile.combined installs nginx from) and `nginx -t` loads
   what it wrote — with default upstreams, with in-cluster overrides, with
   several nameservers, with an IPv6 nameserver — and every validation path
   stops the container with a named reason instead of rendering a config that
   would misroute.
3. Behaviour (Docker network): a running nginx follows a DNS change for its
   upstream with no reload; the request URI and query reach the upstream
   unchanged with Host set to the upstream's own name; an unreachable upstream
   is a 504 in about ten seconds rather than sixty.

Why the variable rule is load-bearing: nginx resolves a literal proxy_pass
hostname once at load and keeps the addresses for the worker's life. The
*.mcps.* ALB addresses move, and on 2026-09-09 every proxied path hung against
addresses cached nine days earlier. A variable makes nginx resolve per request
through `resolver`, which is why a future edit that reintroduces
`proxy_pass https://...mcps...;` must fail here.
"""
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "deployment" / "nginx-combined.conf.template"
ENTRYPOINT = REPO_ROOT / "deployment" / "docker-entrypoint.sh"
NGINX_IMAGE = "nginx:1.26.3"
PYTHON_IMAGE = "python:3.12-slim"
DNS_IMAGE = "alpine:3.20"

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
CONNECT_TIMEOUT_SECONDS = 10
RESOLVER_VALID_SECONDS = 30


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode == 0


def _template() -> str:
    return TEMPLATE.read_text()


def _location_blocks(text: str) -> dict[str, str]:
    """Map each `location <match>` to its body, tracking braces so a nested
    block inside a location (an `if`, say) stays part of that location."""
    blocks: dict[str, str] = {}
    for m in re.finditer(r"location\s+([^{\n]+?)\s*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        blocks[m.group(1).strip()] = text[m.end() : i - 1]
    return blocks


# ── 1. Text invariants (no Docker) ───────────────────────────────────────────


def test_template_and_entrypoint_exist():
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


def test_each_proxied_location_uses_its_provider_variable_and_bounds_connect():
    blocks = _location_blocks(_template())
    for match, var in PROXIED_LOCATIONS:
        assert match in blocks, f"location `{match}` missing"
        body = blocks[match]
        assert re.search(rf"proxy_pass\s+\${var};", body), f"location `{match}` must `proxy_pass ${var};`"
        assert re.search(rf"proxy_connect_timeout\s+{CONNECT_TIMEOUT_SECONDS}s;", body), (
            f"location `{match}` must bound its connect timeout (the default is 60 s per address)"
        )
        # Host must stay the upstream's own name (the ALB routes by Host), so
        # no override to the front-door host in these blocks.
        assert "proxy_set_header Host" not in body, f"location `{match}` must not override Host"


def test_no_other_location_proxies_to_a_variable():
    """The resolver-per-request path is for bond-mcps only; the local backend
    and static locations must keep their literal targets."""
    blocks = _location_blocks(_template())
    proxied = {match for match, _ in PROXIED_LOCATIONS}
    for match, body in blocks.items():
        if match in proxied:
            continue
        assert not re.search(r"proxy_pass\s+\$", body), f"location `{match}` proxies to a variable"


def test_resolver_is_declared_with_a_bounded_ttl():
    text = _template()
    m = re.search(r"^\s*resolver\s+\$\{NGINX_RESOLVER\}\s+(.*);\s*$", text, re.M)
    assert m, "server block must declare `resolver ${NGINX_RESOLVER} ...;`"
    params = m.group(1).split()
    valid = [p for p in params if p.startswith("valid=")]
    assert valid, "resolver needs `valid=` so a moved address is re-read on a schedule"
    seconds = int(valid[0].removeprefix("valid=").rstrip("s"))
    assert seconds == RESOLVER_VALID_SECONDS, "the behaviour test below waits on this exact window"
    assert 5 <= seconds <= 120, f"valid={seconds}s: too short hammers DNS, too long re-creates the 2026-09-09 hang"
    assert "ipv6=off" in params
    assert re.search(r"^\s*resolver_timeout\s+\d+s;", text, re.M)


def test_entrypoint_substitutes_exactly_the_six_placeholders():
    script = ENTRYPOINT.read_text()
    whitelist = re.search(r"envsubst '([^']+)'", script)
    assert whitelist, "entrypoint must call envsubst with an explicit whitelist"
    names = set(re.findall(r"\$\{(\w+)\}", whitelist.group(1)))
    assert names == {f"BOND_MCPS_{p}_UPSTREAM" for p in PROVIDERS} | {"NGINX_RESOLVER"}, names
    placeholders = set(re.findall(r"\$\{([A-Z_]+)\}", _template()))
    assert placeholders == names, "template placeholders and the whitelist must agree"


# ── 2. Entrypoint rendering (Docker) ─────────────────────────────────────────

docker_only = pytest.mark.skipif(not _docker_available(), reason="Docker not available")


def _entrypoint(
    *,
    env: dict[str, str] | None = None,
    resolv_conf: Path | None = None,
    command: str = "nginx -t && cat /etc/nginx/conf.d/default.conf",
) -> subprocess.CompletedProcess:
    """Run the REAL entrypoint in the nginx image; the CMD it execs prints what
    it rendered (or never runs, when validation stops it first)."""
    cmd = ["docker", "run", "--rm"]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    if resolv_conf is not None:
        cmd += ["-v", f"{resolv_conf}:/etc/resolv.conf:ro"]
    cmd += [
        "-v", f"{TEMPLATE}:/etc/nginx/templates/nginx-combined.conf.template:ro",
        "-v", f"{ENTRYPOINT}:/usr/local/bin/docker-entrypoint.sh:ro",
        "--entrypoint", "/usr/local/bin/docker-entrypoint.sh",
        NGINX_IMAGE, "sh", "-c", command,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _directives(rendered: str) -> list[str]:
    return [line for line in rendered.splitlines() if not line.lstrip().startswith("#")]


def _resolver_line(rendered: str) -> str:
    m = re.search(r"^\s*resolver (.*);$", rendered, re.M)
    assert m, rendered
    return m.group(1)


@docker_only
def test_rendered_template_passes_nginx_t_with_default_upstreams():
    result = _entrypoint()
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "syntax is ok" in result.stderr
    rendered = result.stdout
    # Whatever nameserver /etc/resolv.conf names inside the container — an
    # address, never the placeholder.
    assert re.match(r"\d+\.\d+\.\d+\.\d+ valid=", _resolver_line(rendered))
    assert "set $mcps_microsoft  https://ms-graph.mcps.ai.southbayequity.cloud;" in rendered
    assert not [line for line in _directives(rendered) if "${" in line], "a placeholder survived rendering"


@docker_only
def test_rendered_template_honours_in_cluster_upstream_and_resolver_overrides():
    result = _entrypoint(env={
        "BOND_MCPS_AUTH_UPSTREAM": "http://auth-server.bond-mcps.svc.cluster.local:8001",
        "NGINX_RESOLVER": "172.20.0.10",
    })
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    rendered = result.stdout
    assert _resolver_line(rendered).startswith("172.20.0.10 valid=")
    assert "set $mcps_auth       http://auth-server.bond-mcps.svc.cluster.local:8001;" in rendered
    # nginx's own runtime variables must survive envsubst's whitelist.
    assert "proxy_set_header X-Forwarded-Host $http_host;" in rendered
    assert "proxy_pass $mcps_auth;" in rendered


@docker_only
def test_every_nameserver_in_resolv_conf_is_passed_to_nginx(tmp_path: Path):
    resolv = tmp_path / "resolv.conf"
    resolv.write_text("search bond-ai.svc.cluster.local svc.cluster.local\nnameserver 10.1.1.1\nnameserver 10.1.1.2\noptions ndots:5\n")
    result = _entrypoint(resolv_conf=resolv)
    assert result.returncode == 0, result.stderr
    assert _resolver_line(result.stdout).startswith("10.1.1.1 10.1.1.2 valid=")


@docker_only
def test_ipv6_nameservers_are_bracketed_the_way_nginx_spells_them():
    result = _entrypoint(env={"NGINX_RESOLVER": "10.0.0.2 fd00::53 [fd00::54]"})
    assert result.returncode == 0, result.stderr
    assert _resolver_line(result.stdout).startswith("10.0.0.2 [fd00::53] [fd00::54] valid=")


@docker_only
def test_trailing_slashes_on_an_upstream_are_forgiven():
    result = _entrypoint(env={"BOND_MCPS_GITHUB_UPSTREAM": "https://github.example.test//"})
    assert result.returncode == 0, result.stderr
    assert "set $mcps_github     https://github.example.test;" in result.stdout


@pytest.mark.parametrize(
    ("env", "reason"),
    [
        # A variable proxy_pass WITH a URI part replaces the request URI with
        # it: every callback would land on /mcp.
        ({"BOND_MCPS_AUTH_UPSTREAM": "https://auth.example.test/mcp"}, "no path"),
        # Anything past scheme://host[:port] could close the directive.
        ({"BOND_MCPS_AUTH_UPSTREAM": "https://x.test; return 200"}, "no path"),
        ({"BOND_MCPS_AUTH_UPSTREAM": "auth.example.test"}, "no path"),
        ({"NGINX_RESOLVER": "coredns"}, "not an IP address"),
    ],
    ids=["path", "injection", "no-scheme", "resolver-not-an-ip"],
)
@docker_only
def test_a_bad_value_stops_the_container_with_a_named_reason(env, reason):
    result = _entrypoint(env=env, command="echo RENDERED")
    assert result.returncode == 1, f"expected refusal, got {result.returncode}: {result.stdout} {result.stderr}"
    assert "docker-entrypoint:" in result.stderr and reason in result.stderr, result.stderr
    assert "RENDERED" not in result.stdout, "the CMD must never run on a refused config"


@docker_only
def test_no_nameserver_anywhere_stops_the_container(tmp_path: Path):
    empty = tmp_path / "resolv.conf"
    empty.write_text("search example.test\n")
    result = _entrypoint(resolv_conf=empty, command="echo RENDERED")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no nameserver" in result.stderr
    assert "RENDERED" not in result.stdout


# ── 3. Behaviour on a Docker network ─────────────────────────────────────────

# An HTTP server that answers every path with its own name plus what it saw:
# the request path (query included) and the Host header.
ECHO_SERVER = """
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"who": sys.argv[1], "path": self.path, "host": self.headers.get("Host")}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("", 9999), H).serve_forever()
"""


def _sh(*cmd: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check:
        assert result.returncode == 0, f"{' '.join(cmd)}\n{result.stdout}\n{result.stderr}"
    return result


def _http(url: str, timeout: int = 20) -> tuple[int, str, float]:
    """(status, body, seconds) — through curl so the test needs no HTTP client
    beyond what every developer machine has."""
    start = time.monotonic()
    result = subprocess.run(
        ["curl", "-sS", "-o", "-", "-w", "\n%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True, timeout=timeout + 5,
    )
    body, _, status = result.stdout.rpartition("\n")
    return int(status or 0), body, time.monotonic() - start


class _Lab:
    """One Docker network with two echo backends and a dnsmasq whose answer
    for fake.test the test can flip. Everything is named per run and removed
    afterwards, even on failure."""

    SUBNET = "172.31.99.0/24"
    BE1, BE2, DNS = "172.31.99.11", "172.31.99.12", "172.31.99.53"

    def __init__(self) -> None:
        self.tag = uuid.uuid4().hex[:8]
        self.net = f"nxlab-{self.tag}"
        self.containers: list[str] = []

    def _name(self, role: str) -> str:
        name = f"{role}-{self.tag}"
        self.containers.append(name)
        return name

    def up(self) -> None:
        _sh("docker", "network", "create", "--subnet", self.SUBNET, self.net)
        for ip, who in ((self.BE1, "be1"), (self.BE2, "be2")):
            _sh("docker", "run", "-d", "--name", self._name(who), "--network", self.net, "--ip", ip,
                PYTHON_IMAGE, "python", "-c", ECHO_SERVER, who)
        self.point_dns_at(self.BE1)

    def point_dns_at(self, ip: str) -> None:
        name = f"dns-{self.tag}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        if name not in self.containers:
            self.containers.append(name)
        _sh("docker", "run", "-d", "--name", name, "--network", self.net, "--ip", self.DNS, DNS_IMAGE,
            "sh", "-c", f"apk add -q dnsmasq && exec dnsmasq -k --no-resolv --address=/fake.test/{ip}")
        # dnsmasq answers once apk has installed it.
        for _ in range(60):
            probe = subprocess.run(
                ["docker", "run", "--rm", "--network", self.net, "--dns", self.DNS, PYTHON_IMAGE,
                 "python", "-c", "import socket;print(socket.gethostbyname('fake.test'))"],
                capture_output=True, text=True, timeout=30,
            )
            if probe.stdout.strip() == ip:
                return
            time.sleep(1)
        raise AssertionError(f"dnsmasq never answered fake.test -> {ip}")

    def nginx(self, port: int, **env: str) -> str:
        # One nginx per test, each on its own port and under its own name.
        name = self._name(f"nx{port}")
        cmd = ["docker", "run", "-d", "--name", name, "--network", self.net, "-p", f"{port}:8080",
               "-e", f"NGINX_RESOLVER={self.DNS}"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += ["-v", f"{TEMPLATE}:/etc/nginx/templates/nginx-combined.conf.template:ro",
                "-v", f"{ENTRYPOINT}:/usr/local/bin/docker-entrypoint.sh:ro",
                "--entrypoint", "/usr/local/bin/docker-entrypoint.sh",
                NGINX_IMAGE, "nginx", "-g", "daemon off;"]
        _sh(*cmd)
        for _ in range(30):
            status, _, _ = _http(f"http://localhost:{port}/health", timeout=3)
            if status:
                return name
            time.sleep(0.5)
        raise AssertionError(f"nginx {name} never answered on :{port}")

    def down(self) -> None:
        for name in self.containers:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "network", "rm", self.net], capture_output=True)


@pytest.fixture(scope="module")
def lab():
    if not _docker_available():
        pytest.skip("Docker not available")
    lab = _Lab()
    try:
        lab.up()
        yield lab
    finally:
        lab.down()


@docker_only
def test_request_uri_query_and_host_reach_the_upstream_unchanged(lab: _Lab):
    port = 18120
    lab.nginx(port, BOND_MCPS_MICROSOFT_UPSTREAM="http://fake.test:9999")
    status, body, _ = _http(f"http://localhost:{port}/connections/microsoft/callback?code=abc&state=xyz")
    assert status == 200, body
    seen = json.loads(body)
    # The variable form must forward the URI as-is: the code and state a
    # provider sends back are what the callback consumes.
    assert seen["path"] == "/connections/microsoft/callback?code=abc&state=xyz"
    # Host is the upstream's own name — the shared ALB routes on it.
    assert seen["host"] == "fake.test:9999"
    status, body, _ = _http(f"http://localhost:{port}/connect/microsoft?ticket=t1&return_url=https%3A%2F%2Fa.test%2Fconnections")
    assert status == 200 and json.loads(body)["path"] == "/connect/microsoft?ticket=t1&return_url=https%3A%2F%2Fa.test%2Fconnections"


@docker_only
def test_a_running_nginx_follows_a_dns_change_with_no_reload(lab: _Lab):
    """The 2026-09-09 fault, replayed: the upstream's address moves while
    nginx runs. The old literal form kept the stale address for the worker's
    life; the variable form re-resolves once `valid=` expires."""
    port = 18121
    lab.nginx(port, BOND_MCPS_GITHUB_UPSTREAM="http://fake.test:9999")
    status, body, _ = _http(f"http://localhost:{port}/connect/github/status")
    assert status == 200 and json.loads(body)["who"] == "be1", body

    lab.point_dns_at(lab.BE2)
    # Several workers each keep their own cache; only after the window has
    # passed for all of them is the answer deterministic.
    time.sleep(RESOLVER_VALID_SECONDS + 2)
    status, body, _ = _http(f"http://localhost:{port}/connect/github/status")
    assert status == 200 and json.loads(body)["who"] == "be2", body


@docker_only
def test_an_unreachable_upstream_fails_in_seconds_not_a_minute(lab: _Lab):
    """A silently-dropped address stands in for the ALB's abandoned IPs.
    192.0.2.1 is TEST-NET-1 (RFC 5737): never routed, so SYNs vanish exactly as
    they did on 2026-09-09. (An unused address on the lab's OWN subnet would
    fail ARP in seconds and answer 502 — a different, faster failure.) Before
    proxy_connect_timeout was bounded this took 60 s per address."""
    port = 18122
    lab.nginx(port, BOND_MCPS_ATLASSIAN_UPSTREAM="http://192.0.2.1:9")
    status, _, seconds = _http(f"http://localhost:{port}/connect/atlassian/status", timeout=40)
    assert status == 504, status
    assert CONNECT_TIMEOUT_SECONDS - 1 <= seconds <= CONNECT_TIMEOUT_SECONDS + 5, f"took {seconds:.1f}s"
