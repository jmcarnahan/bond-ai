"""Integration tests for bond-mcps-delegated (managed) connections.

Drives bond-ai's Connections endpoints (list / authorize / status / disconnect)
through the real FastAPI router, with bond-mcps stubbed at the seam: discovery is
patched to advertise managed MCPs and the connect client is patched to stand in
for bond-mcps' /connect/<name>/{ticket,status} + DELETE. This exercises the full
delegation choreography from bond-ai's side, including the return-URL handoff and
fail-soft when bond-mcps is unreachable.
"""

import os
import tempfile
from datetime import timedelta

import pytest

_test_db_file = tempfile.NamedTemporaryFile(suffix="_deleg.db", delete=False)
os.environ["METADATA_DB_URL"] = f"sqlite:///{_test_db_file.name}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-delegation")
# Keep the static fallback empty-ish so only discovered managed MCPs appear.
os.environ["BOND_MCP_CONFIG"] = '{"mcpServers": {}}'

from fastapi.testclient import TestClient

from bondable.rest.main import app, create_access_token
import bondable.rest.routers.connections as conn

TEST_EMAIL = "deleg-test@example.com"
TEST_USER_ID = "deleg-user-1"

DISCOVERED = [
    {"name": "atlassian", "display_name": "Atlassian", "url": "http://localhost:18003/mcp"},
    {"name": "github", "display_name": "GitHub", "url": "http://localhost:18002/mcp"},
]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers():
    token = create_access_token(
        data={"sub": TEST_EMAIL, "user_id": TEST_USER_ID, "provider": "okta"},
        expires_delta=timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def patch_discovery(monkeypatch):
    """Advertise managed MCPs via discovery (used by the overlay + router)."""
    monkeypatch.setattr(conn, "get_discovered_mcps", lambda force_refresh=False: list(DISCOVERED))
    yield


class _StubMcps:
    """In-memory stand-in for bond-mcps connect endpoints."""

    def __init__(self):
        self.connected = set()
        self.tickets = []
        self.no_surface = set()  # providers that 404 (no connect flow)

    async def mint_connect_ticket(self, mcp_url, name, jwt_token, return_url):
        assert jwt_token, "JWT must be forwarded to bond-mcps"
        self.tickets.append({"name": name, "return_url": return_url, "url": mcp_url})
        return f"http://localhost:8000/connect/{name}?ticket=TKT&return_url={return_url}"

    async def get_connect_status(self, mcp_url, name, jwt_token, timeout=None):
        if name in self.no_surface:
            return None
        connected = name in self.connected
        return {"connected": connected, "valid": connected, "scopes": "s" if connected else None}

    async def delete_connection(self, mcp_url, name, jwt_token):
        existed = name in self.connected
        self.connected.discard(name)
        return existed


@pytest.fixture
def stub(monkeypatch):
    s = _StubMcps()
    monkeypatch.setattr(conn.mcp_connect_client, "mint_connect_ticket", s.mint_connect_ticket)
    monkeypatch.setattr(conn.mcp_connect_client, "get_connect_status", s.get_connect_status)
    monkeypatch.setattr(conn.mcp_connect_client, "delete_connection", s.delete_connection)
    return s


# --- list -----------------------------------------------------------------

def test_list_includes_managed_disconnected(client, headers, stub):
    resp = client.get("/connections", headers=headers)
    assert resp.status_code == 200
    by_name = {c["name"]: c for c in resp.json()["connections"]}
    assert set(by_name) >= {"atlassian", "github"}
    assert by_name["atlassian"]["auth_type"] == "bond_jwt"
    assert by_name["atlassian"]["connected"] is False
    assert by_name["atlassian"]["requires_authorization"] is True


def test_list_reflects_connected_state(client, headers, stub):
    stub.connected.add("atlassian")
    by_name = {c["name"]: c for c in client.get("/connections", headers=headers).json()["connections"]}
    assert by_name["atlassian"]["connected"] is True
    assert by_name["github"]["connected"] is False


def test_list_omits_mcp_without_connect_surface(client, headers, stub):
    stub.no_surface.add("github")  # github has no provider connection (404 on status)
    names = {c["name"] for c in client.get("/connections", headers=headers).json()["connections"]}
    assert "atlassian" in names
    assert "github" not in names


def test_list_failsoft_when_mcps_down(client, headers, monkeypatch):
    async def boom(*a, **k):
        raise conn.ConnectError("bond-mcps down")
    monkeypatch.setattr(conn.mcp_connect_client, "get_connect_status", boom)
    by_name = {c["name"]: c for c in client.get("/connections", headers=headers).json()["connections"]}
    # Still listed (so user can retry), shown disconnected.
    assert by_name["atlassian"]["connected"] is False


def test_list_failsoft_on_unexpected_error(client, headers, monkeypatch):
    """One MCP raising a non-ConnectError must not 500 the whole list."""
    async def kaboom(*a, **k):
        raise ValueError("unexpected")
    monkeypatch.setattr(conn.mcp_connect_client, "get_connect_status", kaboom)
    resp = client.get("/connections", headers=headers)
    assert resp.status_code == 200
    by_name = {c["name"]: c for c in resp.json()["connections"]}
    assert by_name["atlassian"]["connected"] is False
    assert by_name["github"]["connected"] is False


# --- authorize (delegation) ----------------------------------------------

def test_authorize_delegates_and_returns_connect_url(client, headers, stub):
    resp = client.get("/connections/atlassian/authorize", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorization_url"].startswith("http://localhost:8000/connect/atlassian?ticket=")
    # bond-ai passed a return_url back to its own /connections page.
    assert stub.tickets and stub.tickets[0]["name"] == "atlassian"
    assert stub.tickets[0]["return_url"].endswith("/connections")


def test_authorize_502_when_ticket_fails(client, headers, monkeypatch):
    async def boom(*a, **k):
        raise conn.ConnectError("ticket mint failed")
    monkeypatch.setattr(conn.mcp_connect_client, "mint_connect_ticket", boom)
    resp = client.get("/connections/atlassian/authorize", headers=headers)
    assert resp.status_code == 502


# --- status ---------------------------------------------------------------

def test_status_managed(client, headers, stub):
    stub.connected.add("github")
    resp = client.get("/connections/github/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    assert resp.json()["auth_type"] == "bond_jwt"


def test_status_404_for_no_surface(client, headers, stub):
    stub.no_surface.add("atlassian")
    resp = client.get("/connections/atlassian/status", headers=headers)
    assert resp.status_code == 404


# --- disconnect -----------------------------------------------------------

def test_disconnect_managed(client, headers, stub):
    stub.connected.add("atlassian")
    resp = client.delete("/connections/atlassian", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["disconnected"] is True
    assert "atlassian" not in stub.connected


def test_disconnect_managed_not_connected(client, headers, stub):
    resp = client.delete("/connections/github", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["disconnected"] is False


# --- full choreography ----------------------------------------------------

def test_full_connect_choreography(client, headers, stub):
    # 1. Initially disconnected.
    assert client.get("/connections/atlassian/status", headers=headers).json()["connected"] is False
    # 2. Authorize -> get connect_url (browser would visit bond-mcps).
    connect_url = client.get("/connections/atlassian/authorize", headers=headers).json()["authorization_url"]
    assert "/connect/atlassian" in connect_url
    # 3. Simulate bond-mcps completing the provider OAuth + storing the token.
    stub.connected.add("atlassian")
    # 4. Back in bond-ai: status now shows connected.
    assert client.get("/connections/atlassian/status", headers=headers).json()["connected"] is True
    # 5. Disconnect cleans up in bond-mcps.
    assert client.delete("/connections/atlassian", headers=headers).json()["disconnected"] is True
    assert client.get("/connections/atlassian/status", headers=headers).json()["connected"] is False


def test_managed_endpoints_require_auth(client, stub):
    assert client.get("/connections/atlassian/authorize").status_code == 401
    assert client.delete("/connections/atlassian").status_code == 401
