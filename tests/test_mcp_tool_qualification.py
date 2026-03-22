"""
Tests for MCP tool qualification (server_name:tool_name format).

Tests the fix for the bug where tools with the same name on different MCP
servers get mapped to the wrong server when an agent is loaded for editing.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestParseQualifiedToolName:
    """Tests for parse_qualified_tool_name helper."""

    def test_qualified_name(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name("microsoft:get_user_profile")
        assert server == "microsoft"
        assert tool == "get_user_profile"

    def test_bare_name_backward_compat(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name("get_user_profile")
        assert server is None
        assert tool == "get_user_profile"

    def test_split_on_first_colon_only(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name("server:tool:with:colons")
        assert server == "server"
        assert tool == "tool:with:colons"

    def test_empty_string(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name("")
        assert server is None
        assert tool == ""

    def test_colon_at_start(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name(":tool_name")
        assert server == ""
        assert tool == "tool_name"

    def test_colon_at_end(self):
        from bondable.bond.providers.bedrock.BedrockMCP import parse_qualified_tool_name
        server, tool = parse_qualified_tool_name("server:")
        assert server == "server"
        assert tool == ""


class TestQualifyToolName:
    """Tests for qualify_tool_name helper."""

    def test_basic_qualification(self):
        from bondable.bond.providers.bedrock.BedrockMCP import qualify_tool_name
        result = qualify_tool_name("microsoft", "get_user_profile")
        assert result == "microsoft:get_user_profile"

    def test_roundtrip(self):
        from bondable.bond.providers.bedrock.BedrockMCP import qualify_tool_name, parse_qualified_tool_name
        qualified = qualify_tool_name("my_server", "my_tool")
        server, tool = parse_qualified_tool_name(qualified)
        assert server == "my_server"
        assert tool == "my_tool"


class TestGetMcpToolDefinitionsQualified:
    """Tests for _get_mcp_tool_definitions with qualified tool names."""

    @pytest.fixture
    def two_server_config(self):
        """Config with two servers that both have a tool named 'get_user_profile'."""
        return {
            "mcpServers": {
                "my_client": {
                    "url": "http://127.0.0.1:5555/mcp",
                    "transport": "streamable-http",
                },
                "microsoft": {
                    "url": "http://localhost:5557/mcp",
                    "auth_type": "oauth2",
                    "transport": "streamable-http",
                    "oauth_config": {
                        "client_id": "test-client",
                        "token_url": "https://login.microsoftonline.com/token",
                    }
                }
            }
        }

    def _make_mock_tool(self, name, description="A test tool"):
        tool = Mock()
        tool.name = name
        tool.description = description
        tool.inputSchema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        return tool

    def _setup_client_mock(self, mock_client_class, tools_by_server):
        """
        Setup mock MCP clients that return different tools per server URL.
        tools_by_server: dict mapping server URL to list of Mock tools.
        """
        call_count = [0]
        server_urls = list(tools_by_server.keys())

        async def mock_aenter(self_client):
            url = server_urls[call_count[0]] if call_count[0] < len(server_urls) else server_urls[-1]
            self_client._url = url
            self_client.list_tools = AsyncMock(return_value=tools_by_server.get(url, []))
            call_count[0] += 1
            return self_client

        mock_client = AsyncMock()
        mock_client.__aenter__ = lambda self: mock_aenter(self)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

    @pytest.mark.asyncio
    async def test_qualified_routes_to_correct_server(self, two_server_config):
        """Qualified name 'microsoft:get_user_profile' routes to microsoft, not my_client."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile", "My Client profile")
        microsoft_tool = self._make_mock_tool("get_user_profile", "Microsoft profile")

        mock_token_data = Mock()
        mock_token_data.access_token = "test-token"

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache:

            # Setup token cache for OAuth server
            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "microsoft": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token_data
            mock_cache.return_value = cache_instance

            # Track which servers are queried
            servers_queried = []

            async def mock_aenter(client_self):
                servers_queried.append(len(servers_queried))
                # First call = my_client, second = microsoft (dict iteration order)
                if len(servers_queried) == 1:
                    client_self.list_tools = AsyncMock(return_value=[my_client_tool])
                else:
                    client_self.list_tools = AsyncMock(return_value=[microsoft_tool])
                return client_self

            mock_client = AsyncMock()
            mock_client.__aenter__ = lambda self: mock_aenter(self)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Request the microsoft-qualified tool
            result = await _get_mcp_tool_definitions(
                two_server_config,
                ["microsoft:get_user_profile"],
                user_id="test-user"
            )

            assert len(result) == 1
            assert result[0]['name'] == 'get_user_profile'
            assert result[0]['server_name'] == 'microsoft'

    @pytest.mark.asyncio
    async def test_qualified_routes_to_my_client(self, two_server_config):
        """Qualified name 'my_client:get_user_profile' routes to my_client."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile", "My Client profile")

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.list_tools = AsyncMock(return_value=[my_client_tool])
            mock_client_class.return_value = mock_client

            result = await _get_mcp_tool_definitions(
                two_server_config,
                ["my_client:get_user_profile"]
            )

            assert len(result) == 1
            assert result[0]['name'] == 'get_user_profile'
            assert result[0]['server_name'] == 'my_client'

    @pytest.mark.asyncio
    async def test_bare_name_backward_compat_first_match(self, two_server_config):
        """Bare name 'get_user_profile' matches first server (backward compat)."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile", "My Client profile")

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.list_tools = AsyncMock(return_value=[my_client_tool])
            mock_client_class.return_value = mock_client

            result = await _get_mcp_tool_definitions(
                two_server_config,
                ["get_user_profile"]  # bare name
            )

            assert len(result) == 1
            assert result[0]['name'] == 'get_user_profile'
            # First server in iteration is my_client
            assert result[0]['server_name'] == 'my_client'

    @pytest.mark.asyncio
    async def test_mixed_qualified_and_bare_names(self, two_server_config):
        """Mix of qualified and bare names resolves correctly."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tools = [
            self._make_mock_tool("get_user_profile", "My Client profile"),
            self._make_mock_tool("list_files", "List files"),
        ]
        microsoft_tools = [
            self._make_mock_tool("get_user_profile", "Microsoft profile"),
            self._make_mock_tool("read_emails", "Read emails"),
        ]

        mock_token_data = Mock()
        mock_token_data.access_token = "test-token"

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache:

            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "microsoft": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token_data
            mock_cache.return_value = cache_instance

            call_count = [0]

            async def mock_aenter(client_self):
                if call_count[0] == 0:
                    client_self.list_tools = AsyncMock(return_value=my_client_tools)
                else:
                    client_self.list_tools = AsyncMock(return_value=microsoft_tools)
                call_count[0] += 1
                return client_self

            mock_client = AsyncMock()
            mock_client.__aenter__ = lambda self: mock_aenter(self)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _get_mcp_tool_definitions(
                two_server_config,
                [
                    "microsoft:get_user_profile",  # Qualified: must go to microsoft
                    "list_files",                   # Bare: first match (my_client)
                ],
                user_id="test-user"
            )

            result_map = {(r['name'], r['server_name']): r for r in result}
            assert len(result) == 2
            assert ('get_user_profile', 'microsoft') in result_map
            assert ('list_files', 'my_client') in result_map

    @pytest.mark.asyncio
    async def test_nonexistent_server_qualified_name(self, two_server_config):
        """Qualified name with nonexistent server doesn't match any server."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile")

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.list_tools = AsyncMock(return_value=[my_client_tool])
            mock_client_class.return_value = mock_client

            result = await _get_mcp_tool_definitions(
                two_server_config,
                ["nonexistent_server:get_user_profile"]
            )

            # Tool should NOT be found since it's targeted to a server that doesn't exist
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_qualified_admin_tool(self):
        """Qualified admin tool name resolves correctly."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions
        from bondable.bond.providers.bedrock.AdminMCP import ADMIN_SERVER_NAME, ADMIN_TOOL_NAMES

        if not ADMIN_TOOL_NAMES:
            pytest.skip("No admin tools defined")

        admin_tool_name = next(iter(ADMIN_TOOL_NAMES))
        # Need at least one server in config to avoid early return
        config = {"mcpServers": {"dummy": {"url": "http://localhost:9999/mcp"}}}

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_admin_tool_definitions') as mock_admin_defs:
            mock_admin_defs.return_value = [{
                'name': admin_tool_name,
                'description': 'Test admin tool',
                'inputSchema': {'type': 'object', 'properties': {}, 'required': []}
            }]

            # Qualified with admin server name
            result = await _get_mcp_tool_definitions(
                config,
                [f"{ADMIN_SERVER_NAME}:{admin_tool_name}"]
            )

            assert len(result) == 1
            assert result[0]['name'] == admin_tool_name
            assert result[0]['server_name'] == ADMIN_SERVER_NAME

    @pytest.mark.asyncio
    async def test_bare_admin_tool_backward_compat(self):
        """Bare admin tool name still works (backward compat)."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions
        from bondable.bond.providers.bedrock.AdminMCP import ADMIN_SERVER_NAME, ADMIN_TOOL_NAMES

        if not ADMIN_TOOL_NAMES:
            pytest.skip("No admin tools defined")

        admin_tool_name = next(iter(ADMIN_TOOL_NAMES))
        # Need at least one server in config to avoid early return
        config = {"mcpServers": {"dummy": {"url": "http://localhost:9999/mcp"}}}

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_admin_tool_definitions') as mock_admin_defs:
            mock_admin_defs.return_value = [{
                'name': admin_tool_name,
                'description': 'Test admin tool',
                'inputSchema': {'type': 'object', 'properties': {}, 'required': []}
            }]

            result = await _get_mcp_tool_definitions(
                config,
                [admin_tool_name]  # bare name
            )

            assert len(result) == 1
            assert result[0]['name'] == admin_tool_name
            assert result[0]['server_name'] == ADMIN_SERVER_NAME

    @pytest.mark.asyncio
    async def test_empty_tool_list(self):
        """Empty tool list returns empty results."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        config = {"mcpServers": {"test": {"url": "http://localhost:5555/mcp"}}}
        result = await _get_mcp_tool_definitions(config, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_qualified_same_tool_different_servers(self, two_server_config):
        """Can select the same tool name from two different servers simultaneously."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile", "My Client profile")
        microsoft_tool = self._make_mock_tool("get_user_profile", "Microsoft profile")

        mock_token_data = Mock()
        mock_token_data.access_token = "test-token"

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache:

            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "microsoft": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token_data
            mock_cache.return_value = cache_instance

            call_count = [0]

            async def mock_aenter(client_self):
                if call_count[0] == 0:
                    client_self.list_tools = AsyncMock(return_value=[my_client_tool])
                else:
                    client_self.list_tools = AsyncMock(return_value=[microsoft_tool])
                call_count[0] += 1
                return client_self

            mock_client = AsyncMock()
            mock_client.__aenter__ = lambda self: mock_aenter(self)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Select the same tool from BOTH servers
            result = await _get_mcp_tool_definitions(
                two_server_config,
                [
                    "my_client:get_user_profile",
                    "microsoft:get_user_profile",
                ],
                user_id="test-user"
            )

            assert len(result) == 2
            servers = {r['server_name'] for r in result}
            assert servers == {'my_client', 'microsoft'}

    @pytest.mark.asyncio
    async def test_mixed_qualified_and_bare_same_tool_no_duplicates(self, two_server_config):
        """Mixed qualified + bare name for same tool should NOT produce duplicates."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        my_client_tool = self._make_mock_tool("get_user_profile", "My Client profile")
        microsoft_tool = self._make_mock_tool("get_user_profile", "Microsoft profile")

        mock_token_data = Mock()
        mock_token_data.access_token = "test-token"

        with patch('bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport'), \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache:

            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "microsoft": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token_data
            mock_cache.return_value = cache_instance

            call_count = [0]

            async def mock_aenter(client_self):
                if call_count[0] == 0:
                    client_self.list_tools = AsyncMock(return_value=[my_client_tool])
                else:
                    client_self.list_tools = AsyncMock(return_value=[microsoft_tool])
                call_count[0] += 1
                return client_self

            mock_client = AsyncMock()
            mock_client.__aenter__ = lambda self: mock_aenter(self)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Mixed: qualified + bare for the same tool name
            # Should only produce ONE result (qualified wins, bare is deduplicated)
            result = await _get_mcp_tool_definitions(
                two_server_config,
                [
                    "microsoft:get_user_profile",
                    "get_user_profile",  # bare name - should be deduplicated
                ],
                user_id="test-user"
            )

            # Should be exactly 1 result (microsoft), not 2
            assert len(result) == 1
            assert result[0]['server_name'] == 'microsoft'
