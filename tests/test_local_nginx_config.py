"""Offline validation of deployment/nginx-local-combined.conf.

Runs `nginx -t` inside an ephemeral nginx:1.27-alpine container against the
local-combined config so a config syntax error never makes it past CI. Skips
silently if Docker is not available.

Also enforces the design invariants documented in the config header:
  - All upstreams use host.docker.internal (nginx runs in a container).
  - No HSTS header (would force HTTPS over local HTTP dev).
  - OAuth callback routes (/auth/, /connections/) deliberately bypass nginx.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NGINX_CONF = REPO_ROOT / "deployment" / "nginx-local-combined.conf"
NGINX_IMAGE = "nginx:1.27-alpine"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker not available — skipping nginx config syntax check",
)


def test_nginx_local_combined_conf_exists():
    assert NGINX_CONF.is_file(), f"missing config file: {NGINX_CONF}"


def test_nginx_local_combined_conf_is_syntactically_valid():
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{NGINX_CONF}:/etc/nginx/conf.d/default.conf:ro",
            NGINX_IMAGE,
            "nginx",
            "-t",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"nginx -t failed for {NGINX_CONF.name}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "syntax is ok" in result.stderr.lower() or "successful" in result.stderr.lower()


def test_nginx_local_combined_conf_uses_host_docker_internal():
    """All upstreams must use host.docker.internal so the nginx container can
    reach host-running services. 127.0.0.1 inside the container is the
    container itself, not the host — common source of confusion."""
    text = NGINX_CONF.read_text()
    for forbidden in ("proxy_pass http://127.0.0.1", "proxy_pass http://localhost"):
        assert forbidden not in text, (
            f"found '{forbidden}' — local-combined nginx runs inside a container "
            f"and must use host.docker.internal for upstreams"
        )


def test_nginx_local_combined_conf_drops_hsts_header():
    """HSTS forces HTTPS — would break local HTTP dev. Must be absent."""
    text = NGINX_CONF.read_text()
    assert "Strict-Transport-Security" not in text, (
        "HSTS header would force HTTPS upgrade and break local HTTP dev"
    )


def _has_active_location_block(text: str, path: str) -> bool:
    """Return True if the config has an uncommented `location <path>` block.

    The regex anchors on the start of a logical line (optional leading
    whitespace). Comment lines start with `#`, so they don't match.
    """
    pattern = re.compile(r"^\s*location\s+" + re.escape(path), re.MULTILINE)
    return bool(pattern.search(text))


def test_nginx_local_combined_conf_does_not_route_auth():
    """OAuth user-login callbacks deliberately bypass nginx and hit
    bond-ai :8002 directly (browser navigates straight there). Cookies set
    on :8002 cross over to :8080 thanks to localhost cross-port cookie
    behavior — see docs/local-dev-combined-mode.md. If we route /auth/
    through nginx, the design changes substantially; don't do it by accident."""
    text = NGINX_CONF.read_text()
    assert not _has_active_location_block(text, "/auth/"), (
        "/auth/ must NOT route through nginx — OAuth user-login callbacks "
        "go directly to bond-ai :8002 by design"
    )


def test_nginx_local_combined_conf_does_not_route_connections():
    """MCP OAuth callbacks deliberately bypass nginx and hit bond-mcps
    :8000 directly. Same rationale as the /auth/ guard above — the design
    relies on the existing :8000 callback URLs continuing to work, with
    cross-port cookies handling session continuity."""
    text = NGINX_CONF.read_text()
    assert not _has_active_location_block(text, "/connections/"), (
        "/connections/ must NOT route through nginx — MCP OAuth callbacks "
        "go directly to bond-mcps :8000 by design"
    )


def test_nginx_local_combined_conf_routes_rest_and_root():
    """The two routes nginx DOES handle: /rest/ to bond-ai backend, and /
    to the Flutter dev server. Make sure neither was accidentally dropped."""
    text = NGINX_CONF.read_text()
    assert _has_active_location_block(text, "/rest/"), (
        "missing /rest/ proxy block — API calls from the app won't reach the backend"
    )
    assert _has_active_location_block(text, "/"), "missing default `/` proxy block — app UI won't load"
