"""
Tests for MCP action group creation with OAuth authentication support.

This module tests the fix for the issue where MCP tools were not being
registered as Bedrock action groups because _get_mcp_tool_definitions()
was not using OAuth authentication when fetching tool definitions.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone

# Test fixtures and constants
MOCK_USER_ID = "test-user-123"
MOCK_SERVER_NAME = "atlassian"
MOCK_SERVER_URL = "https://mcp.atlassian.com/v1/sse"


class TestGetMcpToolDefinitions:
    """Tests for _get_mcp_tool_definitions with OAuth support."""

    @pytest.fixture
    def mock_mcp_config(self):
        """Create a mock MCP configuration."""
        return {
            "mcpServers": {
                "atlassian": {
                    "url": MOCK_SERVER_URL,
                    "auth_type": "oauth2",
                    "transport": "sse",
                    "oauth_config": {
                        "client_id": "test-client-id",
                        "authorize_url": "https://mcp.atlassian.com/v1/authorize",
                        "token_url": "https://cf.mcp.atlassian.com/v1/token"
                    }
                }
            }
        }

    @pytest.fixture
    def mock_tool(self):
        """Create a mock MCP tool."""
        tool = Mock()
        tool.name = "getJiraIssue"
        tool.description = "Get a Jira issue by key"
        tool.inputSchema = {
            "type": "object",
            "properties": {
                "issueKey": {"type": "string", "description": "The Jira issue key"}
            },
            "required": ["issueKey"]
        }
        return tool

    @pytest.mark.asyncio
    async def test_get_tool_definitions_with_oauth_user_id(self, mock_mcp_config, mock_tool):
        """Test that tool definitions are fetched with OAuth when user_id is provided."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        mock_token_data = Mock()
        mock_token_data.access_token = "test-access-token-12345"
        mock_token_data.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.SSETransport') as mock_transport_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            # Setup mock token cache
            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "atlassian": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token_data
            mock_cache.return_value = cache_instance

            # Setup mock client to return tools
            mock_client = AsyncMock()
            mock_client.list_tools = AsyncMock(return_value=[mock_tool])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Call the function with user_id
            result = await _get_mcp_tool_definitions(
                mock_mcp_config,
                ["getJiraIssue"],
                user_id=MOCK_USER_ID
            )

            # Verify SSETransport was created with auth headers
            mock_transport_class.assert_called_once()
            call_args = mock_transport_class.call_args
            headers = call_args.kwargs.get('headers', {})

            # Should have Authorization header with Bearer token
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'Bearer test-access-token-12345'
            assert headers.get('User-Agent') == 'Bond-AI-MCP-Client/1.0'

            # Verify tool definitions returned
            assert len(result) == 1
            assert result[0]['name'] == 'getJiraIssue'
            assert result[0]['description'] == 'Get a Jira issue by key'
            assert 'issueKey' in result[0]['parameters']

    @pytest.mark.asyncio
    async def test_get_tool_definitions_without_user_id_falls_back_to_static(self, mock_mcp_config, mock_tool):
        """Test that tool definitions fall back to static headers when no user_id."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

        with patch('bondable.bond.providers.bedrock.BedrockMCP.SSETransport') as mock_transport_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            # Setup mock client
            mock_client = AsyncMock()
            mock_client.list_tools = AsyncMock(return_value=[mock_tool])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Call without user_id
            result = await _get_mcp_tool_definitions(
                mock_mcp_config,
                ["getJiraIssue"],
                user_id=None  # No user ID
            )

            # Should still have User-Agent but no Authorization
            mock_transport_class.assert_called_once()
            call_args = mock_transport_class.call_args
            headers = call_args.kwargs.get('headers', {})

            assert headers.get('User-Agent') == 'Bond-AI-MCP-Client/1.0'
            # Without user_id, oauth2 servers won't have auth - falls back to static

    @pytest.mark.asyncio
    async def test_get_tool_definitions_handles_oauth_not_authorized(self, mock_mcp_config, mock_tool):
        """Test graceful handling when user hasn't authorized OAuth."""
        from bondable.bond.providers.bedrock.BedrockMCP import (
            _get_mcp_tool_definitions,
            AuthorizationRequiredError
        )

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.SSETransport') as mock_transport_class, \
             patch('bondable.bond.providers.bedrock.BedrockMCP.Client') as mock_client_class:

            # Setup mock token cache to raise AuthorizationRequiredError
            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {}  # No connections
            cache_instance.get_token.return_value = None
            mock_cache.return_value = cache_instance

            # Setup mock client
            mock_client = AsyncMock()
            mock_client.list_tools = AsyncMock(return_value=[mock_tool])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Call with user_id but no token
            result = await _get_mcp_tool_definitions(
                mock_mcp_config,
                ["getJiraIssue"],
                user_id=MOCK_USER_ID
            )

            # Should fall back gracefully and still try to get tools
            # (with static headers only)
            assert mock_transport_class.called


class TestCreateMcpActionGroups:
    """Tests for create_mcp_action_groups with OAuth support."""

    @pytest.fixture
    def mock_mcp_config(self):
        """Create a mock MCP configuration."""
        return {
            "mcpServers": {
                "atlassian": {
                    "url": MOCK_SERVER_URL,
                    "auth_type": "oauth2",
                    "transport": "sse"
                }
            }
        }

    def test_create_action_groups_passes_user_id(self, mock_mcp_config):
        """Test that create_mcp_action_groups passes user_id to tool definitions."""
        from bondable.bond.providers.bedrock.BedrockMCP import create_mcp_action_groups

        mock_tool_defs = [
            {
                'name': 'getJiraIssue',
                'description': 'Get a Jira issue',
                'parameters': {'issueKey': {'type': 'string'}}
            }
        ]

        with patch('bondable.bond.providers.bedrock.BedrockMCP.Config') as mock_config, \
             patch('bondable.bond.providers.bedrock.BedrockMCP._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockMCP._get_mcp_tool_definitions_sync') as mock_get_defs:

            # Setup mocks
            mock_config.config.return_value.get_mcp_config.return_value = mock_mcp_config
            mock_get_defs.return_value = mock_tool_defs
            mock_bedrock = Mock()
            mock_bedrock.create_agent_action_group.return_value = {
                'agentActionGroup': {'actionGroupId': 'test-action-group-id'}
            }
            mock_client.return_value = mock_bedrock

            # Call with user_id
            create_mcp_action_groups(
                bedrock_agent_id="test-agent-id",
                mcp_tools=["getJiraIssue"],
                mcp_resources=[],
                user_id=MOCK_USER_ID
            )

            # Verify user_id was passed to _get_mcp_tool_definitions_sync
            mock_get_defs.assert_called_once()
            call_kwargs = mock_get_defs.call_args.kwargs
            assert call_kwargs.get('user_id') == MOCK_USER_ID

    def test_create_action_groups_creates_openapi_spec(self, mock_mcp_config):
        """Test that action groups are created with proper OpenAPI spec."""
        from bondable.bond.providers.bedrock.BedrockMCP import create_mcp_action_groups
        import json

        mock_tool_defs = [
            {
                'name': 'getJiraIssue',
                'description': 'Get a Jira issue by key',
                'parameters': {
                    'issueKey': {'type': 'string', 'description': 'Issue key'}
                }
            }
        ]

        with patch('bondable.bond.providers.bedrock.BedrockMCP.Config') as mock_config, \
             patch('bondable.bond.providers.bedrock.BedrockMCP._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockMCP._get_mcp_tool_definitions_sync') as mock_get_defs:

            mock_config.config.return_value.get_mcp_config.return_value = mock_mcp_config
            mock_get_defs.return_value = mock_tool_defs
            mock_bedrock = Mock()
            mock_bedrock.create_agent_action_group.return_value = {
                'agentActionGroup': {'actionGroupId': 'test-action-group-id'}
            }
            mock_client.return_value = mock_bedrock

            create_mcp_action_groups(
                bedrock_agent_id="test-agent-id",
                mcp_tools=["getJiraIssue"],
                mcp_resources=[],
                user_id=MOCK_USER_ID
            )

            # Verify the action group was created with correct structure
            mock_bedrock.create_agent_action_group.assert_called_once()
            call_kwargs = mock_bedrock.create_agent_action_group.call_args.kwargs

            assert call_kwargs['actionGroupName'] == 'MCPTools'
            assert call_kwargs['actionGroupExecutor'] == {'customControl': 'RETURN_CONTROL'}

            # Parse and verify the OpenAPI schema
            api_schema = json.loads(call_kwargs['apiSchema']['payload'])
            assert api_schema['openapi'] == '3.0.0'
            assert '/_bond_mcp_tool_getJiraIssue' in api_schema['paths']

            tool_path = api_schema['paths']['/_bond_mcp_tool_getJiraIssue']['post']
            assert tool_path['description'] == 'Get a Jira issue by key'

    def test_create_action_groups_no_tools_returns_early(self):
        """Test that empty mcp_tools list returns early without errors."""
        from bondable.bond.providers.bedrock.BedrockMCP import create_mcp_action_groups

        with patch('bondable.bond.providers.bedrock.BedrockMCP._get_bedrock_agent_client') as mock_client:
            # Call with empty tools
            create_mcp_action_groups(
                bedrock_agent_id="test-agent-id",
                mcp_tools=[],  # Empty
                mcp_resources=[],
                user_id=MOCK_USER_ID
            )

            # Should not have called the Bedrock client
            mock_client.assert_not_called()


class TestBedrockCRUDWithMCP:
    """Tests for BedrockCRUD functions passing user_id for MCP."""

    def test_create_bedrock_agent_passes_user_id_to_mcp(self):
        """Test that create_bedrock_agent passes owner_user_id to create_mcp_action_groups."""
        from bondable.bond.providers.bedrock.BedrockCRUD import create_bedrock_agent
        from bondable.bond.definition import AgentDefinition

        agent_def = AgentDefinition(
            name="Test Agent",
            description="Test description",
            instructions="Test instructions",
            model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            user_id=MOCK_USER_ID,
            mcp_tools=["getJiraIssue"],
            mcp_resources=[]
        )

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD.create_mcp_action_groups') as mock_mcp, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': 'arn:aws:iam::123456789:role/test'}):

            # Setup mock Bedrock client
            mock_bedrock = Mock()
            mock_bedrock.create_agent.return_value = {
                'agent': {'agentId': 'test-agent-id', 'agentStatus': 'PREPARED'}
            }
            mock_bedrock.prepare_agent.return_value = {}
            mock_bedrock.create_agent_action_group.return_value = {
                'agentActionGroup': {'actionGroupId': 'code-interpreter-id'}
            }
            mock_bedrock.create_agent_alias.return_value = {
                'agentAlias': {'agentAliasId': 'test-alias-id'}
            }
            mock_client.return_value = mock_bedrock

            # Call with owner_user_id
            create_bedrock_agent(
                agent_id="test-bond-agent-id",
                agent_def=agent_def,
                owner_user_id=MOCK_USER_ID
            )

            # Verify create_mcp_action_groups was called with user_id
            mock_mcp.assert_called_once()
            call_kwargs = mock_mcp.call_args.kwargs
            assert call_kwargs.get('user_id') == MOCK_USER_ID

    def test_update_bedrock_agent_passes_user_id_to_mcp(self):
        """Test that update_bedrock_agent passes owner_user_id to create_mcp_action_groups."""
        from bondable.bond.providers.bedrock.BedrockCRUD import update_bedrock_agent
        from bondable.bond.definition import AgentDefinition

        # Create agent_def without id to avoid vector store lookup
        agent_def = AgentDefinition(
            name="Test Agent Updated",
            description="Updated description",
            instructions="Updated instructions",
            model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            user_id=MOCK_USER_ID,
            mcp_tools=["getJiraIssue", "searchJira"],
            mcp_resources=[]
        )
        # Set id manually after creation to bypass vector store logic
        agent_def.id = "test-bond-agent-id"

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD.create_mcp_action_groups') as mock_mcp, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': 'arn:aws:iam::123456789:role/test'}):

            # Setup mock Bedrock client
            mock_bedrock = Mock()
            mock_bedrock.update_agent.return_value = {'agent': {'agentStatus': 'PREPARED'}}
            mock_bedrock.prepare_agent.return_value = {}
            mock_bedrock.list_agent_action_groups.return_value = {
                'actionGroupSummaries': []  # No existing MCP action group
            }
            mock_bedrock.get_agent_alias.return_value = {
                'agentAlias': {'agentAliasName': 'test-alias', 'agentAliasStatus': 'PREPARED'}
            }
            mock_bedrock.update_agent_alias.return_value = {}
            mock_client.return_value = mock_bedrock

            # Call with owner_user_id
            update_bedrock_agent(
                agent_def=agent_def,
                bedrock_agent_id="bedrock-agent-id",
                bedrock_agent_alias_id="bedrock-alias-id",
                owner_user_id=MOCK_USER_ID
            )

            # Verify create_mcp_action_groups was called with user_id
            mock_mcp.assert_called_once()
            call_kwargs = mock_mcp.call_args.kwargs
            assert call_kwargs.get('user_id') == MOCK_USER_ID


class TestAuthHeaderGeneration:
    """Tests for authentication header generation in MCP tool execution."""

    def test_oauth_headers_use_bearer_capitalized(self):
        """Test that OAuth headers use 'Bearer' (capitalized) per RFC 6750."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server
        from bondable.bond.auth.mcp_token_cache import MCPTokenData

        mock_token = MCPTokenData(
            access_token="test-token-12345",
            token_type="bearer",  # lowercase from mcp-remote
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="openid profile email"
        )

        mock_user = Mock()
        mock_user.user_id = MOCK_USER_ID
        mock_user.email = "test@example.com"

        server_config = {
            "url": MOCK_SERVER_URL,
            "auth_type": "oauth2"
        }

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache') as mock_cache:

            cache_instance = Mock()
            cache_instance.get_user_connections.return_value = {
                "atlassian": {"connected": True, "valid": True}
            }
            cache_instance.get_token.return_value = mock_token
            mock_cache.return_value = cache_instance

            headers = _get_auth_headers_for_server(
                server_name="atlassian",
                server_config=server_config,
                current_user=mock_user
            )

            # Should use capitalized "Bearer" regardless of token_type value
            assert headers['Authorization'] == 'Bearer test-token-12345'
            assert not headers['Authorization'].startswith('bearer ')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
