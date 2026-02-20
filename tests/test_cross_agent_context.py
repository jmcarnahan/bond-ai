#!/usr/bin/env python3
"""
Unit tests for cross-agent conversation history builder.

Tests the get_cross_agent_conversation_history() method in BedrockThreadsProvider
which builds Bedrock-format conversationHistory for multi-agent thread context sharing.

Bedrock requires conversationHistory to:
1. Start with a "user" message
2. Strictly alternate: user, assistant, user, assistant, ...
3. End with an "assistant" message (current user prompt is sent via inputText)
"""

import pytest
import datetime
from unittest.mock import MagicMock
from contextlib import contextmanager

from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
from bondable.bond.providers.bedrock.BedrockThreads import BedrockThreadsProvider


def make_message(message_index, role, msg_type, content, agent_id=None):
    """Helper to create a mock BedrockMessage."""
    msg = MagicMock(spec=BedrockMessage)
    msg.id = f"msg_{message_index}"
    msg.thread_id = "thread_test123"
    msg.user_id = "user_1"
    msg.session_id = "session_1"
    msg.role = role
    msg.type = msg_type
    msg.content = content
    msg.message_index = message_index
    msg.created_at = datetime.datetime(2026, 1, 1, 0, 0, message_index)
    msg.message_metadata = {"agent_id": agent_id} if agent_id else {}
    return msg


def setup_mock_session(threads_provider, messages):
    """Wire up a mock DB session returning the given messages."""
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = messages
    mock_session.query.return_value = mock_query

    @contextmanager
    def mock_context():
        yield mock_session

    threads_provider.metadata.get_db_session = mock_context


@pytest.fixture
def threads_provider():
    """Create a BedrockThreadsProvider with mocked dependencies."""
    mock_runtime = MagicMock()
    mock_provider = MagicMock()
    mock_metadata = MagicMock()
    provider = BedrockThreadsProvider(mock_runtime, mock_provider, mock_metadata)
    return provider


class TestGetCrossAgentConversationHistory:

    def test_returns_none_when_no_messages(self, threads_provider):
        """Should return None when thread has no messages."""
        setup_mock_session(threads_provider, [])
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_A"
        )
        assert result is None

    def test_returns_none_when_only_current_agent(self, threads_provider):
        """Should return None when only the current agent's messages exist."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Hi there"}], agent_id="agent_A"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_A"
        )
        assert result is None

    def test_returns_history_when_cross_agent_messages_exist(self, threads_provider):
        """Should return properly alternating history when other agents' messages exist."""
        messages = [
            make_message(0, "user", "text", [{"text": "What is your phrase?"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "PURPLE ELEPHANT 42"}], agent_id="agent_A"),
            make_message(2, "user", "text", [{"text": "What did the other agent say?"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Trailing user message is dropped (current prompt sent via inputText)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": [{"text": "What is your phrase?"}]}
        assert result[1] == {"role": "assistant", "content": [{"text": "PURPLE ELEPHANT 42"}]}

    def test_skips_leading_assistant_intro(self, threads_provider):
        """Should skip leading assistant messages (e.g. agent introduction/greeting)."""
        messages = [
            make_message(0, "assistant", "text", [{"text": "Hello! Welcome."}], agent_id="agent_A"),
            make_message(1, "user", "text", [{"text": "Create data"}], agent_id="agent_A"),
            make_message(2, "assistant", "text", [{"text": "Here is your data."}], agent_id="agent_A"),
            make_message(3, "user", "text", [{"text": "Analyze this"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Leading assistant dropped, trailing user dropped
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["text"] == "Create data"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"][0]["text"] == "Here is your data."

    def test_merges_consecutive_same_role_messages(self, threads_provider):
        """Should merge consecutive messages of the same role to enforce alternation."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Hi"}], agent_id="agent_A"),
            make_message(2, "assistant", "text", [{"text": "How can I help?"}], agent_id="agent_A"),
            make_message(3, "user", "text", [{"text": "Question"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Two consecutive assistant messages merged, trailing user dropped
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": [{"text": "Hello"}]}
        assert result[1]["role"] == "assistant"
        assert "Hi" in result[1]["content"][0]["text"]
        assert "How can I help?" in result[1]["content"][0]["text"]

    def test_ensures_alternation_starts_with_user(self, threads_provider):
        """Result must always start with user and alternate strictly."""
        messages = [
            make_message(0, "assistant", "text", [{"text": "Intro"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "More intro"}], agent_id="agent_A"),
            make_message(2, "user", "text", [{"text": "Hi"}], agent_id="agent_A"),
            make_message(3, "assistant", "text", [{"text": "Reply"}], agent_id="agent_A"),
            make_message(4, "user", "text", [{"text": "Next"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Verify strict alternation: user, assistant
        for i, msg in enumerate(result):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role, f"Message {i} should be {expected_role}, got {msg['role']}"
        # Should end with assistant
        assert result[-1]["role"] == "assistant"

    def test_respects_max_messages_limit(self, threads_provider):
        """Should only return the last N messages when exceeding max_messages."""
        messages = [
            make_message(i, "user" if i % 2 == 0 else "assistant", "text",
                        [{"text": f"Message {i}"}],
                        agent_id="agent_A" if i < 5 else "agent_B")
            for i in range(30)
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B",
            max_messages=10
        )
        assert result is not None
        assert len(result) <= 10
        # Must start with user
        assert result[0]["role"] == "user"
        # Must end with assistant
        assert result[-1]["role"] == "assistant"

    def test_truncates_long_messages(self, threads_provider):
        """Should truncate individual messages longer than 2000 chars."""
        long_text = "A" * 3000
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": long_text}], agent_id="agent_A"),
            make_message(2, "user", "text", [{"text": "What did they say?"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Trailing user dropped, so we get user + assistant
        assert len(result) == 2
        truncated = result[1]["content"][0]["text"]
        assert len(truncated) == 2003  # 2000 chars + "..."
        assert truncated.endswith("...")

    def test_skips_system_error_file_messages(self, threads_provider):
        """Should skip system, error, file_link, and image_file type messages."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Hi"}], agent_id="agent_A"),
            make_message(2, "assistant", "system", [{"text": "System msg"}], agent_id="agent_A"),
            make_message(3, "assistant", "error", [{"text": "Error msg"}], agent_id="agent_A"),
            make_message(4, "assistant", "file_link", [{"text": "file.pdf"}], agent_id="agent_A"),
            make_message(5, "assistant", "image_file", [{"text": "data:image/png;base64,abc"}], agent_id="agent_A"),
            make_message(6, "user", "text", [{"text": "Next question"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # user "Hello", assistant "Hi" (trailing user dropped)
        assert len(result) == 2
        assert result[0]["content"][0]["text"] == "Hello"
        assert result[1]["content"][0]["text"] == "Hi"

    def test_handles_string_content(self, threads_provider):
        """Should handle messages where content is a plain string."""
        messages = [
            make_message(0, "user", "text", "Hello from string", agent_id="agent_A"),
            make_message(1, "assistant", "text", "Reply as string", agent_id="agent_A"),
            make_message(2, "user", "text", "Next", agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        assert len(result) == 2
        assert result[0]["content"][0]["text"] == "Hello from string"
        assert result[1]["content"][0]["text"] == "Reply as string"

    def test_returns_none_on_database_error(self, threads_provider):
        """Should return None gracefully on database errors."""
        @contextmanager
        def mock_context():
            raise Exception("Database connection failed")
            yield  # noqa: unreachable

        threads_provider.metadata.get_db_session = mock_context
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_A"
        )
        assert result is None

    def test_skips_empty_text_messages(self, threads_provider):
        """Should skip messages with empty or whitespace-only text content."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": ""}], agent_id="agent_A"),
            make_message(2, "assistant", "text", [{"text": "   "}], agent_id="agent_A"),
            make_message(3, "assistant", "text", [{"text": "Real reply"}], agent_id="agent_A"),
            make_message(4, "user", "text", [{"text": "Question"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # user "Hello", assistant "Real reply" (empty skipped, trailing user dropped)
        assert len(result) == 2
        assert result[0]["content"][0]["text"] == "Hello"
        assert result[1]["content"][0]["text"] == "Real reply"

    def test_full_conversation_flow(self, threads_provider):
        """Should handle a realistic multi-agent conversation with proper alternation."""
        messages = [
            make_message(0, "user", "text", [{"text": "Tell me a joke"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Why did the chicken..."}], agent_id="agent_A"),
            make_message(2, "user", "text", [{"text": "That was funny!"}], agent_id="agent_A"),
            make_message(3, "assistant", "text", [{"text": "Glad you liked it"}], agent_id="agent_A"),
            make_message(4, "user", "text", [{"text": "What jokes were told earlier?"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # 4 messages (trailing user dropped)
        assert len(result) == 4
        roles = [m["role"] for m in result]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_messages_without_agent_id_not_considered_cross_agent(self, threads_provider):
        """Messages without agent_id in metadata should not trigger cross-agent detection."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id=None),
            make_message(1, "assistant", "text", [{"text": "Hi"}], agent_id="agent_A"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_A"
        )
        assert result is None

    def test_merged_messages_are_re_truncated(self, threads_provider):
        """After merging consecutive same-role messages, result should still be <= 2000 chars."""
        long_text_a = "A" * 1500
        long_text_b = "B" * 1500
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": long_text_a}], agent_id="agent_A"),
            make_message(2, "assistant", "text", [{"text": long_text_b}], agent_id="agent_A"),
            make_message(3, "user", "text", [{"text": "Question"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        merged_text = result[1]["content"][0]["text"]
        # 1500 + "\n\n" + 1500 = 3002 chars, should be truncated to 2003
        assert len(merged_text) == 2003
        assert merged_text.endswith("...")

    def test_max_messages_truncation_to_empty(self, threads_provider):
        """max_messages=1 with only a user message left should return None."""
        messages = [
            make_message(0, "user", "text", [{"text": "Hello"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Hi"}], agent_id="agent_A"),
            make_message(2, "user", "text", [{"text": "Next"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B",
            max_messages=1
        )
        # After dropping trailing user, we have [user, assistant] (2 items).
        # max_messages=1 keeps last 1: [assistant]. Leading assistant dropped -> empty -> None.
        assert result is None

    def test_realistic_ui_scenario_with_intro(self, threads_provider):
        """
        Reproduce the real UI scenario that caused the ValidationException:
        Agent A sends intro, user asks question, Agent A responds, then user
        switches to Agent B in the same thread.
        """
        messages = [
            # Agent A's auto-intro (system sends "greet the user" as user role)
            make_message(0, "user", "text", [{"text": "Greet the user with a brief welcome"}], agent_id="agent_A"),
            make_message(1, "assistant", "text", [{"text": "Hello! I'm here to help."}], agent_id="agent_A"),
            # User asks Agent A a real question
            make_message(2, "user", "text", [{"text": "Create some fake data"}], agent_id="agent_A"),
            make_message(3, "assistant", "text", [{"text": "Here is your fake data: ..."}], agent_id="agent_A"),
            # User switches to Agent B
            make_message(4, "user", "text", [{"text": "What is the average weight?"}], agent_id="agent_B"),
        ]
        setup_mock_session(threads_provider, messages)
        result = threads_provider.get_cross_agent_conversation_history(
            thread_id="thread_test123",
            current_agent_id="agent_B"
        )
        assert result is not None
        # Must start with user, alternate, end with assistant
        assert result[0]["role"] == "user"
        assert result[-1]["role"] == "assistant"
        for i in range(len(result) - 1):
            assert result[i]["role"] != result[i + 1]["role"], \
                f"Messages {i} and {i+1} have same role: {result[i]['role']}"
