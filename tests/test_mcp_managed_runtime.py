"""Runtime tests for executing tools on bond-mcps-managed (bond_jwt) MCPs.

Covers: the Bond JWT is forwarded as the Bearer token to a discovered server;
a MissingProviderConnection-shaped tool error (carrying a /connect URL) is
surfaced as a structured authorization_required response with the connect_url;
the server-side mint fallback (no forwarded JWT) asserts a real identity with
a narrow audience and short expiry; and /mcp/tools' managed-status delegation
maps bond-mcps' status shape correctly.
"""

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-managed-runtime")

import jwt as pyjwt
import pytest

from bondable.bond.providers.bedrock.BedrockMCP import (
    _extract_connect_url,
    _get_auth_headers_for_server,
    execute_mcp_tool,
)


MANAGED_CONFIG = {
    "mcpServers": {
        "atlassian": {
            "url": "http://localhost:18003/mcp",
            "transport": "streamable-http",
            "auth_type": "bond_jwt",
        }
    }
}


def _mock_tool(name):
    t = Mock()
    t.name = name
    t.inputSchema = {}
    return t


def test_extract_connect_url():
    msg = ("atlassian is not connected for the current user. Open "
           "http://localhost:8000/connect/atlassian?ticket=abc in a browser to authorize.")
    assert _extract_connect_url(msg) == "http://localhost:8000/connect/atlassian?ticket=abc"
    assert _extract_connect_url("boom") is None
    assert _extract_connect_url("") is None


@pytest.mark.asyncio
async def test_bond_jwt_forwarded_to_managed_server():
    """The user's Bond JWT becomes the Bearer token for a bond_jwt server."""
    result_obj = Mock()
    result_obj.content = [Mock(text="ok")]

    with patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport") as transport_cls, \
         patch("bondable.bond.providers.bedrock.BedrockMCP.Client") as client_cls:
        client = AsyncMock()
        client.list_tools = AsyncMock(return_value=[_mock_tool("getJiraIssue")])
        client.call_tool = AsyncMock(return_value=result_obj)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        out = await execute_mcp_tool(
            MANAGED_CONFIG, "getJiraIssue", {"issueKey": "X-1"},
            current_user=Mock(user_id="u-1"), jwt_token="BONDJWT", target_server="atlassian",
        )

    assert out["success"] is True
    headers = transport_cls.call_args.kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer BONDJWT"


@pytest.mark.asyncio
async def test_missing_connection_surfaces_connect_url():
    """A tool error carrying a /connect URL becomes a structured response."""
    with patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport"), \
         patch("bondable.bond.providers.bedrock.BedrockMCP.Client") as client_cls:
        client = AsyncMock()
        client.list_tools = AsyncMock(return_value=[_mock_tool("getJiraIssue")])
        client.call_tool = AsyncMock(side_effect=Exception(
            "atlassian is not connected. Open "
            "http://localhost:8000/connect/atlassian?ticket=TKT in a browser to authorize."
        ))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        out = await execute_mcp_tool(
            MANAGED_CONFIG, "getJiraIssue", {"issueKey": "X-1"},
            current_user=Mock(user_id="u-1"), jwt_token="BONDJWT", target_server="atlassian",
        )

    assert out["success"] is False
    assert out["authorization_required"] is True
    assert out["connect_url"] == "http://localhost:8000/connect/atlassian?ticket=TKT"
    assert out["server_name"] == "atlassian"


# --- server-side Bond JWT mint (no forwarded request JWT) -------------------

BOND_JWT_SERVER = {
    "url": "http://localhost:18003/mcp",
    "transport": "streamable-http",
    "auth_type": "bond_jwt",
}


def _user(email):
    return SimpleNamespace(user_id="u-1", email=email)


def test_forwarded_jwt_wins_over_mint():
    headers = _get_auth_headers_for_server(
        "atlassian", BOND_JWT_SERVER, current_user=_user("a@example.com"), jwt_token="FORWARDED"
    )
    assert headers["Authorization"] == "Bearer FORWARDED"


def test_mint_asserts_real_identity_with_narrow_scope():
    """Server-side flows mint from the user's real email — and the token must
    be MCP-only (aud excludes bond-ai-api) and short-lived, never a full
    24h bond-ai API session handed to an MCP server."""
    from bondable.rest.utils.auth import jwt_config

    headers = _get_auth_headers_for_server(
        "atlassian", BOND_JWT_SERVER, current_user=_user("a@example.com"), jwt_token=None
    )
    token = headers["Authorization"].removeprefix("Bearer ")
    claims = pyjwt.decode(
        token, jwt_config.JWT_SECRET_KEY, algorithms=["HS256"], audience="mcp-server"
    )
    assert claims["sub"] == "a@example.com"
    assert claims["iss"] == "bond-ai"
    assert claims["aud"] == ["mcp-server"]          # NOT a bond-ai API session
    assert "bond-ai-api" not in claims["aud"]
    lifetime = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert 0 < lifetime <= 6 * 60                    # short-lived (~5 min)


@pytest.mark.parametrize("email", [None, "", "unknown"])
def test_mint_refuses_placeholder_identity(email):
    """A placeholder email must never be signed into a JWT (bond-mcps would
    trust it as a real user_key). No mint -> no Authorization header."""
    headers = _get_auth_headers_for_server(
        "atlassian", BOND_JWT_SERVER, current_user=_user(email), jwt_token=None
    )
    assert "Authorization" not in headers


# --- /mcp/tools managed-status delegation ------------------------------------

from bondable.rest.routers.mcp import _get_managed_connection_status  # noqa: E402


@pytest.mark.asyncio
async def test_managed_status_maps_connected_payload(monkeypatch):
    async def fake_status(url, name, jwt_token, timeout=None):
        return {"connected": True, "valid": True, "scopes": "read",
                "expires_at": 1750000000.0, "has_refresh_token": True}
    monkeypatch.setattr("bondable.bond.mcp_connect_client.get_connect_status", fake_status)

    info = await _get_managed_connection_status("atlassian", BOND_JWT_SERVER, "JWT")
    assert info.connected is True
    assert info.valid is True
    assert info.requires_authorization is False
    assert info.expires_at == "2025-06-15T15:06:40+00:00"  # epoch -> ISO
    assert info.has_refresh_token is True


@pytest.mark.asyncio
async def test_managed_status_disconnected_gates_tools(monkeypatch):
    """Disconnected reads valid=False here: `valid` gates tool selection in
    the agent editor (unlike the Connections screen, where it means
    'not expired')."""
    async def fake_status(url, name, jwt_token, timeout=None):
        return {"connected": False, "valid": True, "scopes": None,
                "expires_at": None, "has_refresh_token": False}
    monkeypatch.setattr("bondable.bond.mcp_connect_client.get_connect_status", fake_status)

    info = await _get_managed_connection_status("atlassian", BOND_JWT_SERVER, "JWT")
    assert info.connected is False
    assert info.valid is False
    assert info.requires_authorization is True


@pytest.mark.asyncio
async def test_managed_status_no_connect_surface_reads_connected(monkeypatch):
    """404 (no connect surface, e.g. PAT-based databricks) -> nothing to
    connect; the server must render as usable. (The Connections screen makes
    the opposite call and omits the tile.)"""
    async def fake_status(url, name, jwt_token, timeout=None):
        return None
    monkeypatch.setattr("bondable.bond.mcp_connect_client.get_connect_status", fake_status)

    info = await _get_managed_connection_status("databricks", BOND_JWT_SERVER, "JWT")
    assert info.connected is True
    assert info.requires_authorization is False


@pytest.mark.asyncio
async def test_managed_status_fails_soft_when_mcps_down(monkeypatch):
    async def boom(url, name, jwt_token, timeout=None):
        raise RuntimeError("bond-mcps unreachable")
    monkeypatch.setattr("bondable.bond.mcp_connect_client.get_connect_status", boom)

    info = await _get_managed_connection_status("atlassian", BOND_JWT_SERVER, "JWT")
    assert info.connected is False
    assert info.requires_authorization is True
