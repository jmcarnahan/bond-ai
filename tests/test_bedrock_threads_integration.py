#!/usr/bin/env python3
"""
Integration test for Bedrock Threads - tests the actual Bond interface
with the Bedrock provider to ensure it works like the OpenAI provider would.

This simulates how the Bond system would actually use threads.
"""

import pytest
pytest.skip("Integration test: requires live AWS Bedrock for thread operations", allow_module_level=True)

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Force Bedrock provider
os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'

from bondable.bond.config import Config
from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider


def test_provider_setup():
    """Test that we can get the Bedrock provider"""
    print("=== Testing Provider Setup ===")

    # Get provider instance
    provider = BedrockProvider.provider()
    print(f"✓ Provider type: {type(provider).__name__}")
    print(f"✓ Provider info: {provider}")

    # Check it's actually Bedrock
    assert isinstance(provider, BedrockProvider), "Expected BedrockProvider"

    return provider


def test_thread_operations(provider):
    """Test thread operations through the provider interface"""
    print("\n=== Testing Thread Operations ===")

    threads = provider.threads

    # Create a thread
    print("\n1. Creating a new thread...")
    thread_id = threads.create_thread_resource()
    print(f"✓ Created thread: {thread_id}")
    assert thread_id.startswith('bedrock_thread_'), "Thread ID should have bedrock prefix"

    # Check if thread has messages (should be empty)
    print("\n2. Checking empty thread...")
    has_messages = threads.has_messages(thread_id, None)
    print(f"✓ Empty thread has messages: {has_messages}")
    assert not has_messages, "New thread should have no messages"

    # Get messages from empty thread
    messages = threads.get_messages(thread_id)
    print(f"✓ Messages in empty thread: {len(messages)}")
    assert len(messages) == 0, "New thread should have no messages"

    # Add a message (using the helper method)
    print("\n3. Adding a message...")
    if hasattr(threads, 'add_message'):
        msg_id = threads.add_message(
            thread_id=thread_id,
            user_id="test_user",
            role="user",
            content="Hello, this is a test message!"
        )
        print(f"✓ Added message: {msg_id}")

        # Check if thread now has messages
        has_messages = threads.has_messages(thread_id, None)
        print(f"✓ Thread now has messages: {has_messages}")
        assert has_messages, "Thread should have messages after adding one"

        # Get messages
        messages = threads.get_messages(thread_id)
        print(f"✓ Retrieved {len(messages)} messages")
        assert len(messages) == 1, "Should have exactly one message"

        # Check message content
        msg = list(messages.values())[0]
        print(f"✓ Message role: {msg.role}")
        print(f"✓ Message content: {msg.clob.content}")
        assert msg.role == "user"
        assert "test message" in msg.clob.content

        # Add assistant response
        print("\n4. Adding assistant response...")
        response_id = threads.add_message(
            thread_id=thread_id,
            user_id="test_user",
            role="assistant",
            content="Hello! I received your test message."
        )
        print(f"✓ Added assistant response: {response_id}")

        # Get all messages
        messages = threads.get_messages(thread_id)
        print(f"✓ Total messages: {len(messages)}")
        assert len(messages) == 2, "Should have two messages"

        # Check message ordering
        msg_list = sorted(messages.values(), key=lambda m: m.message_index)
        print(f"✓ First message role: {msg_list[0].role}")
        print(f"✓ Second message role: {msg_list[1].role}")
        assert msg_list[0].role == "user"
        assert msg_list[1].role == "assistant"
    else:
        print("⚠ add_message method not available - this is expected for base ThreadsProvider")

    # Delete thread
    print("\n5. Deleting thread...")
    success = threads.delete_thread_resource(thread_id)
    print(f"✓ Thread deleted: {success}")
    assert success, "Thread deletion should succeed"

    # Verify deletion
    messages = threads.get_messages(thread_id)
    print(f"✓ Messages after deletion: {len(messages)}")
    assert len(messages) == 0, "Deleted thread should have no messages"

    return True


def test_thread_message_continuity(provider):
    """Test that messages persist and can be retrieved correctly"""
    print("\n=== Testing Message Continuity ===")

    threads = provider.threads

    # Create thread and add messages
    thread_id = threads.create_thread_resource()
    print(f"✓ Created thread: {thread_id}")

    if hasattr(threads, 'add_message'):
        # Simulate a conversation
        messages_to_add = [
            ("user", "What is the capital of France?"),
            ("assistant", "The capital of France is Paris."),
            ("user", "What is its population?"),
            ("assistant", "The population of Paris is approximately 2.1 million people in the city proper."),
        ]

        message_ids = []
        for role, content in messages_to_add:
            msg_id = threads.add_message(
                thread_id=thread_id,
                user_id="test_user",
                role=role,
                content=content
            )
            message_ids.append(msg_id)
            print(f"✓ Added {role} message: {msg_id[:8]}...")

        # Test has_messages with last_message_id
        print("\n Testing message detection...")

        # Should have new messages after first message
        has_new = threads.has_messages(thread_id, message_ids[0])
        print(f"✓ Has messages after first message: {has_new}")
        assert has_new, "Should have new messages after first message"

        # Should not have new messages after last message
        has_new = threads.has_messages(thread_id, message_ids[-1])
        print(f"✓ Has messages after last message: {has_new}")
        assert not has_new, "Should not have new messages after last message"

        # Get conversation messages (if available)
         # TODO: this method was removed. Need to replace with get_messages()
        if hasattr(threads, 'get_conversation_messages'):
            convo = threads.get_conversation_messages(thread_id, "test_user")
            print(f"\n✓ Got {len(convo)} conversation messages")

            # Check format
            for i, msg in enumerate(convo):
                print(f"  Message {i+1}: {msg['role']} - {msg['content'][0]['text'][:50]}...")
                assert 'role' in msg
                assert 'content' in msg
                assert isinstance(msg['content'], list)

        # Cleanup
        threads.delete_thread_resource(thread_id)
        print("\n✓ Cleaned up test thread")
    else:
        print("⚠ add_message not available - skipping continuity test")

    return True


def test_config_integration():
    """Test that Bedrock provider is configured correctly"""
    print("\n=== Testing Configuration Integration ===")

    # Check that the provider class is set correctly
    provider_class = os.environ.get('BOND_PROVIDER_CLASS')
    print(f"✓ BOND_PROVIDER_CLASS: {provider_class}")
    assert 'BedrockProvider' in provider_class, "Should be configured to use BedrockProvider"

    # Get config and check it recognizes Bedrock
    config = Config.config()
    print(f"✓ Config instance created")

    return True


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("Bedrock Threads Integration Test")
    print("=" * 60)

    try:
        # Test provider setup
        provider = test_provider_setup()

        # Test thread operations
        test_thread_operations(provider)

        # Test message continuity
        test_thread_message_continuity(provider)

        # Test configuration integration
        test_config_integration()

        print("\n" + "=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60)
        print("\nThe Bedrock threads implementation is working correctly.")
        print("However, note that we still need to implement:")
        print("  - AgentProvider (Phase 2) for actual AI interactions")
        print("  - Message streaming support")
        print("  - File and vector store support")

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
