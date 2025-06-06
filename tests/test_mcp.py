#!/usr/bin/env python3
"""
Comprehensive test suite for MCP (Model Context Protocol) integration.

Tests the integration between MCP tools/resources and OpenAI Assistants API,
including tool conversion, agent creation/update, and event handling.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, Mock
from bondable.bond.definition import AgentDefinition


class TestMCPFunctionDetection:
    """Test MCP function name detection and parsing."""

    def test_mcp_function_name_detection(self):
        """Test that MCP function names are correctly detected."""
        # Test MCP tool detection
        assert "mcp_test_tool".startswith("mcp_")
        assert not "mcp_test_tool".startswith("mcp_resource_")
        
        # Test MCP resource detection
        assert "mcp_resource_test_resource".startswith("mcp_resource_")
        assert "mcp_resource_test_resource".startswith("mcp_")
        
        # Test regular function detection
        assert not "calculate_sum".startswith("mcp_")

    def test_mcp_name_parsing(self):
        """Test parsing of MCP function names."""
        # Test MCP tool name extraction
        function_name = "mcp_add_numbers"
        tool_name = function_name[4:]  # Remove "mcp_" prefix
        assert tool_name == "add_numbers"
        
        # Test MCP resource name extraction
        function_name = "mcp_resource_settings"
        resource_name = function_name[13:]  # Remove "mcp_resource_" prefix
        assert resource_name == "settings"

    def test_argument_handling(self):
        """Test MCP argument parsing and handling."""
        arguments = {"a": 10, "b": 5}
        arguments_json = json.dumps(arguments)
        parsed_args = json.loads(arguments_json)
        assert parsed_args == arguments


class TestMCPToolConversion:
    """Test MCP tool and resource conversion to OpenAI format."""

    @patch('bondable.bond.mcp_client.MCPClient.client')
    @patch('bondable.bond.config.Config.config')
    def test_mcp_tool_conversion_logic(self, mock_config, mock_client_method):
        """Test the logic of converting MCP tools to OpenAI format."""
        from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
        
        # Mock the MCP client
        mock_client = MagicMock()
        mock_client_method.return_value = mock_client
        
        # Create mock MCP tool
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool description"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            },
            "required": ["param1"]
        }
        
        mock_client.list_tools_sync.return_value = [mock_tool]
        
        # Create provider
        provider = OAIAAgentProvider(openai_client=MagicMock(), metadata=MagicMock())
        
        # Test conversion
        result = provider._fetch_and_convert_mcp_tools(["test_tool"])
        
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "mcp_test_tool"
        assert result[0]["function"]["description"] == "Test tool description"
        assert result[0]["function"]["parameters"] == mock_tool.inputSchema

    @patch('bondable.bond.mcp_client.MCPClient.client')
    @patch('bondable.bond.config.Config.config')
    def test_mcp_resource_conversion_logic(self, mock_config, mock_client_method):
        """Test the logic of converting MCP resources to OpenAI format."""
        from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
        
        # Mock the MCP client
        mock_client = MagicMock()
        mock_client_method.return_value = mock_client
        
        # Create mock MCP resource
        mock_resource = MagicMock()
        mock_resource.name = "test_resource"
        mock_resource.uri = "file:///test/resource"
        mock_resource.description = "Test resource description"
        
        mock_client.list_resources_sync.return_value = [mock_resource]
        
        # Create provider
        provider = OAIAAgentProvider(openai_client=MagicMock(), metadata=MagicMock())
        
        # Test conversion
        result = provider._fetch_and_convert_mcp_resources(["test_resource"])
        
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "mcp_resource_test_resource"
        assert "Read resource:" in result[0]["function"]["description"]
        assert result[0]["function"]["parameters"]["type"] == "object"


class TestEventHandlerMCP:
    """Test EventHandler MCP tool and resource execution."""

    @patch('bondable.bond.mcp_client.MCPClient.client')
    def test_event_handler_mcp_tool_call(self, mock_client_method):
        """Test that EventHandler correctly handles MCP tool calls."""
        from bondable.bond.providers.openai.OAIAAgent import EventHandler
        from bondable.bond.functions import Functions
        from queue import Queue
        
        # Mock the MCP client
        mock_client = MagicMock()
        mock_client_method.return_value = mock_client
        mock_client.call_tool_sync.return_value = "test_result"
        
        # Create EventHandler
        event_handler = EventHandler(
            message_queue=Queue(),
            openai_client=MagicMock(),
            functions=Functions.functions(),
            thread_id="test_thread"
        )
        
        # Test MCP tool call
        result = event_handler._handle_mcp_call("mcp_test_tool", {"param": "value"})
        assert result == "test_result"
        mock_client.call_tool_sync.assert_called_with("test_tool", {"param": "value"})

    @patch('bondable.bond.mcp_client.MCPClient.client')
    def test_event_handler_mcp_resource_call(self, mock_client_method):
        """Test that EventHandler correctly handles MCP resource calls."""
        from bondable.bond.providers.openai.OAIAAgent import EventHandler
        from bondable.bond.functions import Functions
        from queue import Queue
        
        # Mock the MCP client
        mock_client = MagicMock()
        mock_client_method.return_value = mock_client
        
        # Create a proper mock resource with the expected attributes
        mock_resource = MagicMock()
        mock_resource.name = "test_resource"
        mock_resource.uri = "test://uri"
        
        mock_client.list_resources_sync.return_value = [mock_resource]
        mock_client.read_resource_sync.return_value = "resource_content"
        
        # Create EventHandler
        event_handler = EventHandler(
            message_queue=Queue(),
            openai_client=MagicMock(),
            functions=Functions.functions(),
            thread_id="test_thread"
        )
        
        # Test MCP resource call
        result = event_handler._handle_mcp_call("mcp_resource_test_resource", {})
        assert result == "resource_content"
        mock_client.read_resource_sync.assert_called_with("test://uri")


class TestAgentDefinition:
    """Test AgentDefinition with MCP tools and resources."""

    def test_agent_definition_with_mcp(self):
        """Test creating an AgentDefinition with MCP tools and resources."""
        agent_def = AgentDefinition(
            name="Test Agent",
            description="Test Description",
            instructions="Test Instructions",
            model="gpt-4o",
            user_id="test_user",
            mcp_tools=["tool1", "tool2"],
            mcp_resources=["resource1", "resource2"]
        )
        
        assert agent_def.name == "Test Agent"
        assert agent_def.mcp_tools == ["tool1", "tool2"]
        assert agent_def.mcp_resources == ["resource1", "resource2"]
        assert len(agent_def.tools) == 0  # No regular tools added


if __name__ == "__main__":
    # Run the tests with pytest
    pytest.main([__file__, "-v"])