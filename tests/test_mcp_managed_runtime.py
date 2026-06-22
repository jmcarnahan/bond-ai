"""Runtime tests for executing tools on bond-mcps-managed (bond_jwt) MCPs.

Covers: the Bond JWT is forwarded as the Bearer token to a discovered server,
and a MissingProviderConnection-shaped tool error (carrying a /connect URL) is
surfaced as a structured authorization_required response with the connect_url.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bondable.bond.providers.bedrock.BedrockMCP import (
    _extract_connect_url,
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
