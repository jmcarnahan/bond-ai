"""
Integration test for BedrockAgent.stream_response method.
This test actually calls AWS Bedrock to validate the streaming functionality.
"""

import os
import json
import pytest
import logging
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def provider():
    """Get the configured Bedrock provider"""
    os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'
    os.environ['BOND_MCP_CONFIG'] = json.dumps({
        "mcpServers": {
            "test_server": {
                "url": "http://127.0.0.1:5555/mcp"
            }
        }
    })
    config = Config.config()
    return config.get_provider()


@pytest.mark.integration
class TestStreamResponseIntegration:
    """Integration tests that actually call AWS Bedrock"""
    
    def test_basic_text_streaming(self, provider):
        """Test basic text streaming functionality"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Integration Test Agent",
            description="Agent for integration testing",
            instructions="You are a helpful assistant. Keep responses brief.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()
        
        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Integration Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Stream a simple response
            response_chunks = []
            bond_message_count = 0
            
            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What is 2+2? Answer with just the number."
            ):
                response_chunks.append(chunk)
                if chunk.startswith('<_bondmessage'):
                    bond_message_count += 1
                    logger.info(f"Bond message started: {chunk[:100]}...")
                elif chunk == '</_bondmessage>':
                    logger.info("Bond message ended")
            
            # Verify response
            full_response = ''.join(response_chunks)
            assert '4' in full_response
            assert bond_message_count == 1
            
            # Check database
            messages = provider.threads.get_messages(thread_id=thread_id)
            assert len(messages) >= 2  # User + assistant
            
            logger.info("✓ Basic text streaming test passed")
            
        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
    
    def test_image_generation_streaming(self, provider):
        """Test streaming with image generation"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Image Generation Test Agent",
            description="Agent for testing image generation",
            instructions="You are a helpful assistant that can create visualizations using code interpreter.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()
        
        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Image Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Request image generation
            prompt = "Using code interpreter, create a simple bar chart with 3 data points: A=10, B=20, C=15. Save it as an image."
            
            message_types = []
            current_type = None
            
            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt=prompt
            ):
                if 'type="text"' in chunk:
                    current_type = 'text'
                    message_types.append('text')
                    logger.info("Started text message")
                elif 'type="image_file"' in chunk:
                    current_type = 'image_file'
                    message_types.append('image_file')
                    logger.info("Started image message")
                elif 'data:image' in chunk and current_type == 'image_file':
                    logger.info(f"Received image data (length: {len(chunk)})")
            
            # Verify we got both text and image
            assert 'text' in message_types
            assert 'image_file' in message_types
            
            logger.info("✓ Image generation streaming test passed")
            
        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
    
    def test_mcp_tool_streaming(self, provider):
        """Test streaming with MCP tool execution"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="MCP Tool Test Agent",
            description="Agent for testing MCP tools",
            instructions="You are a helpful assistant. When asked for the time, use the current_time tool.",
            model=provider.get_default_model(),
            mcp_tools=["current_time"]
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()
        
        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="MCP Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Request MCP tool use
            response_chunks = []
            
            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What is the current time?"
            ):
                response_chunks.append(chunk)
                if 'returnControl' in chunk:
                    logger.info("MCP tool invocation detected")
            
            # Verify response mentions time
            full_response = ''.join(response_chunks).lower()
            assert any(word in full_response for word in ['time', 'clock', 'hour', 'minute'])
            
            logger.info("✓ MCP tool streaming test passed")
            
        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)


# Run with: poetry run pytest tests/test_bedrock_stream_response_integration.py -v -m integration