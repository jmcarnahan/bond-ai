"""Offline validation of deployment/nginx-local-combined.conf.

Runs `nginx -t` inside an ephemeral nginx:1.27-alpine container against the
local-combined config so a config syntax error never makes it past CI. Skips
silently if Docker is not available (e.g. CI environments without docker-in-
docker — the local Makefile path is what catches it there).
"""
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


def test_nginx_local_combined_conf_routes_connections_to_mcps_port():
    """Regression guard: /connections/ must point at :8000 (bond-mcps), not :8002
    (bond-ai backend). The MCP OAuth callbacks live in bond-mcps now."""
    text = NGINX_CONF.read_text()
    assert "location /connections/" in text
    # The proxy_pass line for /connections/ must reference :8000.
    # Capture the block to verify.
    start = text.index("location /connections/")
    block = text[start : start + 600]
    assert "host.docker.internal:8000" in block, (
        "/connections/ must proxy to bond-mcps on :8000, not bond-ai :8002"
    )


def test_nginx_local_combined_conf_uses_host_docker_internal():
    """All upstreams must use host.docker.internal so the nginx container can
    reach host-running services. 127.0.0.1 inside the container is the
    container itself, not the host — common source of confusion."""
    text = NGINX_CONF.read_text()
    # Block any proxy_pass to 127.0.0.1 or localhost (would target the
    # container, not the host).
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
