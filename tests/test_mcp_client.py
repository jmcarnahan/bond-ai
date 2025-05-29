import pytest
import asyncio
import os
import json
from unittest.mock import Mock, patch
from bondable.bond.mcp_client import MCPClient, MCPTool
from bondable.bond.config import Config


class TestMCPClient:
    """Test cases for MCP client functionality"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config with test MCP servers"""
        config = Mock(spec=Config)
        config.get_mcp_servers.return_value = [
            {
                "name": "hello",
                "command": ["python", "hello_mcp_server.py"]
            }
        ]
        return config

    @pytest.fixture
    def mcp_client(self, mock_config):
        """Create MCP client with mock config"""
        return MCPClient(config=mock_config)

    def test_mcp_tool_creation(self):
        """Test MCPTool object creation and serialization"""
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            server="test_server",
            schema={"type": "object", "properties": {"param": {"type": "string"}}}
        )
        
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.server == "test_server"
        assert tool.schema["type"] == "object"
        
        tool_dict = tool.to_dict()
        assert tool_dict["name"] == "test_tool"
        assert tool_dict["server"] == "test_server"

    def test_mcp_client_initialization(self, mock_config):
        """Test MCP client initialization"""
        client = MCPClient(config=mock_config)
        assert client.config == mock_config
        assert len(client.sessions) == 0
        assert client._tools_cache is None

    def test_config_get_mcp_servers_default(self):
        """Test Config.get_mcp_servers with default values"""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            servers = config.get_mcp_servers()
            
            assert len(servers) == 1
            assert servers[0]["name"] == "hello"
            assert servers[0]["command"] == ["python", "hello_mcp_server.py"]

    def test_config_get_mcp_servers_custom(self):
        """Test Config.get_mcp_servers with custom environment variable"""
        custom_servers = [
            {"name": "custom", "command": ["python", "custom_server.py"]},
            {"name": "another", "command": ["node", "server.js"]}
        ]
        
        with patch.dict(os.environ, {
            'BOND_MCP_SERVERS': json.dumps(custom_servers)
        }, clear=True):
            config = Config()
            servers = config.get_mcp_servers()
            
            assert len(servers) == 2
            assert servers[0]["name"] == "custom"
            assert servers[1]["name"] == "another"

    def test_config_get_mcp_servers_invalid_json(self):
        """Test Config.get_mcp_servers with invalid JSON"""
        with patch.dict(os.environ, {
            'BOND_MCP_SERVERS': 'invalid json'
        }, clear=True):
            config = Config()
            servers = config.get_mcp_servers()
            
            assert servers == []

    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, mcp_client):
        """Test getting tool by name from cache"""
        # Manually populate cache for testing
        test_tools = [
            MCPTool("tool1", "Description 1", "server1", {}),
            MCPTool("tool2", "Description 2", "server1", {}),
            MCPTool("tool3", "Description 3", "server2", {})
        ]
        mcp_client._tools_cache = test_tools
        
        tool = mcp_client.get_tool_by_name("tool2")
        assert tool is not None
        assert tool.name == "tool2"
        assert tool.description == "Description 2"
        
        # Test non-existent tool
        tool = mcp_client.get_tool_by_name("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_get_tools_by_server(self, mcp_client):
        """Test getting tools by server from cache"""
        # Manually populate cache for testing
        test_tools = [
            MCPTool("tool1", "Description 1", "server1", {}),
            MCPTool("tool2", "Description 2", "server1", {}),
            MCPTool("tool3", "Description 3", "server2", {})
        ]
        mcp_client._tools_cache = test_tools
        
        server1_tools = mcp_client.get_tools_by_server("server1")
        assert len(server1_tools) == 2
        assert all(tool.server == "server1" for tool in server1_tools)
        
        server2_tools = mcp_client.get_tools_by_server("server2")
        assert len(server2_tools) == 1
        assert server2_tools[0].name == "tool3"
        
        # Test non-existent server
        nonexistent_tools = mcp_client.get_tools_by_server("nonexistent")
        assert len(nonexistent_tools) == 0

    @pytest.mark.asyncio
    async def test_close_sessions(self, mcp_client):
        """Test closing all MCP sessions"""
        # Mock sessions
        mock_session1 = Mock()
        mock_session1.close = Mock(return_value=asyncio.Future())
        mock_session1.close.return_value.set_result(None)
        
        mock_session2 = Mock()
        mock_session2.close = Mock(return_value=asyncio.Future())
        mock_session2.close.return_value.set_result(None)
        
        mcp_client.sessions = {
            "server1": mock_session1,
            "server2": mock_session2
        }
        mcp_client._tools_cache = [MCPTool("test", "test", "test", {})]
        
        await mcp_client.close()
        
        # Verify sessions were closed
        mock_session1.close.assert_called_once()
        mock_session2.close.assert_called_once()
        
        # Verify cleanup
        assert len(mcp_client.sessions) == 0
        assert mcp_client._tools_cache is None


# Integration test that requires actual MCP server
class TestMCPClientIntegration:
    """Integration tests for MCP client (requires running MCP server)"""

    @pytest.fixture
    def real_config(self):
        """Create a real config for integration testing"""
        return Config()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_mcp_connection(self, real_config):
        """
        Test connecting to a real MCP server.
        This test requires the hello_mcp_server.py to be available and working.
        Mark with @pytest.mark.integration and run separately if needed.
        """
        client = MCPClient(config=real_config)
        
        try:
            # This will try to connect to the configured MCP servers
            await client.connect_to_servers()
            
            # If we have sessions, test getting tools
            if client.sessions:
                tools = await client.get_available_tools()
                assert isinstance(tools, list)
                
                # If we found tools, test calling one
                if tools:
                    hello_tool = next((t for t in tools if t.name == "hello"), None)
                    if hello_tool:
                        result = await client.call_tool(
                            "hello", 
                            hello_tool.server, 
                            {"name": "Test User"}
                        )
                        assert result is not None
            
        finally:
            await client.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])