"""Offline validation of deployment/nginx-local-combined.conf.

Runs `nginx -t` inside an ephemeral nginx:1.27-alpine container against the
local-combined config so a config syntax error never makes it past CI. Skips
silently if Docker is not available.

Also enforces the design invariants documented in the config header:
  - listen 8000 (matches existing OAuth callback URL registrations)
  - All upstreams use host.docker.internal (nginx runs in a container)
  - No HSTS header (would force HTTPS over local HTTP dev)
  - /auth/ proxies to backend :8002
  - /connections/ proxies to bond-mcps :18000 (NOT :8000 — nginx owns :8000)
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


def test_nginx_local_combined_conf_listens_on_8000():
    """The front-door port must be 8000 — that's where every OAuth provider
    already has its callback URLs registered. Changing this breaks every
    OAuth flow until provider consoles are updated."""
    text = NGINX_CONF.read_text()
    assert re.search(r"^\s*listen\s+8000\s*;", text, re.MULTILINE), (
        "front door must listen on :8000 to match existing OAuth callback URLs"
    )


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
    """True if the config has an uncommented `location <path>` block."""
    pattern = re.compile(r"^\s*location\s+" + re.escape(path), re.MULTILINE)
    return bool(pattern.search(text))


def test_nginx_local_combined_conf_routes_auth_to_backend():
    """User-login OAuth callbacks (Google/Okta/Cognito) come back to
    /auth/<provider>/callback on the front door and must reach bond-ai :8002."""
    text = NGINX_CONF.read_text()
    assert _has_active_location_block(text, "/auth/"), "missing /auth/ proxy block"
    # Find the block and check its upstream.
    start = text.index("location /auth/")
    block = text[start : start + 400]
    assert "host.docker.internal:8002" in block, (
        "/auth/ must proxy to bond-ai backend on :8002"
    )


def test_nginx_local_combined_conf_routes_connections_to_mcps_18000():
    """MCP OAuth callbacks come back to /connections/<svc>/callback on the
    front door. bond-mcps's auth proxy moves to :18000 in combined mode
    (because nginx took :8000). Make sure routing reflects that."""
    text = NGINX_CONF.read_text()
    assert _has_active_location_block(text, "/connections/"), "missing /connections/ proxy block"
    start = text.index("location /connections/")
    block = text[start : start + 600]
    assert "host.docker.internal:18000" in block, (
        "/connections/ must proxy to bond-mcps on :18000 (combined-mode port). "
        "Pointing at :8000 would loop back to nginx itself."
    )


def test_nginx_local_combined_conf_routes_rest_and_root():
    """The two app-serving routes: /rest/ to bond-ai, / to Flutter."""
    text = NGINX_CONF.read_text()
    assert _has_active_location_block(text, "/rest/"), (
        "missing /rest/ proxy block — API calls from the app won't reach the backend"
    )
    assert _has_active_location_block(text, "/"), "missing default `/` proxy block — app UI won't load"
