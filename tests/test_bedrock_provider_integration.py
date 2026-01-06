"""
Integration tests for the Bedrock provider covering agent lifecycle and conversation functionality.
Based on quick_provider_test.py and test_bedrock_agent_lifecycle.py functionality.
"""

import os
import pytest
import uuid
from unittest.mock import patch
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition


@pytest.fixture(scope="module")
def bedrock_provider():
    """Get the Bedrock provider instance"""
    # Force Bedrock provider
    with patch.dict(os.environ, {'BOND_PROVIDER_CLASS': 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'}):
        config = Config.config()
        provider = config.get_provider()

        # Verify it's the Bedrock provider
        assert type(provider).__name__ == "BedrockProvider"
        yield provider


@pytest.fixture
def test_user_id():
    """Generate a unique test user ID"""
    return f"pytest_user_{uuid.uuid4().hex[:8]}"


class TestBedrockAgentLifecycle:
    """Test complete agent lifecycle including creation, conversation, and deletion"""

    def test_agent_creation_with_automatic_bedrock_agent(self, bedrock_provider, test_user_id):
        """Test that creating a Bond agent automatically creates a Bedrock Agent"""
        # Create agent definition
        agent_def = AgentDefinition(
            user_id=test_user_id,
            name="Pytest Lifecycle Agent",
            description="Test agent for lifecycle testing",
            instructions="You are a helpful assistant created for pytest testing. Be concise.",
            model=bedrock_provider.get_default_model()
        )

        # Create agent
        agent = bedrock_provider.agents.create_or_update_agent_resource(
            agent_def=agent_def,
            owner_user_id=test_user_id
        )
        agent_id = agent.get_agent_id()

        try:
            # Verify agent was created
            assert agent_id is not None
            assert agent_id.startswith("bedrock_agent_")

            # Verify Bedrock-specific attributes
            assert hasattr(agent, 'bedrock_agent_id')
            assert hasattr(agent, 'bedrock_agent_alias_id')
            assert agent.bedrock_agent_id is not None
            assert agent.bedrock_agent_alias_id is not None

            # Verify we can retrieve the agent
            retrieved_agent = bedrock_provider.agents.get_agent(agent_id)
            assert retrieved_agent is not None
            assert retrieved_agent.get_agent_id() == agent_id
            assert retrieved_agent.get_name() == "Pytest Lifecycle Agent"

        finally:
            # Cleanup
            bedrock_provider.agents.delete_agent_resource(agent_id)

    def test_agent_name_uniqueness(self, bedrock_provider, test_user_id):
        """Test that multiple agents can have the same display name"""
        agents = []
        display_name = "Duplicate Name Agent"

        try:
            # Create 3 agents with the same display name
            for i in range(3):
                agent_def = AgentDefinition(
                    user_id=test_user_id,
                    name=display_name,
                    description=f"Test agent #{i+1}",
                    instructions="You are a helpful assistant.",
                    model=bedrock_provider.get_default_model()
                )

                agent = bedrock_provider.agents.create_or_update_agent(
                    agent_def=agent_def,
                    user_id=test_user_id
                )
                agents.append(agent.get_agent_id())

            # Verify all 3 were created successfully
            assert len(agents) == 3
            assert len(set(agents)) == 3  # All IDs are unique

            # Verify all have the same display name
            for agent_id in agents:
                agent = bedrock_provider.agents.get_agent(agent_id)
                assert agent.get_name() == display_name

        finally:
            # Cleanup
            for agent_id in agents:
                try:
                    bedrock_provider.agents.delete_agent(agent_id=agent_id)
                except:
                    pass


class TestBedrockConversation:
    """Test conversation functionality with context maintenance"""

    @pytest.fixture
    def conversation_agent(self, bedrock_provider, test_user_id):
        """Create an agent for conversation testing"""
        agent_def = AgentDefinition(
            user_id=test_user_id,
            name="Conversation Test Agent",
            description="Agent for testing conversations",
            instructions="You are a helpful AI assistant. Keep your responses concise.",
            model=bedrock_provider.get_default_model()
        )

        agent = bedrock_provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id=test_user_id
        )

        yield agent

        # Cleanup
        bedrock_provider.agents.delete_agent(agent_id=agent.get_agent_id())

    @pytest.fixture
    def conversation_thread(self, bedrock_provider, test_user_id):
        """Create a thread for conversation testing"""
        thread = bedrock_provider.threads.create_thread(
            user_id=test_user_id,
            name="Pytest Conversation Thread"
        )

        yield thread

        # Cleanup
        bedrock_provider.threads.delete_thread_resource(thread.thread_id)

    def test_basic_conversation(self, bedrock_provider, conversation_agent, conversation_thread):
        """Test basic question-answer conversation"""
        thread_id = conversation_thread.thread_id

        # Send first message
        response = ""
        for chunk in conversation_agent.stream_response(
            thread_id=thread_id,
            prompt="What is 2+2?"
        ):
            if not chunk.startswith('<') and not chunk.endswith('>'):
                response += chunk

        # Verify response
        assert "4" in response

        # Send follow-up
        response2 = ""
        for chunk in conversation_agent.stream_response(
            thread_id=thread_id,
            prompt="What's 10 times that?"
        ):
            if not chunk.startswith('<') and not chunk.endswith('>'):
                response2 += chunk

        # Verify response shows context was maintained
        assert "40" in response2

    def test_context_maintenance(self, bedrock_provider, conversation_agent, conversation_thread):
        """Test that conversation context is maintained across messages"""
        thread_id = conversation_thread.thread_id

        # First message - introduce a topic
        response1 = ""
        for chunk in conversation_agent.stream_response(
            thread_id=thread_id,
            prompt="My favorite color is blue and I love dolphins."
        ):
            if not chunk.startswith('<') and not chunk.endswith('>'):
                response1 += chunk

        # Second message - ask about previous information
        response2 = ""
        for chunk in conversation_agent.stream_response(
            thread_id=thread_id,
            prompt="What did I just tell you about?"
        ):
            if not chunk.startswith('<') and not chunk.endswith('>'):
                response2 += chunk

        # Verify context was maintained
        response2_lower = response2.lower()
        assert "blue" in response2_lower or "color" in response2_lower or "dolphin" in response2_lower

    def test_message_retrieval(self, bedrock_provider, conversation_agent, conversation_thread, test_user_id):
        """Test that messages are properly stored and retrievable"""
        thread_id = conversation_thread.thread_id

        # Send a few messages
        prompts = [
            "Hello, how are you?",
            "What's the weather like?",
            "Thank you!"
        ]

        for prompt in prompts:
            for chunk in conversation_agent.stream_response(thread_id=thread_id, prompt=prompt):
                pass  # Just consume the response

        # Retrieve messages
        messages = bedrock_provider.threads.get_messages(thread_id, limit=10)

        # Verify we have the expected number of messages (user + assistant for each prompt)
        assert len(messages) >= len(prompts) * 2

        # Verify message structure
        for msg_id, msg in messages.items():
            assert hasattr(msg, 'role')
            assert hasattr(msg, 'message_index')
            assert msg.role in ['user', 'assistant']


class TestBedrockStreaming:
    """Test streaming functionality"""

    def test_streaming_response_format(self, bedrock_provider, test_user_id):
        """Test that streaming responses use correct Bond message format"""
        # Create a simple agent
        agent_def = AgentDefinition(
            user_id=test_user_id,
            name="Streaming Test Agent",
            description="Agent for testing streaming",
            instructions="You are helpful. Be very brief.",
            model=bedrock_provider.get_default_model()
        )

        agent = bedrock_provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id=test_user_id
        )

        # Create thread
        thread = bedrock_provider.threads.create_thread(
            user_id=test_user_id,
            name="Streaming Test"
        )

        try:
            chunks = []
            for chunk in agent.stream_response(
                thread_id=thread.thread_id,
                prompt="Say 'Hello'"
            ):
                chunks.append(chunk)

            # Verify Bond message format
            assert any('<_bondmessage' in chunk for chunk in chunks)
            assert any('</_bondmessage>' in chunk for chunk in chunks)

            # Verify we got actual content
            content = ''.join(chunk for chunk in chunks if not chunk.startswith('<') and not chunk.endswith('>'))
            assert len(content) > 0

        finally:
            # Cleanup
            bedrock_provider.threads.delete_thread_resource(thread.thread_id)
            bedrock_provider.agents.delete_agent_resource(agent.get_agent_id())


class TestBedrockModels:
    """Test model-related functionality"""

    def test_get_available_models(self, bedrock_provider):
        """Test that we can retrieve available models"""
        models = bedrock_provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Check model structure
        for model in models:
            assert 'name' in model
            assert 'description' in model
            assert 'is_default' in model

        # Verify exactly one default model
        default_models = [m for m in models if m['is_default']]
        assert len(default_models) == 1

    def test_get_default_model(self, bedrock_provider):
        """Test that we can get the default model"""
        default_model = bedrock_provider.get_default_model()

        assert default_model is not None
        assert isinstance(default_model, str)
        assert len(default_model) > 0

        # Verify it matches the default in available models
        models = bedrock_provider.get_available_models()
        default_from_list = next((m['name'] for m in models if m['is_default']), None)
        assert default_model == default_from_list


@pytest.mark.parametrize("instruction_length", [
    ("short", "Talk like a pirate"),
    ("exact_40", "x" * 40),
    ("long", "You are a helpful AI assistant. Please provide detailed and accurate responses to questions.")
])
def test_instruction_padding(bedrock_provider, test_user_id, instruction_length):
    """Test that short instructions are properly padded"""
    instruction_text = instruction_length[1]

    agent_def = AgentDefinition(
        user_id=test_user_id,
        name=f"Instruction Test {instruction_length[0]}",
        description="Testing instruction padding",
        instructions=instruction_text,
        model=bedrock_provider.get_default_model()
    )

    agent = bedrock_provider.agents.create_or_update_agent(
        agent_def=agent_def,
        user_id=test_user_id
    )

    try:
        # Verify agent was created successfully
        assert agent is not None

        # Check stored instructions
        retrieved = bedrock_provider.agents.get_agent(agent.get_agent_id())
        stored_instructions = retrieved.system_prompt

        # Bedrock requires minimum 40 characters
        assert len(stored_instructions) >= 40

        # Original content should be preserved
        assert instruction_text in stored_instructions or instruction_text.strip() == stored_instructions.strip()

    finally:
        bedrock_provider.agents.delete_agent(agent_id=agent.get_agent_id())


# Run with: pytest tests/test_bedrock_provider_integration.py -v
