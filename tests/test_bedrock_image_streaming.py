"""
Test image streaming functionality for Bedrock provider.
Tests that BedrockAgent can properly stream both text and images from code interpreter.
"""

import os
import pytest
import base64
from unittest.mock import patch, MagicMock
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition


@pytest.fixture(scope="module") 
def provider():
    """Get the configured provider (should be Bedrock for these tests)"""
    with patch.dict(os.environ, {'BOND_PROVIDER_CLASS': 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'}):
        config = Config.config()
        return config.get_provider()


class TestImageStreaming:
    """Test image streaming functionality"""
    
    def test_text_only_response(self, provider):
        """Test that text-only responses work correctly"""
        # Create agent
        agent_def = AgentDefinition(
            user_id="image-test-user",
            name="Image Test Bot",
            description="A bot for testing image generation",
            instructions="You are a helpful assistant that can create visualizations.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="image-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="image-test-user",
            name="Image Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Test text-only response
            response = ""
            message_count = 0
            bond_messages = []
            
            for chunk in agent.stream_response(thread_id=thread_id, prompt="What is 2+2?"):
                if chunk.startswith('<_bondmessage'):
                    message_count += 1
                    # Extract agent_id and type from the bond message tag
                    if 'agent_id="' in chunk:
                        chunk_agent_id = chunk.split('agent_id="')[1].split('"')[0]
                        chunk_type = chunk.split('type="')[1].split('"')[0] if 'type="' in chunk else None
                        bond_messages.append({'agent_id': chunk_agent_id, 'type': chunk_type})
                elif not chunk.startswith('<') and not chunk.endswith('>'):
                    response += chunk
            
            # Should have exactly one message
            assert message_count == 1
            assert "4" in response
            
            # Verify agent_id is in bond messages
            assert len(bond_messages) == 1
            assert bond_messages[0]['agent_id'] == agent_id
            assert bond_messages[0]['type'] == 'text'
            
            # Verify messages are stored correctly in the database
            messages = provider.threads.get_messages(thread_id=thread_id)
            assert len(messages) >= 2  # User message + assistant response
            
            # Check assistant message has agent_id and correct type
            assistant_messages = [m for m in messages.values() if m.role == 'assistant']
            assert len(assistant_messages) >= 1
            
            for msg in assistant_messages:
                # Check agent_id is set on the message object
                assert hasattr(msg, 'agent_id'), "BondMessage should have agent_id attribute"
                assert msg.agent_id == agent_id, f"Expected agent_id {agent_id}, got {msg.agent_id}"
                
                # Check message type
                assert msg.type == 'text', f"Expected type 'text', got {msg.type}"
                
                # Also check metadata contains agent_id
                if hasattr(msg, 'metadata') and msg.metadata:
                    assert msg.metadata.get('agent_id') == agent_id, "Metadata should contain agent_id"
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="image-test-user")
            provider.agents.delete_agent(agent_id=agent_id)
    
    def test_image_generation_response(self, provider):
        """Test that image generation responses work correctly"""
        # Create agent with code interpreter enabled
        agent_def = AgentDefinition(
            user_id="image-test-user",
            name="Image Generation Bot",
            description="A bot that generates images",
            instructions="You are a helpful assistant that can create visualizations using code interpreter.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="image-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="image-test-user",
            name="Image Generation Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Request image generation
            prompt = "Using code interpreter, create a simple bar chart showing sales data for 5 products (Product A: 100, Product B: 150, Product C: 80, Product D: 120, Product E: 90)"
            
            messages = []
            current_message = None
            bond_messages = []
            
            for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                if chunk.startswith('<_bondmessage'):
                    # Extract agent_id and type
                    chunk_agent_id = None
                    chunk_type = None
                    if 'agent_id="' in chunk:
                        chunk_agent_id = chunk.split('agent_id="')[1].split('"')[0]
                    if 'type="' in chunk:
                        chunk_type = chunk.split('type="')[1].split('"')[0]
                    
                    bond_messages.append({'agent_id': chunk_agent_id, 'type': chunk_type})
                    
                    # Parse message attributes
                    if 'type="text"' in chunk:
                        current_message = {"type": "text", "content": "", "agent_id": chunk_agent_id}
                    elif 'type="image_file"' in chunk:
                        current_message = {"type": "image_file", "content": "", "agent_id": chunk_agent_id}
                elif chunk == '</_bondmessage>':
                    if current_message:
                        messages.append(current_message)
                        current_message = None
                elif current_message is not None:
                    current_message["content"] += chunk
            
            # Verify all bond messages have agent_id
            for bond_msg in bond_messages:
                assert bond_msg['agent_id'] == agent_id, f"Expected agent_id {agent_id}, got {bond_msg['agent_id']}"
                assert bond_msg['type'] in ['text', 'image_file'], f"Invalid message type: {bond_msg['type']}"
            
            # Should have at least one text message
            text_messages = [m for m in messages if m["type"] == "text"]
            assert len(text_messages) >= 1
            
            # Should have at least one image message
            image_messages = [m for m in messages if m["type"] == "image_file"]
            assert len(image_messages) >= 1, f"Expected at least one image message, got {len(image_messages)}"
            
            # Verify image message contains base64 data
            for img_msg in image_messages:
                assert img_msg["content"].startswith("data:image/"), f"Image should start with data URL format"
                assert ";base64," in img_msg["content"], "Image should be base64 encoded"
                
                # Verify it's valid base64
                try:
                    data_url = img_msg["content"]
                    base64_data = data_url.split(",")[1]
                    base64.b64decode(base64_data)
                except Exception as e:
                    pytest.fail(f"Invalid base64 image data: {e}")
            
            # Verify database storage
            db_messages = provider.threads.get_messages(thread_id=thread_id)
            
            # Check we have both text and image messages in DB
            db_text_messages = [m for m in db_messages.values() if m.type == 'text' and m.role == 'assistant']
            db_image_messages = [m for m in db_messages.values() if m.type == 'image_file' and m.role == 'assistant']
            
            assert len(db_text_messages) >= 1, "Should have at least one text message in DB"
            assert len(db_image_messages) >= 1, "Should have at least one image message in DB"
            
            # Verify all messages have agent_id
            for msg in db_messages.values():
                if msg.role == 'assistant':
                    assert hasattr(msg, 'agent_id'), f"Message {msg.message_id} should have agent_id"
                    assert msg.agent_id == agent_id, f"Expected agent_id {agent_id}, got {msg.agent_id}"
                    
                    # Verify metadata also contains agent_id
                    if hasattr(msg, 'metadata') and msg.metadata:
                        assert msg.metadata.get('agent_id') == agent_id, "Metadata should contain agent_id"
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="image-test-user")
            provider.agents.delete_agent(agent_id=agent_id)
    
    def test_mixed_content_response(self, provider):
        """Test that responses with both text and images work correctly"""
        # Create agent
        agent_def = AgentDefinition(
            user_id="mixed-test-user",
            name="Mixed Content Bot",
            description="A bot that generates mixed content",
            instructions="You are a helpful assistant that can create visualizations and explain them.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="mixed-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="mixed-test-user",
            name="Mixed Content Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Request mixed content
            prompt = "Using code interpreter, create a pie chart showing market share (Company A: 40%, Company B: 30%, Company C: 20%, Company D: 10%) and explain what it shows"
            
            messages = []
            current_message = None
            message_order = []
            bond_messages = []
            
            for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                if chunk.startswith('<_bondmessage'):
                    # Extract agent_id and type
                    chunk_agent_id = None
                    chunk_type = None
                    if 'agent_id="' in chunk:
                        chunk_agent_id = chunk.split('agent_id="')[1].split('"')[0]
                    if 'type="' in chunk:
                        chunk_type = chunk.split('type="')[1].split('"')[0]
                    
                    bond_messages.append({'agent_id': chunk_agent_id, 'type': chunk_type})
                    
                    # Parse message attributes
                    if 'type="text"' in chunk:
                        current_message = {"type": "text", "content": "", "agent_id": chunk_agent_id}
                        message_order.append("text")
                    elif 'type="image_file"' in chunk:
                        current_message = {"type": "image_file", "content": "", "agent_id": chunk_agent_id}
                        message_order.append("image")
                elif chunk == '</_bondmessage>':
                    if current_message:
                        messages.append(current_message)
                        current_message = None
                elif current_message is not None:
                    current_message["content"] += chunk
            
            # Verify all bond messages have agent_id
            for bond_msg in bond_messages:
                assert bond_msg['agent_id'] == agent_id, f"Expected agent_id {agent_id}, got {bond_msg['agent_id']}"
                assert bond_msg['type'] in ['text', 'image_file'], f"Invalid message type: {bond_msg['type']}"
            
            # Should have both text and image messages
            text_messages = [m for m in messages if m["type"] == "text"]
            image_messages = [m for m in messages if m["type"] == "image_file"]
            
            assert len(text_messages) >= 1, "Should have at least one text message"
            assert len(image_messages) >= 1, "Should have at least one image message"
            
            # Verify message ordering makes sense (text can come before and/or after image)
            assert "text" in message_order
            assert "image" in message_order
            
            # Verify text content relates to the chart
            combined_text = " ".join(m["content"] for m in text_messages)
            # Should mention something about the chart or data
            assert any(word in combined_text.lower() for word in ["chart", "pie", "market", "share", "company", "percent", "%"])
            
            # Verify database storage
            db_messages = provider.threads.get_messages(thread_id=thread_id)
            
            # Verify all assistant messages have agent_id and proper types
            for msg in db_messages.values():
                if msg.role == 'assistant':
                    assert hasattr(msg, 'agent_id'), f"Message {msg.message_id} should have agent_id"
                    assert msg.agent_id == agent_id, f"Expected agent_id {agent_id}, got {msg.agent_id}"
                    assert msg.type in ['text', 'image_file'], f"Invalid message type: {msg.type}"
                    
                    # Verify metadata also contains agent_id
                    if hasattr(msg, 'metadata') and msg.metadata:
                        assert msg.metadata.get('agent_id') == agent_id, "Metadata should contain agent_id"
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="mixed-test-user")
            provider.agents.delete_agent(agent_id=agent_id)


class TestImageStreamingErrorHandling:
    """Test error handling for image streaming"""
    
    def test_invalid_image_data_handling(self, provider):
        """Test that invalid image data is handled gracefully"""
        # This test would require mocking the Bedrock response to send invalid data
        # For now, we'll test that the agent handles requests that don't generate images
        
        agent_def = AgentDefinition(
            user_id="error-test-user",
            name="Error Test Bot",
            description="A bot for error testing",
            instructions="You are a helpful assistant.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="error-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="error-test-user",
            name="Error Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Request that shouldn't generate an image
            response = ""
            error_occurred = False
            
            try:
                for chunk in agent.stream_response(thread_id=thread_id, prompt="Tell me a joke"):
                    if not chunk.startswith('<') and not chunk.endswith('>'):
                        response += chunk
            except Exception as e:
                error_occurred = True
                pytest.fail(f"Should handle non-image responses gracefully: {e}")
            
            assert not error_occurred
            assert len(response) > 0  # Should have some text response
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="error-test-user")
            provider.agents.delete_agent(agent_id=agent_id)


# Run with: pytest tests/test_bedrock_image_streaming.py -v