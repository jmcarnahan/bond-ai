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


# --- disconnect -----------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_returns_flag(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp({"disconnected": True})
    assert await cc.delete_connection(MCP_URL, "atlassian", "JWT") is True


@pytest.mark.asyncio
async def test_delete_404_returns_false(fake_http):
    fake_http["handler"] = lambda *a, **k: FakeResp(status_code=404, content=b"")
    assert await cc.delete_connection(MCP_URL, "atlassian", "JWT") is False
