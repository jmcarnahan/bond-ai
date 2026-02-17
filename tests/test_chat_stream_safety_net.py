"""
Unit tests for the chat streaming safety net in bondable/rest/routers/chat.py.

Verifies that stream_response_generator() catches exceptions and always emits
a complete error bond message to the frontend, even when the agent's
stream_response() fails mid-stream. Also verifies content and done-signal
guarantees.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


def _simulate_stream_response_generator(
    agent_instance,
    thread_id="test-thread-123",
    agent_id="test-agent-456",
    prompt="Hello",
):
    """
    Reproduce the stream_response_generator logic from chat.py
    without needing FastAPI dependencies.
    """
    import uuid

    bond_message_open = False
    has_yielded_bond_message = False
    has_yielded_done = False
    has_yielded_assistant_content = False
    current_is_assistant = False
    try:
        for response_chunk in agent_instance.stream_response(
            thread_id=thread_id,
            prompt=prompt,
            attachments=[],
            override_role="user",
            current_user=None,
            jwt_token=None,
        ):
            if isinstance(response_chunk, str):
                if response_chunk.startswith('<_bondmessage '):
                    bond_message_open = True
                    has_yielded_bond_message = True
                    if 'is_done="true"' in response_chunk:
                        has_yielded_done = True
                    current_is_assistant = 'role="assistant"' in response_chunk
                elif response_chunk == '</_bondmessage>':
                    bond_message_open = False
                    current_is_assistant = False
                elif current_is_assistant and response_chunk.strip():
                    has_yielded_assistant_content = True
            yield response_chunk

        # Post-stream content guarantee
        if has_yielded_bond_message and not has_yielded_assistant_content and not has_yielded_done:
            if bond_message_open:
                yield '</_bondmessage>'
                bond_message_open = False
            fallback_id = str(uuid.uuid4())
            yield (
                f'<_bondmessage '
                f'id="{fallback_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{agent_id}" '
                f'type="error" '
                f'role="system" '
                f'is_error="true" '
                f'is_done="true">'
            )
            yield "The agent was unable to generate a response. Please try again."
            yield '</_bondmessage>'
            has_yielded_done = True

        # Post-stream done guarantee
        if has_yielded_bond_message and not has_yielded_done:
            if bond_message_open:
                yield '</_bondmessage>'
                bond_message_open = False
            done_id = str(uuid.uuid4())
            yield (
                f'<_bondmessage '
                f'id="{done_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{agent_id}" '
                f'type="text" '
                f'role="system" '
                f'is_error="false" '
                f'is_done="true">'
            )
            yield "Done."
            yield '</_bondmessage>'

    except Exception as e:
        try:
            if bond_message_open:
                yield '</_bondmessage>'

            error_type = type(e).__name__
            error_detail = str(e)
            if len(error_detail) > 300:
                error_detail = error_detail[:300] + "..."
            user_error_msg = (
                f"An unexpected error occurred while processing your request "
                f"({error_type}: {error_detail}). Please try again."
            )

            error_id = str(uuid.uuid4())
            yield (
                f'<_bondmessage '
                f'id="{error_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{agent_id}" '
                f'type="error" '
                f'role="system" '
                f'is_error="true" '
                f'is_done="true">'
            )
            yield user_error_msg
            yield '</_bondmessage>'
        except Exception as inner_e:
            try:
                yield (
                    '<_bondmessage '
                    'id="error-fallback" '
                    f'thread_id="{thread_id or "unknown"}" '
                    f'agent_id="{agent_id or "unknown"}" '
                    'type="error" '
                    'role="system" '
                    'is_error="true" '
                    'is_done="true">'
                )
                yield "An internal error occurred. Please try again."
                yield '</_bondmessage>'
            except Exception:
                pass


class TestStreamSafetyNetNoContent:
    """Tests where the exception occurs before any content is yielded."""

    def test_immediate_exception_yields_error_bond_message(self):
        """If stream_response raises immediately, should yield complete error message."""
        agent = MagicMock()
        agent.stream_response.side_effect = RuntimeError("Connection refused")

        results = list(_simulate_stream_response_generator(agent))

        # Should have: open tag, error text, close tag
        assert len(results) == 3
        assert results[0].startswith('<_bondmessage ')
        assert 'type="error"' in results[0]
        assert 'is_error="true"' in results[0]
        assert 'is_done="true"' in results[0]
        assert "RuntimeError" in results[1]
        assert "Connection refused" in results[1]
        assert results[2] == '</_bondmessage>'

    def test_immediate_exception_includes_thread_and_agent_ids(self):
        """Error bond message should include correct thread_id and agent_id."""
        agent = MagicMock()
        agent.stream_response.side_effect = ValueError("Bad input")

        results = list(_simulate_stream_response_generator(
            agent,
            thread_id="my-thread",
            agent_id="my-agent",
        ))

        open_tag = results[0]
        assert 'thread_id="my-thread"' in open_tag
        assert 'agent_id="my-agent"' in open_tag

    def test_long_error_message_is_truncated(self):
        """Error details longer than 300 chars should be truncated."""
        agent = MagicMock()
        long_message = "x" * 500
        agent.stream_response.side_effect = RuntimeError(long_message)

        results = list(_simulate_stream_response_generator(agent))

        error_text = results[1]
        # Should be truncated with "..."
        assert "..." in error_text
        # Should not contain the full 500-char message
        assert long_message not in error_text


class TestStreamSafetyNetMidStream:
    """Tests where the exception occurs after some content has been yielded."""

    def test_exception_after_open_tag_closes_it(self):
        """If bond message is open when exception occurs, should close it first."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Some partial content"
            raise RuntimeError("Mid-stream failure")

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Should have: open tag, partial content, close tag (for open msg),
        # error open tag, error text, error close tag
        assert len(results) == 6
        assert results[0].startswith('<_bondmessage ')
        assert results[1] == "Some partial content"
        assert results[2] == '</_bondmessage>'  # Closes the interrupted message
        assert 'type="error"' in results[3]  # Error message open tag
        assert "RuntimeError" in results[4]
        assert "Mid-stream failure" in results[4]
        assert results[5] == '</_bondmessage>'  # Closes error message

    def test_exception_after_closed_tag_does_not_double_close(self):
        """If bond message was already closed, should not emit extra close tag."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Complete content"
            yield '</_bondmessage>'
            raise RuntimeError("After-close failure")

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Should have: open tag, content, close tag, error open tag, error text, error close tag
        # (NO extra close tag between close and error open)
        assert len(results) == 6
        assert results[0].startswith('<_bondmessage ')
        assert results[1] == "Complete content"
        assert results[2] == '</_bondmessage>'  # Original close
        assert 'type="error"' in results[3]  # Error message (no extra close before this)
        assert results[5] == '</_bondmessage>'

    def test_exception_preserves_all_earlier_content(self):
        """All content yielded before the exception should be preserved."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "First chunk. "
            yield "Second chunk. "
            yield "Third chunk."
            raise RuntimeError("Late failure")

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        text_chunks = [r for r in results if not r.startswith('<')]
        assert "First chunk. " in text_chunks
        assert "Second chunk. " in text_chunks
        assert "Third chunk." in text_chunks


class TestStreamSafetyNetNormalFlow:
    """Tests that the safety net does not interfere with normal operation."""

    def test_successful_stream_with_done_passes_through_unchanged(self):
        """Stream with content and is_done should pass through without modifications."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Hello world"
            yield '</_bondmessage>'
            yield '<_bondmessage id="-1" thread_id="t" agent_id="a" type="text" role="system" is_error="false" is_done="true">'
            yield "Done."
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        assert len(results) == 6
        assert results[1] == "Hello world"
        assert results[4] == "Done."

    def test_successful_stream_without_done_gets_done_appended(self):
        """Stream with assistant content but no is_done gets a done message appended."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Hello world"
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 3 + done open tag + "Done." + done close tag = 6
        assert len(results) == 6
        assert results[0].startswith('<_bondmessage ')
        assert results[1] == "Hello world"
        assert results[2] == '</_bondmessage>'
        # Synthetic done message
        assert 'is_done="true"' in results[3]
        assert 'is_error="false"' in results[3]
        assert 'role="system"' in results[3]
        assert results[4] == "Done."
        assert results[5] == '</_bondmessage>'

    def test_empty_stream_does_not_produce_error(self):
        """An empty stream (no yields) should not trigger the error path."""
        def mock_stream(**kwargs):
            return
            yield  # Make it a generator

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Should be empty - no bond messages means no guarantees triggered
        assert len(results) == 0

    def test_multiple_bond_messages_tracked_correctly(self):
        """Multiple open/close cycles should track state correctly."""
        def mock_stream(**kwargs):
            # First message
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "First message"
            yield '</_bondmessage>'
            # Second message
            yield '<_bondmessage id="msg-2" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Second message"
            # Exception while second message is open
            raise RuntimeError("Fail during second message")

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # First message complete (3), second message interrupted (2), close tag (1),
        # error message (3) = 9 total
        assert len(results) == 9
        # The interrupted second message should be closed
        assert results[5] == '</_bondmessage>'  # Closes interrupted second message
        assert 'type="error"' in results[6]  # Error message follows


class TestStreamSafetyNetExceptionTypes:
    """Tests that various exception types are handled correctly."""

    def test_keyboard_interrupt_not_caught(self):
        """KeyboardInterrupt should not be caught (it's BaseException, not Exception)."""
        agent = MagicMock()
        agent.stream_response.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            list(_simulate_stream_response_generator(agent))

    def test_client_error_includes_details(self):
        """AWS ClientError should have its details in the error message."""
        from botocore.exceptions import ClientError

        agent = MagicMock()
        agent.stream_response.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeAgent"
        )

        results = list(_simulate_stream_response_generator(agent))

        error_text = results[1]
        assert "ClientError" in error_text
        assert "ThrottlingException" in error_text


class TestStreamContentGuarantee:
    """Tests that the frontend always gets visible content when bond messages are sent."""

    def test_empty_assistant_message_gets_fallback(self):
        """Bond messages with no assistant text content should trigger fallback."""
        def mock_stream(**kwargs):
            # Open and close an assistant message with no text between
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 2 + fallback (open tag + text + close tag) = 5
        assert len(results) == 5
        assert results[0].startswith('<_bondmessage ')
        assert results[1] == '</_bondmessage>'
        # Fallback error message
        assert 'type="error"' in results[2]
        assert 'is_error="true"' in results[2]
        assert 'is_done="true"' in results[2]
        assert "unable to generate a response" in results[3]
        assert results[4] == '</_bondmessage>'

    def test_whitespace_only_assistant_content_gets_fallback(self):
        """Assistant message with only whitespace should trigger fallback."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "   \n  "
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 3 + fallback (3) = 6
        assert len(results) == 6
        assert "unable to generate a response" in results[4]

    def test_non_empty_assistant_message_no_fallback(self):
        """Assistant message with real content should not trigger fallback."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Hello, I can help!"
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 3 + done message (3) = 6 (done guarantee kicks in, not content fallback)
        assert len(results) == 6
        # No error fallback - the appended message should be the done signal, not an error
        assert 'is_error="false"' in results[3]
        assert 'is_done="true"' in results[3]
        assert results[4] == "Done."

    def test_system_only_messages_get_fallback(self):
        """Stream with only system messages and no assistant content gets fallback."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="system" is_error="false" is_done="false">'
            yield "Processing..."
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 3 + fallback error (3) = 6
        assert len(results) == 6
        assert 'is_error="true"' in results[3]
        assert "unable to generate a response" in results[4]

    def test_content_fallback_includes_done_signal(self):
        """The content fallback message should have is_done=true."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Find the error tag
        error_tags = [r for r in results if isinstance(r, str) and 'is_done="true"' in r]
        assert len(error_tags) == 1
        assert 'is_error="true"' in error_tags[0]

    def test_no_fallback_when_agent_already_sent_done_with_content(self):
        """If agent sent is_done with no assistant content, done is already present, no content fallback needed since done was sent."""
        def mock_stream(**kwargs):
            # Agent sends a done message directly without assistant content
            yield '<_bondmessage id="-1" thread_id="t" agent_id="a" type="text" role="system" is_error="false" is_done="true">'
            yield "Done."
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Only the original 3 chunks - done was already sent, content fallback
        # condition checks `not has_yielded_done` which is True here
        assert len(results) == 3


class TestStreamDoneGuarantee:
    """Tests that a done message is always emitted when bond content is yielded."""

    def test_done_message_emitted_when_agent_forgets(self):
        """If agent yields content but no is_done message, safety net adds one."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Hello world"
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Original 3 + done (open tag + "Done." + close tag) = 6
        assert len(results) == 6
        assert 'is_done="true"' in results[3]
        assert 'is_error="false"' in results[3]
        assert 'type="text"' in results[3]
        assert 'role="system"' in results[3]
        assert results[4] == "Done."
        assert results[5] == '</_bondmessage>'

    def test_done_message_not_duplicated_when_agent_sends_it(self):
        """If agent already yields is_done message, safety net should not add another."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Hello world"
            yield '</_bondmessage>'
            yield '<_bondmessage id="msg-done" thread_id="t" agent_id="a" type="text" role="system" is_error="false" is_done="true">'
            yield "Done."
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Should be exactly the 6 chunks from the agent, no extras
        assert len(results) == 6
        # Only one is_done="true" message
        done_count = sum(1 for r in results if isinstance(r, str) and 'is_done="true"' in r)
        assert done_count == 1

    def test_done_not_emitted_for_empty_stream(self):
        """Empty stream should not get a synthetic done message."""
        def mock_stream(**kwargs):
            return
            yield

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))
        assert len(results) == 0

    def test_done_not_emitted_for_raw_text_stream(self):
        """Raw text without bond message tags should not trigger done guarantee."""
        def mock_stream(**kwargs):
            yield "Hello "
            yield "world!"

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(agent))

        # Just the 2 raw text chunks, no done message appended
        assert len(results) == 2
        assert results[0] == "Hello "
        assert results[1] == "world!"

    def test_done_includes_correct_thread_and_agent_ids(self):
        """Synthetic done message should include the correct thread_id and agent_id."""
        def mock_stream(**kwargs):
            yield '<_bondmessage id="msg-1" thread_id="t" agent_id="a" type="text" role="assistant" is_error="false" is_done="false">'
            yield "Content"
            yield '</_bondmessage>'

        agent = MagicMock()
        agent.stream_response.side_effect = mock_stream

        results = list(_simulate_stream_response_generator(
            agent,
            thread_id="thread-xyz",
            agent_id="agent-abc",
        ))

        done_tag = results[3]
        assert 'thread_id="thread-xyz"' in done_tag
        assert 'agent_id="agent-abc"' in done_tag


class TestStreamDoubleExceptFallback:
    """Tests that the fallback handles error-handler failures."""

    def test_fallback_when_uuid_fails_in_error_handler(self):
        """If uuid.uuid4 raises during error handling, the fallback should still yield."""
        agent = MagicMock()
        agent.stream_response.side_effect = RuntimeError("Original error")

        call_count = [0]
        original_uuid4 = __import__('uuid').uuid4

        def failing_uuid4():
            call_count[0] += 1
            # Fail on the first call (the one in the error handler)
            if call_count[0] == 1:
                raise RuntimeError("uuid4 broken")
            return original_uuid4()

        with patch('uuid.uuid4', side_effect=failing_uuid4):
            results = list(_simulate_stream_response_generator(agent))

        # Should get the fallback message
        assert len(results) == 3
        assert 'id="error-fallback"' in results[0]
        assert 'is_error="true"' in results[0]
        assert 'is_done="true"' in results[0]
        assert "An internal error occurred" in results[1]
        assert results[2] == '</_bondmessage>'
