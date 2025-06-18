"""
MCP functionality tests for Bedrock provider.
Tests MCP tool integration with real MCP server.
"""

import os
import json
import pytest
from datetime import datetime
from unittest.mock import patch
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition


@pytest.fixture(scope="module") 
def provider():
    """Get the configured provider with MCP config"""
    mcp_config = {
        "mcpServers": {
            "test_server": {
                "url": "http://127.0.0.1:5555/mcp"
            }
        }
    }
    
    with patch.dict(os.environ, {
        'BOND_PROVIDER_CLASS': 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider',
        'BOND_MCP_CONFIG': json.dumps(mcp_config)
    }):
        config = Config.config()
        return config.get_provider()


class TestMCPFunctionality:
    """Test MCP tool functionality with Bedrock provider"""
    
    def test_mcp_current_time(self, provider):
        """Test that agent can use current_time MCP tool"""
        # Create agent with MCP tool
        agent_def = AgentDefinition(
            user_id="mcp-test-user",
            name="MCP Time Assistant",
            description="An assistant that can check the current time",
            instructions="""You are a helpful assistant that can check the current time.
When asked about the time, use the _bond_mcp_tool_current_time tool to get the accurate time.
Always use the tool when asked about time - don't guess or make up times.""",
            model=provider.get_default_model(),
            mcp_tools=["current_time"]  # Include MCP tool
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="mcp-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="mcp-test-user",
            name="MCP Time Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Ask about the time
            prompt = "What is the current time?"
            response = ""
            
            for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                if not chunk.startswith('<') and not chunk.endswith('>'):
                    response += chunk
            
            # Check that response contains time information
            assert any(indicator in response.lower() for indicator in ['time', 'o\'clock', 'am', 'pm', ':']), \
                f"Response doesn't appear to contain time information: {response}"
            
            # Extract time from response and verify it's close to current time
            current_time = datetime.now()
            current_hour = current_time.hour
            
            # Check if response contains current hour (allowing for timezone differences)
            # Convert to 12-hour format for checking
            hour_12 = current_hour % 12
            if hour_12 == 0:
                hour_12 = 12
                
            hour_found = False
            # Check for various hour formats
            for hour_format in [str(current_hour), str(hour_12), f"{current_hour:02d}", f"{hour_12:02d}"]:
                if hour_format in response:
                    hour_found = True
                    break
            
            assert hour_found, f"Response doesn't contain current hour ({current_hour} or {hour_12}): {response}"
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="mcp-test-user")
            provider.agents.delete_agent(agent_id=agent_id)
    
    def test_mcp_tool_not_used_when_not_needed(self, provider):
        """Test that MCP tools are not used when not needed"""
        # Create agent with MCP tool
        agent_def = AgentDefinition(
            user_id="mcp-test-user",
            name="MCP Math Assistant",
            description="An assistant with MCP tools",
            instructions="You are a helpful math assistant. You have access to tools but should only use them when necessary.",
            model=provider.get_default_model(),
            mcp_tools=["current_time"]  # Tool available but not needed
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="mcp-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="mcp-test-user",
            name="MCP Math Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Ask a math question (shouldn't use time tool)
            prompt = "What is 2 + 2?"
            response = ""
            
            for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                if not chunk.startswith('<') and not chunk.endswith('>'):
                    response += chunk
            
            # Check response contains the answer
            assert "4" in response, f"Response doesn't contain correct answer: {response}"
            
            # Verify time-related content is not in response (tool wasn't used)
            time_indicators = ['current time', 'o\'clock', 'am', 'pm']
            assert not any(indicator in response.lower() for indicator in time_indicators), \
                f"Response unexpectedly contains time information: {response}"
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="mcp-test-user")
            provider.agents.delete_agent(agent_id=agent_id)
    
    def test_multiple_mcp_tools(self, provider):
        """Test agent with multiple MCP tools available"""
        # Create agent with multiple MCP tools
        agent_def = AgentDefinition(
            user_id="mcp-test-user",
            name="Multi-Tool Assistant",
            description="An assistant with multiple MCP tools",
            instructions="""You are a helpful assistant with access to various tools.
Use the appropriate tool when asked:
- For time questions, use the _bond_mcp_tool_current_time tool
Always use tools to get accurate information.""",
            model=provider.get_default_model(),
            mcp_tools=["current_time"]  # In a real test, we'd add more tools
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="mcp-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="mcp-test-user",
            name="Multi-Tool Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Test conversation with tool usage
            conversations = [
                ("What time is it?", ['time', 'o\'clock', 'am', 'pm', ':']),
                ("Thanks! What is 5 * 5?", ['25'])
            ]
            
            for prompt, expected_indicators in conversations:
                response = ""
                for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                    if not chunk.startswith('<') and not chunk.endswith('>'):
                        response += chunk
                
                # Check response contains expected indicators
                assert any(indicator in response.lower() for indicator in expected_indicators), \
                    f"Response missing expected content. Prompt: '{prompt}', Response: '{response}'"
            
            # Verify conversation history
            messages = provider.threads.get_messages(thread_id, limit=10)
            assert len(messages) >= 4  # At least 2 exchanges
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="mcp-test-user")
            provider.agents.delete_agent(agent_id=agent_id)


@pytest.mark.skipif(
    os.getenv('SKIP_MCP_TESTS', 'false').lower() == 'true',
    reason="MCP server not available or SKIP_MCP_TESTS is set"
)
class TestMCPServerRequired:
    """Tests that require a running MCP server"""
    
    def test_mcp_server_connectivity(self, provider):
        """Test that MCP server is accessible"""
        try:
            # Create a minimal agent with MCP tool to test connectivity
            agent_def = AgentDefinition(
                user_id="mcp-connectivity-test",
                name="Connectivity Test",
                description="Testing MCP server connectivity",
                instructions="Test agent",
                model=provider.get_default_model(),
                mcp_tools=["current_time"]
            )
            
            agent = provider.agents.create_or_update_agent(
                agent_def=agent_def,
                user_id="mcp-connectivity-test"
            )
            
            # If we get here, MCP server is accessible
            provider.agents.delete_agent(agent_id=agent.get_agent_id())
            
        except Exception as e:
            pytest.skip(f"MCP server not accessible: {e}")


# Run with: pytest tests/test_bedrock_mcp_functionality.py -v
# To skip MCP tests: SKIP_MCP_TESTS=true pytest tests/test_bedrock_mcp_functionality.py -v