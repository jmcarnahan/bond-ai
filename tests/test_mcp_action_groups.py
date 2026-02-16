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
            # Tool paths use /b.{hash6}.{tool_name} format
            matching_paths = [p for p in api_schema['paths'] if 'getJiraIssue' in p]
            assert len(matching_paths) == 1, f"Expected one path with getJiraIssue, got: {list(api_schema['paths'].keys())}"

            tool_path = api_schema['paths'][matching_paths[0]]['post']
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

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD.create_mcp_action_groups') as mock_mcp, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': 'arn:aws:iam::123456789:role/test'}):

            agent_def = AgentDefinition(
                name="Test Agent",
                description="Test description",
                instructions="Test instructions",
                model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                user_id=MOCK_USER_ID,
                mcp_tools=["getJiraIssue"],
                mcp_resources=[]
            )

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

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD.create_mcp_action_groups') as mock_mcp, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': 'arn:aws:iam::123456789:role/test'}):

            # Create agent_def inside patch context to avoid real S3 HeadBucket call
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


class TestSanitizePropertySchema:
    """Tests for _sanitize_property_schema function."""

    def test_simple_string_passes_through(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"type": "string", "description": "A string param"}
        result = _sanitize_property_schema("test", schema)
        assert result == {"type": "string", "description": "A string param"}

    def test_simple_integer_passes_through(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"type": "integer", "description": "A number"}
        result = _sanitize_property_schema("count", schema)
        assert result == {"type": "integer", "description": "A number"}

    def test_simple_boolean_passes_through(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"type": "boolean", "description": "A flag"}
        result = _sanitize_property_schema("flag", schema)
        assert result == {"type": "boolean", "description": "A flag"}

    def test_nullable_string_anyof(self):
        """str | None -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Optional string"
        }
        result = _sanitize_property_schema("name", schema)
        assert result["type"] == "string"
        assert result["description"] == "Optional string"
        assert "anyOf" not in result

    def test_nullable_integer_anyof(self):
        """int | None -> integer"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "description": "Optional int"
        }
        result = _sanitize_property_schema("count", schema)
        assert result["type"] == "integer"
        assert "anyOf" not in result

    def test_nullable_object_anyof(self):
        """dict | None -> string with JSON hint"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "anyOf": [{"type": "object"}, {"type": "null"}],
            "description": "Optional dict"
        }
        result = _sanitize_property_schema("fields", schema)
        assert result["type"] == "string"
        assert result["description"] == "Optional dict"
        assert "anyOf" not in result

    def test_mixed_union_anyof(self):
        """dict[str, Any] | str | None -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "anyOf": [
                {"type": "object", "additionalProperties": {}},
                {"type": "string"},
                {"type": "null"}
            ]
        }
        result = _sanitize_property_schema("additional_fields", schema)
        assert result["type"] == "string"
        assert "anyOf" not in result
        assert "additionalProperties" not in result

    def test_str_int_none_union(self):
        """str | int | None -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "null"}
            ],
            "description": "Page ID"
        }
        result = _sanitize_property_schema("page_id", schema)
        assert result["type"] == "string"
        assert "anyOf" not in result

    def test_object_type_converted_to_string(self):
        """dict[str, Any] -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "type": "object",
            "additionalProperties": {},
            "description": "Issue fields"
        }
        result = _sanitize_property_schema("fields", schema)
        assert result["type"] == "string"
        assert result["description"] == "Issue fields"
        assert "additionalProperties" not in result

    def test_array_of_strings_converted(self):
        """list[str] -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of keys"
        }
        result = _sanitize_property_schema("keys", schema)
        assert result["type"] == "string"
        assert "items" not in result

    def test_array_of_objects_converted(self):
        """list[dict] -> string"""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "type": "array",
            "items": {"type": "object", "properties": {"name": {"type": "string"}}}
        }
        result = _sanitize_property_schema("items", schema)
        assert result["type"] == "string"
        assert "items" not in result

    def test_ref_converted_to_string(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"$ref": "#/definitions/SomeModel"}
        result = _sanitize_property_schema("model", schema)
        assert result["type"] == "string"
        assert "$ref" not in result

    def test_allof_converted_to_string(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {
            "allOf": [{"type": "string"}, {"minLength": 1}],
            "description": "Required string"
        }
        result = _sanitize_property_schema("name", schema)
        assert result["type"] == "string"
        assert "allOf" not in result

    def test_enum_preserved(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"type": "string", "enum": ["open", "closed"], "description": "Status"}
        result = _sanitize_property_schema("status", schema)
        assert result["type"] == "string"
        assert result["enum"] == ["open", "closed"]

    def test_primitive_default_preserved(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        schema = {"type": "integer", "default": 10, "description": "Limit"}
        result = _sanitize_property_schema("limit", schema)
        assert result["default"] == 10

    def test_non_dict_input(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_property_schema
        result = _sanitize_property_schema("bad", "not a dict")
        assert result["type"] == "string"


class TestSanitizeToolParameters:
    """Tests for _sanitize_tool_parameters function."""

    def test_simple_params_pass_through(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "key": {"type": "string", "description": "Issue key"},
            "limit": {"type": "integer", "description": "Max results"}
        }
        sanitized, required = _sanitize_tool_parameters("test_tool", props, ["key"])
        assert len(sanitized) == 2
        assert required == ["key"]

    def test_truncation_preserves_required(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "required1": {"type": "string"},
            "required2": {"type": "string"},
            "optional1": {"type": "string"},
            "optional2": {"type": "string"},
            "optional3": {"type": "string"},
            "optional4": {"type": "string"},
            "optional5": {"type": "string"},
        }
        sanitized, required = _sanitize_tool_parameters(
            "big_tool", props, ["required1", "required2"], max_params=5
        )
        assert len(sanitized) == 5
        assert "required1" in sanitized
        assert "required2" in sanitized
        assert required == ["required1", "required2"]

    def test_no_params_returns_empty(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        sanitized, required = _sanitize_tool_parameters("empty", {}, [])
        assert sanitized == {}
        assert required == []

    def test_complex_params_sanitized(self):
        """Simulate an Atlassian-like tool with complex schemas."""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "issue_key": {"type": "string", "description": "Issue key"},
            "fields": {"type": "object", "additionalProperties": {}, "description": "Fields to update"},
            "visibility": {
                "anyOf": [
                    {"type": "object", "properties": {"type": {"type": "string"}, "value": {"type": "string"}}},
                    {"type": "null"}
                ],
                "description": "Comment visibility"
            },
            "comment": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Optional comment"
            },
        }
        sanitized, required = _sanitize_tool_parameters(
            "update_issue", props, ["issue_key", "fields"]
        )
        # All should be sanitized to basic types
        for prop_name, prop_schema in sanitized.items():
            assert prop_schema["type"] in ("string", "integer", "number", "boolean"), \
                f"Property '{prop_name}' has unsupported type: {prop_schema.get('type')}"
            assert "anyOf" not in prop_schema
            assert "oneOf" not in prop_schema
            assert "additionalProperties" not in prop_schema


class TestSanitizeDescription:
    """Tests for _sanitize_description function."""

    def test_short_description_unchanged(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_description
        assert _sanitize_description("Short desc") == "Short desc"

    def test_long_description_truncated(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_description
        long_desc = "A" * 300
        result = _sanitize_description(long_desc, max_length=200)
        assert len(result) == 200
        assert result.endswith("...")

    def test_empty_description(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_description
        assert _sanitize_description("") == ""

    def test_exact_length_unchanged(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_description
        desc = "A" * 200
        assert _sanitize_description(desc, max_length=200) == desc


class TestValidateOpenapiForBedrock:
    """Tests for _validate_openapi_for_bedrock function."""

    def test_valid_spec_no_warnings(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _validate_openapi_for_bedrock
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/b.abc123.tool1": {
                    "post": {
                        "operationId": "b_abc123_tool1",
                        "summary": "Short desc",
                        "description": "Short desc",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "key": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        warnings = _validate_openapi_for_bedrock(spec)
        assert len(warnings) == 0

    def test_too_many_apis_warns(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _validate_openapi_for_bedrock
        paths = {}
        for i in range(15):
            paths[f"/b.abc123.tool{i}"] = {
                "post": {
                    "operationId": f"b_abc123_tool{i}",
                    "summary": "desc",
                    "description": "desc",
                    "responses": {"200": {"description": "OK"}}
                }
            }
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": paths
        }
        warnings = _validate_openapi_for_bedrock(spec)
        assert any("API count" in w for w in warnings)

    def test_unsupported_keyword_warns(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _validate_openapi_for_bedrock
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/b.abc123.tool1": {
                    "post": {
                        "operationId": "b_abc123_tool1",
                        "summary": "desc",
                        "description": "desc",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "bad": {"anyOf": [{"type": "string"}, {"type": "null"}]}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        warnings = _validate_openapi_for_bedrock(spec)
        assert any("unsupported keyword" in w for w in warnings)

    def test_too_many_params_warns(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _validate_openapi_for_bedrock
        props = {f"param{i}": {"type": "string"} for i in range(8)}
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/b.abc123.tool1": {
                    "post": {
                        "operationId": "b_abc123_tool1",
                        "summary": "desc",
                        "description": "desc",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": props
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        warnings = _validate_openapi_for_bedrock(spec)
        assert any("parameter count" in w for w in warnings)


class TestAtlassianLikeSchemas:
    """Integration-style tests with schemas that mimic real Atlassian MCP tools."""

    def test_jira_create_issue_schema(self):
        """Simulate the create_issue tool from sooperset/mcp-atlassian."""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "project_key": {"type": "string", "description": "Project key"},
            "summary": {"type": "string", "description": "Issue summary"},
            "issue_type": {"type": "string", "description": "Issue type"},
            "assignee": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Assignee"
            },
            "description": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Description"
            },
            "components": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Components"
            },
            "additional_fields": {
                "anyOf": [
                    {"type": "object", "additionalProperties": {}},
                    {"type": "string"},
                    {"type": "null"}
                ],
                "description": "Additional fields as JSON"
            }
        }
        sanitized, required = _sanitize_tool_parameters(
            "create_issue", props,
            ["project_key", "summary", "issue_type"],
            max_params=5
        )
        # Should truncate to 5 params, keeping required ones
        assert len(sanitized) <= 5
        assert "project_key" in sanitized
        assert "summary" in sanitized
        assert "issue_type" in sanitized
        # All should be basic types
        for name, schema in sanitized.items():
            assert schema["type"] in ("string", "integer", "number", "boolean"), \
                f"{name}: unexpected type {schema.get('type')}"
            for kw in ('anyOf', 'oneOf', 'allOf', 'additionalProperties', '$ref'):
                assert kw not in schema, f"{name}: still has {kw}"

    def test_jira_update_issue_schema(self):
        """Simulate the update_issue tool with dict[str, Any] fields param."""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "issue_key": {"type": "string", "description": "Issue key"},
            "fields": {
                "type": "object",
                "additionalProperties": {},
                "description": "Fields to update as JSON"
            },
            "additional_fields": {
                "anyOf": [
                    {"type": "object", "additionalProperties": {}},
                    {"type": "null"}
                ],
                "description": "Extra fields"
            },
            "attachments": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Attachments"
            }
        }
        sanitized, required = _sanitize_tool_parameters(
            "update_issue", props, ["issue_key", "fields"]
        )
        assert sanitized["fields"]["type"] == "string"
        assert "additionalProperties" not in sanitized["fields"]

    def test_confluence_get_page_schema(self):
        """Simulate get_page with str | int | None page_id."""
        from bondable.bond.providers.bedrock.BedrockMCP import _sanitize_tool_parameters
        props = {
            "page_id": {
                "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
                "description": "Numeric page ID"
            },
            "title": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Page title"
            },
            "space_key": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Space key"
            },
            "include_metadata": {"type": "boolean", "default": True, "description": "Include metadata"},
            "convert_to_markdown": {"type": "boolean", "default": True, "description": "Convert to markdown"}
        }
        sanitized, required = _sanitize_tool_parameters(
            "get_page", props, []
        )
        assert sanitized["page_id"]["type"] == "string"
        assert sanitized["include_metadata"]["type"] == "boolean"
        assert len(sanitized) == 5  # Exactly at limit


class TestCoerceParametersForMcp:
    """Tests for _coerce_parameters_for_mcp function."""

    def test_string_param_stays_string(self):
        """String params with string schema stay as strings."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"issue_key": "MAS-6"}
        schema = {"properties": {"issue_key": {"type": "string"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["issue_key"] == "MAS-6"
        assert isinstance(result["issue_key"], str)

    def test_object_param_parsed_from_json_string(self):
        """String value for object-type param gets JSON-parsed to dict."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"fields": '{"description": "Updated description"}'}
        schema = {
            "properties": {
                "fields": {"type": "object", "additionalProperties": {}}
            }
        }
        result = _coerce_parameters_for_mcp("jira_update_issue", params, schema)
        assert isinstance(result["fields"], dict)
        assert result["fields"]["description"] == "Updated description"

    def test_array_param_parsed_from_json_string(self):
        """String value for array-type param gets JSON-parsed to list."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"issue_ids": '["MAS-1", "MAS-2", "MAS-3"]'}
        schema = {
            "properties": {
                "issue_ids": {"type": "array", "items": {"type": "string"}}
            }
        }
        result = _coerce_parameters_for_mcp("batch_get", params, schema)
        assert isinstance(result["issue_ids"], list)
        assert result["issue_ids"] == ["MAS-1", "MAS-2", "MAS-3"]

    def test_anyof_object_null_coerced(self):
        """String value for anyOf[object, null] param gets JSON-parsed."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"additional_fields": '{"priority": {"name": "High"}}'}
        schema = {
            "properties": {
                "additional_fields": {
                    "anyOf": [
                        {"type": "object", "additionalProperties": {}},
                        {"type": "null"}
                    ]
                }
            }
        }
        result = _coerce_parameters_for_mcp("create_issue", params, schema)
        assert isinstance(result["additional_fields"], dict)
        assert result["additional_fields"]["priority"]["name"] == "High"

    def test_non_json_string_stays_string(self):
        """String value that isn't JSON stays as string even for object type."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"fields": "not json at all"}
        schema = {
            "properties": {
                "fields": {"type": "object"}
            }
        }
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["fields"] == "not json at all"
        assert isinstance(result["fields"], str)

    def test_invalid_json_stays_string(self):
        """Malformed JSON stays as string."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"fields": '{bad json: ""}'}
        schema = {
            "properties": {
                "fields": {"type": "object"}
            }
        }
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert isinstance(result["fields"], str)

    def test_empty_params_returns_empty(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        result = _coerce_parameters_for_mcp("test", {}, {"properties": {}})
        assert result == {}

    def test_none_params_returns_none(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        result = _coerce_parameters_for_mcp("test", None, {"properties": {}})
        assert result is None

    def test_mixed_params_only_objects_coerced(self):
        """Only object/array params are coerced, strings stay as strings."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {
            "issue_key": "MAS-6",
            "fields": '{"summary": "New title"}',
            "comment": "This is a comment"
        }
        schema = {
            "properties": {
                "issue_key": {"type": "string"},
                "fields": {"type": "object", "additionalProperties": {}},
                "comment": {"anyOf": [{"type": "string"}, {"type": "null"}]}
            }
        }
        result = _coerce_parameters_for_mcp("jira_update_issue", params, schema)
        assert isinstance(result["issue_key"], str)
        assert result["issue_key"] == "MAS-6"
        assert isinstance(result["fields"], dict)
        assert result["fields"]["summary"] == "New title"
        assert isinstance(result["comment"], str)
        assert result["comment"] == "This is a comment"

    def test_does_not_mutate_original(self):
        """Original parameters dict is not modified."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"fields": '{"key": "val"}'}
        schema = {"properties": {"fields": {"type": "object"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert isinstance(params["fields"], str)  # Original unchanged
        assert isinstance(result["fields"], dict)  # Result coerced

    def test_boolean_true_coerced(self):
        """String "true" coerced to bool True for boolean params."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"include_metadata": "true"}
        schema = {"properties": {"include_metadata": {"type": "boolean", "default": True}}}
        result = _coerce_parameters_for_mcp("confluence_get_page", params, schema)
        assert result["include_metadata"] is True

    def test_boolean_false_coerced(self):
        """String "false" coerced to bool False for boolean params."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"convert_to_markdown": "false"}
        schema = {"properties": {"convert_to_markdown": {"type": "boolean"}}}
        result = _coerce_parameters_for_mcp("confluence_get_page", params, schema)
        assert result["convert_to_markdown"] is False

    def test_boolean_case_insensitive(self):
        """Boolean coercion is case-insensitive."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"flag": "True"}
        schema = {"properties": {"flag": {"type": "boolean"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["flag"] is True

    def test_boolean_non_bool_string_unchanged(self):
        """Non-boolean string stays as string for boolean param."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"flag": "yes"}
        schema = {"properties": {"flag": {"type": "boolean"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["flag"] == "yes"

    def test_integer_coerced(self):
        """String "10" coerced to int 10 for integer params."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"max_results": "10"}
        schema = {"properties": {"max_results": {"type": "integer", "description": "Max results"}}}
        result = _coerce_parameters_for_mcp("jira_search", params, schema)
        assert result["max_results"] == 10
        assert isinstance(result["max_results"], int)

    def test_integer_invalid_stays_string(self):
        """Non-numeric string stays as string for integer param."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"limit": "abc"}
        schema = {"properties": {"limit": {"type": "integer"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["limit"] == "abc"

    def test_number_coerced(self):
        """String "3.14" coerced to float for number params."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"score": "3.14"}
        schema = {"properties": {"score": {"type": "number"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["score"] == 3.14
        assert isinstance(result["score"], float)

    def test_number_integer_value_coerced_to_float(self):
        """String "10" coerced to float 10.0 for number params."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"weight": "10"}
        schema = {"properties": {"weight": {"type": "number"}}}
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["weight"] == 10.0
        assert isinstance(result["weight"], float)

    def test_anyof_integer_null_coerced(self):
        """Integer inside anyOf[integer, null] is coerced."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"start": "25"}
        schema = {
            "properties": {
                "start": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "description": "Start index"
                }
            }
        }
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["start"] == 25
        assert isinstance(result["start"], int)

    def test_anyof_boolean_null_coerced(self):
        """Boolean inside anyOf[boolean, null] is coerced."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {"verbose": "true"}
        schema = {
            "properties": {
                "verbose": {
                    "anyOf": [{"type": "boolean"}, {"type": "null"}]
                }
            }
        }
        result = _coerce_parameters_for_mcp("test", params, schema)
        assert result["verbose"] is True

    def test_full_atlassian_tool_coercion(self):
        """Simulate a full Atlassian tool call with mixed types."""
        from bondable.bond.providers.bedrock.BedrockMCP import _coerce_parameters_for_mcp
        params = {
            "issue_key": "MAS-6",
            "fields": '{"description": "Updated"}',
            "additional_fields": '{"priority": {"name": "High"}}',
            "attachments": "file.txt"
        }
        schema = {
            "properties": {
                "issue_key": {"type": "string"},
                "fields": {"type": "object", "additionalProperties": {}},
                "additional_fields": {
                    "anyOf": [
                        {"type": "object", "additionalProperties": {}},
                        {"type": "null"}
                    ]
                },
                "attachments": {
                    "anyOf": [{"type": "string"}, {"type": "null"}]
                }
            }
        }
        result = _coerce_parameters_for_mcp("jira_update_issue", params, schema)
        assert isinstance(result["issue_key"], str)
        assert isinstance(result["fields"], dict)
        assert isinstance(result["additional_fields"], dict)
        assert isinstance(result["attachments"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
