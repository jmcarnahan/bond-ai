"""
Quick functionality tests for Bedrock provider.
Mirrors the functionality from scripts/quick_provider_test.py
"""

import os
import pytest
from unittest.mock import patch
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition


@pytest.fixture(scope="module") 
def provider():
    """Get the configured provider (should be Bedrock for these tests)"""
    with patch.dict(os.environ, {'BOND_PROVIDER_CLASS': 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'}):
        config = Config.config()
        return config.get_provider()


class TestQuickFunctionality:
    """Quick tests that mirror quick_provider_test.py functionality"""
    
    def test_provider_basics(self, provider):
        """Test basic provider information"""
        # Check provider name
        assert type(provider).__name__ == "BedrockProvider"
        
        # Check default model
        default_model = provider.get_default_model()
        assert default_model is not None
        assert isinstance(default_model, str)
        assert len(default_model) > 0
    
    def test_quick_conversation_flow(self, provider):
        """Test a quick conversation flow like in quick_provider_test.py"""
        # Create agent
        agent_def = AgentDefinition(
            user_id="quick-test-user",
            name="Quick Test Bot",
            description="A quick test bot",
            instructions="You are a helpful math tutor. Be concise.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="quick-test-user"
        )
        agent_id = agent.get_agent_id()
        
        # Create thread
        thread = provider.threads.create_thread(
            user_id="quick-test-user",
            name="Quick Test Thread"
        )
        thread_id = thread.thread_id
        
        try:
            # Test conversation flow
            conversations = [
                ("Hello! What's 2+2?", "4"),
                ("Great! Now what's 10 times that?", "40"),
                ("Thanks!", None)  # Don't check response for this
            ]
            
            for prompt, expected in conversations:
                response = ""
                for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
                    if not chunk.startswith('<') and not chunk.endswith('>'):
                        response += chunk
                
                # Check response if expected
                if expected:
                    assert expected in response, f"Expected '{expected}' in response but got: {response}"
            
            # Verify thread has messages
            messages = provider.threads.get_messages(thread_id, limit=10)
            assert len(messages) >= len(conversations) * 2  # User + assistant messages
            
        finally:
            # Cleanup
            provider.threads.delete_thread(thread_id=thread_id, user_id="quick-test-user")
            provider.agents.delete_agent(agent_id=agent_id)
    
    def test_agent_instructions_followed(self, provider):
        """Test that agents follow their instructions"""
        test_cases = [
            {
                "name": "Concise Agent",
                "instructions": "You are a helpful assistant. Always respond in exactly one sentence.",
                "prompt": "Explain photosynthesis",
                "check": lambda r: r.count('.') <= 2  # Should have minimal sentences
            },
            {
                "name": "Enthusiastic Agent",
                "instructions": "You are an enthusiastic assistant. Always include an exclamation mark in your responses!",
                "prompt": "What is 2+2?",
                "check": lambda r: '!' in r
            }
        ]
        
        for test_case in test_cases:
            # Create agent
            agent_def = AgentDefinition(
                user_id="instruction-test-user",
                name=test_case["name"],
                description="Testing instruction following",
                instructions=test_case["instructions"],
                model=provider.get_default_model()
            )
            
            agent = provider.agents.create_or_update_agent(
                agent_def=agent_def,
                user_id="instruction-test-user"
            )
            
            # Create thread
            thread = provider.threads.create_thread(
                user_id="instruction-test-user",
                name=f"{test_case['name']} Test"
            )
            
            try:
                # Get response
                response = ""
                for chunk in agent.stream_response(
                    thread_id=thread.thread_id,
                    prompt=test_case["prompt"]
                ):
                    if not chunk.startswith('<') and not chunk.endswith('>'):
                        response += chunk
                
                # Check response matches expected pattern
                assert test_case["check"](response), \
                    f"{test_case['name']} didn't follow instructions. Response: {response}"
                
            finally:
                # Cleanup
                provider.threads.delete_thread(
                    thread_id=thread.thread_id,
                    user_id="instruction-test-user"
                )
                provider.agents.delete_agent(agent_id=agent.get_agent_id())


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_missing_thread_id(self, provider):
        """Test that streaming without thread_id raises appropriate error"""
        agent_def = AgentDefinition(
            user_id="error-test-user",
            name="Error Test Agent",
            description="Testing error handling",
            instructions="You are a test agent.",
            model=provider.get_default_model()
        )
        
        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="error-test-user"
        )
        
        try:
            # Should raise ValueError for missing thread_id
            with pytest.raises(ValueError, match="thread_id is required"):
                list(agent.stream_response(prompt="Hello"))
                
        finally:
            provider.agents.delete_agent(agent_id=agent.get_agent_id())
    
    def test_agent_not_found(self, provider):
        """Test retrieving non-existent agent"""
        fake_agent_id = "bedrock_agent_nonexistent"
        agent = provider.agents.get_agent(fake_agent_id)
        assert agent is None


# Run with: pytest tests/test_bedrock_quick_functionality.py -v