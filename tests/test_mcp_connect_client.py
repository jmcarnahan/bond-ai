"""Unit tests for the bond-mcps connect (OAuth delegation) HTTP client."""

import httpx
import pytest

from bondable.bond import mcp_connect_client as cc
from bondable.bond.mcp_connect_client import ConnectError


MCP_URL = "http://localhost:18003/mcp"


class FakeResp:
    def __init__(self, payload=None, status_code=200, content=b"{}"):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture
def fake_http(monkeypatch):
    """Patch the async httpx client; tests set `handler` and inspect `calls`."""
    state = {"handler": lambda method, url, **kw: FakeResp(), "calls": []}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            state["calls"].append({"method": "POST", "url": url, "json": json, "headers": headers})
            return state["handler"]("POST", url, json=json, headers=headers)

        async def get(self, url, headers=None):
            state["calls"].append({"method": "GET", "url": url, "headers": headers})
            return state["handler"]("GET", url, headers=headers)

        async def request(self, method, url, headers=None):
            state["calls"].append({"method": method, "url": url, "headers": headers})
            return state["handler"](method, url, headers=headers)

    monkeypatch.setattr(cc.httpx, "AsyncClient", FakeClient)
    return state


# --- base URL (sync helpers) ----------------------------------------------

def test_connect_base_url_strips_path():
    assert cc.connect_base_url("http://localhost:18003/mcp") == "http://localhost:18003"
    assert cc.connect_base_url("https://github.mcps.example.com/mcp") == "https://github.mcps.example.com"


def test_connect_base_url_rejects_garbage():
    with pytest.raises(ConnectError):
        cc.connect_base_url("not-a-url")


def test_safe_name_passes_legitimate_names():
    for name in ("atlassian", "github", "ms-graph", "databricks", "foo_bar.v2"):
        assert cc._safe_name(name) == name


@pytest.mark.parametrize("evil,expected", [
    ("../../evil", ".._.._evil"),
    ("a/b", "a_b"),
    ("x?y=1", "x_y_1"),
    ("host@evil.com", "host_evil.com"),
    ("a b", "a_b"),
])
def test_safe_name_neutralizes_url_control_chars(evil, expected):
    safe = cc._safe_name(evil)
    assert safe == expected
    for ch in "/?@: ":
        assert ch not in safe


@pytest.mark.asyncio
async def test_malicious_name_cannot_escape_path(fake_http):
    """A name with path-traversal/host chars stays a single sanitized segment."""
    fake_http["handler"] = lambda *a, **k: FakeResp(
        {"ticket": "t", "connect_url": "http://localhost:8000/connect/x?ticket=t"})
    await cc.mint_connect_ticket(MCP_URL, "../@evil.com/x", "JWT", "http://localhost:8000/connections")
    url = fake_http["calls"][0]["url"]
    # Host is unchanged; the name became one inert path segment.
    assert url.startswith("http://localhost:18003/connect/")
    assert "evil.com" not in url.split("/connect/")[0]
    assert "@" not in url and "?" not in url


# --- mint ticket ----------------------------------------------------------

@pytest.mark.asyncio
async def test_mint_ticket_posts_and_returns_connect_url(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(
        {"ticket": "t", "connect_url": "http://localhost:8000/connect/atlassian?ticket=t"})
    out = await cc.mint_connect_ticket(MCP_URL, "atlassian", "JWT123", "http://localhost:8000/connections")

    assert out == "http://localhost:8000/connect/atlassian?ticket=t"
    call = fake_http["calls"][0]
    assert call["url"] == "http://localhost:18003/connect/atlassian/ticket"
    assert call["json"] == {"return_url": "http://localhost:8000/connections"}
    assert call["headers"]["Authorization"] == "Bearer JWT123"


@pytest.mark.asyncio
async def test_mint_ticket_requires_jwt(fake_http):
    with pytest.raises(ConnectError):
        await cc.mint_connect_ticket(MCP_URL, "atlassian", "", "http://x/connections")


@pytest.mark.asyncio
async def test_mint_ticket_missing_connect_url_raises(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp({"ticket": "t"})
    with pytest.raises(ConnectError):
        await cc.mint_connect_ticket(MCP_URL, "atlassian", "JWT", "http://x/connections")


# --- status ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_returns_payload(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp({"connected": True, "valid": True, "scopes": "s"})
    out = await cc.get_connect_status(MCP_URL, "atlassian", "JWT")
    assert out == {"connected": True, "valid": True, "scopes": "s"}


@pytest.mark.asyncio
async def test_status_404_means_no_connect_surface(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(status_code=404)
    assert await cc.get_connect_status(MCP_URL, "weather", "JWT") is None


@pytest.mark.asyncio
async def test_status_other_error_raises(fake_http):
    def boom(*a, **k):
        raise httpx.ConnectError("down")
    fake_http["handler"] = boom
    with pytest.raises(ConnectError):
        await cc.get_connect_status(MCP_URL, "atlassian", "JWT")


# --- status (safe wrapper) --------------------------------------------------

@pytest.mark.asyncio
async def test_status_safe_normalizes_expires_at_to_iso(fake_http):
    # bond-mcps reports epoch seconds; the safe wrapper converts to ISO-8601
    # (the shape the REST models / Flutter expect).
    fake_http["handler"] = lambda *a, **k: FakeResp(
        {"connected": True, "valid": True, "scopes": "s",
         "expires_at": 1750000000.0, "has_refresh_token": True}
    )
    out = await cc.get_connect_status_safe(MCP_URL, "atlassian", "JWT")
    assert out["connected"] is True
    assert out["expires_at"] == "2025-06-15T15:06:40+00:00"
    assert out["has_refresh_token"] is True


@pytest.mark.asyncio
async def test_status_safe_none_expiry_stays_none(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(
        {"connected": True, "valid": True, "scopes": None,
         "expires_at": None, "has_refresh_token": False}
    )
    out = await cc.get_connect_status_safe(MCP_URL, "atlassian", "JWT")
    assert out["expires_at"] is None


@pytest.mark.asyncio
async def test_status_safe_404_passthrough(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(status_code=404)
    assert await cc.get_connect_status_safe(MCP_URL, "weather", "JWT") is None


@pytest.mark.asyncio
async def test_status_safe_error_reads_disconnected(fake_http):
    def boom(*a, **k):
        raise httpx.ConnectError("down")
    fake_http["handler"] = boom
    out = await cc.get_connect_status_safe(MCP_URL, "atlassian", "JWT")
    assert out["connected"] is False
    assert out["valid"] is False
    assert "error" in out


# --- disconnect -----------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_returns_flag(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp({"disconnected": True})
    assert await cc.delete_connection(MCP_URL, "atlassian", "JWT") is True


@pytest.mark.asyncio
async def test_delete_404_returns_false(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(status_code=404, content=b"")
    assert await cc.delete_connection(MCP_URL, "atlassian", "JWT") is False
