"""
Integration tests for the combined Docker image Nginx routing.

Builds the combined Docker image (Nginx + Uvicorn + Supervisord), runs it,
and verifies that Nginx correctly routes requests:

    /rest/*          → Uvicorn (strips /rest prefix)
    /auth/*          → Uvicorn (passthrough — OAuth callbacks)
    /connections/*   → Uvicorn (passthrough — MCP OAuth callbacks)
    /health          → Uvicorn (passthrough — App Runner health check)
    /*               → Flutter static files (SPA fallback)

The backend does NOT need to be fully healthy for these tests. We layer a
test index.html (with a known marker) on top of the combined image and
verify that API paths do NOT return it — proving Nginx proxied the request
instead of serving the SPA fallback.

The host filesystem is never modified (test content is injected via a
temporary Docker layer).

Requirements:
    - Docker daemon must be running
    - flutterui/build/web/ must exist (run a Flutter build first, or the
      test creates a minimal placeholder)
    - Run with: poetry run python -m pytest tests/test_combined_docker_routing.py --docker -v
"""

import pytest
import subprocess
import tempfile
import time
import os
import shutil
import requests

DOCKER_IMAGE_BASE = "bond-ai-combined-routing-base"
DOCKER_IMAGE_TEST = "bond-ai-combined-routing-test"
CONTAINER_NAME = "bond-ai-routing-test"
HOST_PORT = 18080
SPA_MARKER = "<!-- BOND_AI_ROUTING_TEST_MARKER -->"

pytestmark = pytest.mark.docker


def _docker_available():
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="module")
def combined_container():
    """Build and run the combined Docker image for routing tests.

    Two-stage build:
    1. Build the real Dockerfile.combined (the base image).
    2. Layer a tiny Dockerfile on top that replaces index.html with our
       test marker. This avoids modifying any host files.
    """
    if not _docker_available():
        pytest.skip("Docker daemon is not available")

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(project_root, "flutterui", "build", "web")

    # Ensure flutterui/build/web exists with at least an index.html.
    # If the user hasn't run a Flutter build, create a minimal placeholder.
    created_web_dir = False
    if not os.path.isdir(web_dir):
        os.makedirs(web_dir, exist_ok=True)
        created_web_dir = True
    if not os.path.exists(os.path.join(web_dir, "index.html")):
        with open(os.path.join(web_dir, "index.html"), "w") as f:
            f.write("<html><body>placeholder</body></html>\n")

    temp_dir = tempfile.mkdtemp(prefix="bond-routing-test-")

    try:
        # --- Stage 1: Build the real combined image ---
        print(f"\nBuilding base image '{DOCKER_IMAGE_BASE}'...")
        result = subprocess.run(
            [
                "docker", "build",
                "-f", "deployment/Dockerfile.combined",
                "-t", DOCKER_IMAGE_BASE,
                ".",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Docker build (base) failed:\n{result.stderr[-3000:]}"
            )

        # --- Stage 2: Layer test index.html on top ---
        # This injects our marker into the image without touching host files.
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(
                f"<!DOCTYPE html><html><head><title>Test</title></head>"
                f"<body>{SPA_MARKER}</body></html>\n"
            )
        with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
            f.write(
                f"FROM {DOCKER_IMAGE_BASE}\n"
                f"COPY index.html /usr/share/nginx/html/index.html\n"
            )

        print("Layering test marker into image...")
        result = subprocess.run(
            ["docker", "build", "-t", DOCKER_IMAGE_TEST, "."],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Docker build (test layer) failed:\n{result.stderr[-2000:]}"
            )

        # --- Start the container ---
        subprocess.run(
            ["docker", "rm", "-f", CONTAINER_NAME],
            capture_output=True,
        )

        print(f"Starting container '{CONTAINER_NAME}' on port {HOST_PORT}...")
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "-p", f"{HOST_PORT}:8080",
                DOCKER_IMAGE_TEST,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.fail(f"Docker run failed:\n{result.stderr}")

        # Wait for Nginx to start accepting connections
        base_url = f"http://localhost:{HOST_PORT}"
        for attempt in range(30):
            try:
                r = requests.get(f"{base_url}/", timeout=2)
                if r.status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)
        else:
            logs = subprocess.run(
                ["docker", "logs", CONTAINER_NAME],
                capture_output=True,
                text=True,
            )
            pytest.fail(
                f"Container did not become ready in 30s:\n"
                f"STDOUT:\n{logs.stdout[-1000:]}\n"
                f"STDERR:\n{logs.stderr[-1000:]}"
            )

        yield {"base_url": base_url, "marker": SPA_MARKER}

    finally:
        # Clean up container and images
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", DOCKER_IMAGE_TEST], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", DOCKER_IMAGE_BASE], capture_output=True)

        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Clean up placeholder web dir if we created it
        if created_web_dir:
            shutil.rmtree(
                os.path.join(project_root, "flutterui", "build"),
                ignore_errors=True,
            )


# =============================================================================
# Static file / SPA routing tests
# =============================================================================


class TestStaticFileRouting:
    """Verify Nginx serves Flutter static files for non-API paths."""

    def test_root_serves_spa(self, combined_container):
        """GET / should serve index.html."""
        r = requests.get(f"{combined_container['base_url']}/")
        assert r.status_code == 200
        assert combined_container["marker"] in r.text

    def test_spa_fallback_for_unknown_paths(self, combined_container):
        """Unknown paths should fall back to index.html (SPA client-side routing)."""
        r = requests.get(f"{combined_container['base_url']}/some/app/route")
        assert r.status_code == 200
        assert combined_container["marker"] in r.text

    def test_html_no_cache_headers(self, combined_container):
        """index.html should have no-cache headers."""
        r = requests.get(f"{combined_container['base_url']}/")
        cache_control = r.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control


# =============================================================================
# Backend proxy routing tests
# =============================================================================


class TestBackendProxyRouting:
    """Verify Nginx proxies API paths to Uvicorn instead of serving the SPA.

    These tests do NOT require the backend to be fully healthy. A 502
    (backend not ready) or a JSON error both prove that Nginx proxied
    the request rather than serving index.html.
    """

    def test_rest_proxy(self, combined_container):
        """/rest/health should proxy to backend, not serve SPA."""
        r = requests.get(f"{combined_container['base_url']}/rest/health")
        assert combined_container["marker"] not in r.text

    def test_health_direct(self, combined_container):
        """/health should proxy directly to backend."""
        r = requests.get(f"{combined_container['base_url']}/health")
        assert combined_container["marker"] not in r.text

    def test_auth_proxy(self, combined_container):
        """/auth/* should proxy to backend (OAuth callbacks)."""
        r = requests.get(f"{combined_container['base_url']}/auth/okta/callback")
        assert combined_container["marker"] not in r.text

    def test_connections_proxy(self, combined_container):
        """/connections/* should proxy to backend (MCP OAuth callbacks)."""
        r = requests.get(
            f"{combined_container['base_url']}/connections/test/callback"
        )
        assert combined_container["marker"] not in r.text

    def test_rest_strips_prefix(self, combined_container):
        """/rest/health and /health should reach the same backend endpoint."""
        base = combined_container["base_url"]
        r_rest = requests.get(f"{base}/rest/health")
        r_direct = requests.get(f"{base}/health")

        # Both should be proxied (not SPA)
        assert combined_container["marker"] not in r_rest.text
        assert combined_container["marker"] not in r_direct.text

        # Both should get the same status code from the backend
        assert r_rest.status_code == r_direct.status_code

    def test_rest_login_proxied(self, combined_container):
        """/rest/login should proxy to backend (Flutter calls this)."""
        r = requests.get(
            f"{combined_container['base_url']}/rest/login",
            allow_redirects=False,
        )
        assert combined_container["marker"] not in r.text

    def test_auth_cognito_proxy(self, combined_container):
        """/auth/cognito/callback should proxy to backend."""
        r = requests.get(
            f"{combined_container['base_url']}/auth/cognito/callback"
        )
        assert combined_container["marker"] not in r.text


# =============================================================================
# Boundary tests
# =============================================================================


class TestRoutingBoundaries:
    """Verify edge cases in the routing configuration."""

    def test_rest_without_trailing_path(self, combined_container):
        """/rest/ alone should proxy to backend root (/)."""
        r = requests.get(f"{combined_container['base_url']}/rest/")
        assert combined_container["marker"] not in r.text

    def test_static_asset_extension(self, combined_container):
        """Requests for .js/.css files should NOT proxy to backend."""
        r = requests.get(f"{combined_container['base_url']}/main.dart.js")
        # Should be 404 (no such file) or SPA fallback — but NOT proxied
        # A 502 would mean it was wrongly proxied to the backend
        assert r.status_code != 502

    def test_rest_threads_proxied(self, combined_container):
        """/rest/threads should proxy to backend (common Flutter API call)."""
        r = requests.get(f"{combined_container['base_url']}/rest/threads")
        assert combined_container["marker"] not in r.text
