"""
Tests for the allowed_tools filtering feature in MCP server config.

When a server config includes an 'allowed_tools' list, only tools whose
names appear in that list are exposed to users and Bedrock action groups.
Servers without 'allowed_tools' are unaffected (backward compat).
"""

import os
import tempfile
from datetime import timedelta

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set up a minimal test environment before importing the app.
_test_db_file = tempfile.NamedTemporaryFile(suffix='_allowed_tools.db', delete=False)
os.environ.setdefault('METADATA_DB_URL', f"sqlite:///{_test_db_file.name}")
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-allowed-tools')


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MICROSOFT_TOOLS = [
    "get_user_profile",
    "list_emails",
    "read_email",
    "send_email",
    "list_teams",
    "list_chats",
    "read_teams_messages",
    "send_teams_message",
    "get_teams_activity",
    "list_sharepoint_sites",
    "list_files",
    "inspect_file",
    "upload_file",
    "copy_or_rename_file",
]

POWERBI_TOOLS = [
    "list_powerbi_workspaces",
    "list_powerbi_content",
    "query_dataset",
    "refresh_dataset",
    "export_report",
]

ALL_19_TOOLS = MICROSOFT_TOOLS + POWERBI_TOOLS


def _make_mock_tool(name: str):
    """Return a MagicMock that behaves like a fastmcp Tool object."""
    t = MagicMock()
    t.name = name
    t.description = f"Tool {name}"
    t.inputSchema = {"type": "object", "properties": {}}
    return t


# ---------------------------------------------------------------------------
# Tool-split correctness (no code needed, just verifying the constants)
# ---------------------------------------------------------------------------

class TestToolSplitDefinition:
    """Verify the intended microsoft/powerbi split is complete and non-overlapping."""

    def test_all_19_tools_accounted_for(self):
        assert len(MICROSOFT_TOOLS) == 14
        assert len(POWERBI_TOOLS) == 5
        assert len(ALL_19_TOOLS) == 19
        assert len(set(ALL_19_TOOLS)) == 19, "Duplicate tool name in split definition"

    def test_powerbi_tools_not_in_microsoft_set(self):
        ms_set = set(MICROSOFT_TOOLS)
        for tool in POWERBI_TOOLS:
            assert tool not in ms_set, f"{tool} should not be in microsoft allowed_tools"

    def test_microsoft_tools_not_in_powerbi_set(self):
        pbi_set = set(POWERBI_TOOLS)
        for tool in MICROSOFT_TOOLS:
            assert tool not in pbi_set, f"{tool} should not be in powerbi allowed_tools"


# ---------------------------------------------------------------------------
# BedrockMCP._get_mcp_tool_definitions — allowed_tools filtering
# ---------------------------------------------------------------------------

class TestBedrockMCPAllowedToolsFilter:
    """
    Tests that _get_mcp_tool_definitions respects the allowed_tools field
    in server config when building Bedrock action group definitions.
    """

    def _make_mcp_config(self, server_name: str, allowed_tools=None):
        config = {
            "mcpServers": {
                server_name: {
                    "url": "https://fake-mcp.example.com/mcp",
                    "transport": "streamable-http",
                    "auth_type": "bond_jwt",
                }
            }
        }
        if allowed_tools is not None:
            config["mcpServers"][server_name]["allowed_tools"] = allowed_tools
        return config

    def _run_sync(self, coro):
        import asyncio
        # asyncio.get_event_loop() raises in Py3.10+ when no loop exists in the
        # current thread (e.g. after an earlier test closed its loop). Create a
        # fresh loop per test to keep behavior independent of test ordering.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport")
    @patch("bondable.bond.providers.bedrock.BedrockMCP.Client")
    def test_allowed_tools_filters_bedrock_tool_defs(self, mock_client_cls, mock_transport_cls):
        """Only allowed tools should appear in action group definitions."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_transport_cls.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS])
        mock_client_cls.return_value = mock_client

        config = self._make_mcp_config("microsoft", allowed_tools=MICROSOFT_TOOLS)

        result = self._run_sync(
            _get_mcp_tool_definitions(config, ["microsoft:send_email"], user_id=None)
        )

        assert len(result) == 1
        assert result[0]["name"] == "send_email"
        assert result[0]["server_name"] == "microsoft"

    @patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport")
    @patch("bondable.bond.providers.bedrock.BedrockMCP.Client")
    def test_powerbi_tool_blocked_on_microsoft_server(self, mock_client_cls, mock_transport_cls):
        """A powerbi tool requested on the microsoft server should not be found."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_transport_cls.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS])
        mock_client_cls.return_value = mock_client

        config = self._make_mcp_config("microsoft", allowed_tools=MICROSOFT_TOOLS)

        result = self._run_sync(
            _get_mcp_tool_definitions(config, ["microsoft:list_powerbi_workspaces"], user_id=None)
        )

        assert result == [], "powerbi tool must not be accessible via microsoft server"

    @patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport")
    @patch("bondable.bond.providers.bedrock.BedrockMCP.Client")
    def test_no_allowed_tools_returns_all(self, mock_client_cls, mock_transport_cls):
        """Server without allowed_tools should return all tools (backward compat)."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_transport_cls.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS])
        mock_client_cls.return_value = mock_client

        # No allowed_tools key at all
        config = self._make_mcp_config("unfiltered")

        # Request every tool (unqualified, so first-match wins)
        result = self._run_sync(
            _get_mcp_tool_definitions(config, ALL_19_TOOLS, user_id=None)
        )

        returned_names = {r["name"] for r in result}
        assert returned_names == set(ALL_19_TOOLS)

    @patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport")
    @patch("bondable.bond.providers.bedrock.BedrockMCP.Client")
    def test_allowed_tools_empty_list_returns_no_tools(self, mock_client_cls, mock_transport_cls):
        """allowed_tools=[] means no tools are exposed from that server."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_transport_cls.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS])
        mock_client_cls.return_value = mock_client

        config = self._make_mcp_config("microsoft", allowed_tools=[])

        result = self._run_sync(
            _get_mcp_tool_definitions(config, ALL_19_TOOLS, user_id=None)
        )

        assert result == []

    @patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport")
    @patch("bondable.bond.providers.bedrock.BedrockMCP.Client")
    def test_powerbi_server_only_exposes_powerbi_tools(self, mock_client_cls, mock_transport_cls):
        """powerbi server with allowed_tools should only return powerbi tools."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_transport_cls.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS])
        mock_client_cls.return_value = mock_client

        config = self._make_mcp_config("powerbi", allowed_tools=POWERBI_TOOLS)

        result = self._run_sync(
            _get_mcp_tool_definitions(
                config,
                [f"powerbi:{t}" for t in POWERBI_TOOLS],
                user_id=None,
            )
        )

        returned_names = {r["name"] for r in result}
        assert returned_names == set(POWERBI_TOOLS)
        for r in result:
            assert r["server_name"] == "powerbi"


# ---------------------------------------------------------------------------
# REST router /mcp/tools — allowed_tools filtering via FastAPI TestClient
# ---------------------------------------------------------------------------

def _make_mcp_config_for_router(server_name: str, allowed_tools=None):
    """Build a minimal mcpServers config dict for mocking the router."""
    server = {
        "url": "https://fake-mcp.example.com/mcp",
        "transport": "streamable-http",
        "auth_type": "bond_jwt",
        "display_name": server_name.title(),
    }
    if allowed_tools is not None:
        server["allowed_tools"] = allowed_tools
    return {"mcpServers": {server_name: server}}


class TestMCPRouterAllowedToolsFilter:
    """
    Tests the allowed_tools filter in bondable/rest/routers/mcp.py via the
    real FastAPI endpoint.

    The test drives the endpoint through the full auth middleware by using
    create_access_token (same as test_connections_api.py) so the JWT path
    is exercised normally.  Only the MCP I/O layer is mocked.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Fixtures needed once per class."""
        from bondable.rest.main import app, create_access_token
        from fastapi.testclient import TestClient

        token = create_access_token(
            data={
                "sub": "router-test@example.com",
                "user_id": "router-test-user",
                "provider": "okta",
            },
            expires_delta=timedelta(minutes=15),
        )
        self._auth_headers = {"Authorization": f"Bearer {token}"}
        self._client = TestClient(app)

    def _call_tools_endpoint(self, mcp_config: dict):
        """
        Call GET /mcp/tools?grouped=true with a mocked MCP client that
        returns all 19 tools from the server, then let the production filter
        logic narrow the list based on allowed_tools.
        """
        mock_mcp_client = MagicMock()
        mock_mcp_client.mcp_config = mcp_config

        mock_fastmcp_client = AsyncMock()
        mock_fastmcp_client.__aenter__ = AsyncMock(return_value=mock_fastmcp_client)
        mock_fastmcp_client.__aexit__ = AsyncMock(return_value=False)
        mock_fastmcp_client.list_tools = AsyncMock(
            return_value=[_make_mock_tool(n) for n in ALL_19_TOOLS]
        )

        with patch("bondable.bond.mcp_client.MCPClient.client", return_value=mock_mcp_client), \
             patch("bondable.rest.routers.mcp.get_mcp_auth_headers", return_value={}), \
             patch("bondable.rest.routers.mcp.get_mcp_token_cache") as mock_cache, \
             patch("bondable.rest.routers.mcp.Client", return_value=mock_fastmcp_client), \
             patch("bondable.rest.routers.mcp._discover_user_mcp_server_tools",
                   new=AsyncMock(return_value={"servers": [], "tools": []})), \
             patch("bondable.rest.dependencies.auth._is_token_revoked", return_value=False):

            mock_cache.return_value.get_user_connections.return_value = {}

            response = self._client.get(
                "/mcp/tools?grouped=true",
                headers=self._auth_headers,
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        return response.json()

    def test_microsoft_filter_returns_only_graph_tools(self):
        """GET /mcp/tools for a microsoft server with allowed_tools returns only the 14 Graph tools."""
        config = _make_mcp_config_for_router("microsoft", allowed_tools=MICROSOFT_TOOLS)
        data = self._call_tools_endpoint(config)

        ms_server = next((s for s in data["servers"] if s["server_name"] == "microsoft"), None)
        assert ms_server is not None
        tool_names = {t["name"] for t in ms_server["tools"]}
        assert tool_names == set(MICROSOFT_TOOLS)
        assert not tool_names.intersection(POWERBI_TOOLS), "Power BI tools must not appear in microsoft server"

    def test_powerbi_filter_returns_only_powerbi_tools(self):
        """GET /mcp/tools for a powerbi server with allowed_tools returns only the 5 Power BI tools."""
        config = _make_mcp_config_for_router("powerbi", allowed_tools=POWERBI_TOOLS)
        data = self._call_tools_endpoint(config)

        pbi_server = next((s for s in data["servers"] if s["server_name"] == "powerbi"), None)
        assert pbi_server is not None
        tool_names = {t["name"] for t in pbi_server["tools"]}
        assert tool_names == set(POWERBI_TOOLS)
        assert not tool_names.intersection(MICROSOFT_TOOLS), "Graph tools must not appear in powerbi server"

    def test_no_allowed_tools_returns_all(self):
        """Server without allowed_tools exposes all tools (backward compat)."""
        config = _make_mcp_config_for_router("unfiltered")
        data = self._call_tools_endpoint(config)

        server = next((s for s in data["servers"] if s["server_name"] == "unfiltered"), None)
        assert server is not None
        assert {t["name"] for t in server["tools"]} == set(ALL_19_TOOLS)

    def test_empty_allowed_tools_returns_no_tools(self):
        """allowed_tools=[] means no tools are exposed from that server."""
        config = _make_mcp_config_for_router("locked_down", allowed_tools=[])
        data = self._call_tools_endpoint(config)

        server = next((s for s in data["servers"] if s["server_name"] == "locked_down"), None)
        assert server is not None
        assert server["tools"] == []
        assert server["tool_count"] == 0
