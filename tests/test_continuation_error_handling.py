"""
Unit tests for _handle_continuation_response error handling in BedrockAgent.

Tests that continuation stream errors (EventStreamError, invoke_agent failures,
generic exceptions) are caught and yield user-visible error messages instead of
crashing silently or hanging.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from botocore.exceptions import EventStreamError, ClientError, ReadTimeoutError
from urllib3.exceptions import ReadTimeoutError as Urllib3ReadTimeoutError


def _make_agent():
    """Create a minimal BedrockAgent instance with mocked dependencies."""
    from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent

    agent = object.__new__(BedrockAgent)
    agent.bedrock_agent_id = "test-agent-id"
    agent.bedrock_agent_alias_id = "test-alias-id"
    agent.bond_provider = MagicMock()
    agent._current_user = None
    agent._jwt_token = None
    return agent


def _make_return_control(invocation_id="inv-123"):
    """Create a minimal returnControl event."""
    return {
        "invocationId": invocation_id,
        "invocationInputs": [
            {
                "apiInvocationInput": {
                    "actionGroupName": "test-action-group",
                    "apiPath": "/b.abc123.jira_search",
                    "httpMethod": "POST",
                    "parameters": [
                        {"name": "jql", "value": "project = TEST"}
                    ]
                }
            }
        ]
    }


def _make_tool_results():
    """Create tool results as _handle_return_control would return."""
    return [
        {
            "apiResult": {
                "actionGroup": "test-action-group",
                "apiPath": "/b.abc123.jira_search",
                "httpMethod": "POST",
                "httpStatusCode": 200,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps({"result": "some data"})
                    }
                }
            }
        }
    ]


def _make_error_tool_results():
    """Create tool results with a 500 error status."""
    return [
        {
            "apiResult": {
                "actionGroup": "test-action-group",
                "apiPath": "/b.abc123.jira_search",
                "httpMethod": "POST",
                "httpStatusCode": 500,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps({"error": "Tool execution failed"})
                    }
                }
            }
        }
    ]


class TestContinuationInvokeAgentFailure:
    """Tests for when invoke_agent fails during continuation."""

    def test_invoke_agent_exception_yields_error_message(self):
        """When invoke_agent raises an exception, should yield error message, not crash."""
        agent = _make_agent()

        # Mock _handle_return_control to return successful tool results
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        # Mock invoke_agent to raise an exception
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = (
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                "InvokeAgent"
            )
        )

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        # Should yield an error message string (not crash)
        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield at least one error message"
        assert any("error" in r.lower() for r in text_results), \
            f"Error message should mention 'error': {text_results}"

    def test_invoke_agent_generic_exception_yields_error_message(self):
        """Generic exceptions from invoke_agent should also be caught."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = (
            RuntimeError("Connection reset")
        )

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message for generic exception"


class TestContinuationStreamErrors:
    """Tests for errors during continuation stream iteration."""

    def test_event_stream_error_yields_error_message(self):
        """EventStreamError (e.g. dependencyFailedException) should be caught."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_error_tool_results())

        # Mock invoke_agent to return a stream that raises EventStreamError
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {
                "Error": {
                    "Code": "dependencyFailedException",
                    "Message": "POST:500:FAILURE:{\"result\": \"Tool execution failed\"}"
                }
            },
            "InvokeAgent"
        ))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message for EventStreamError"
        assert any("error" in r.lower() for r in text_results), \
            f"Should mention error: {text_results}"

    def test_event_stream_error_mid_stream_preserves_earlier_content(self):
        """If EventStreamError occurs after some chunks, earlier content should be preserved."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Here is some text")

        # Create a stream that yields one chunk then raises
        def stream_events():
            yield {"chunk": {"bytes": b"some data"}}
            raise EventStreamError(
                {
                    "Error": {
                        "Code": "dependencyFailedException",
                        "Message": "Failure"
                    }
                },
                "InvokeAgent"
            )

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=stream_events)

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        # Should have both the content chunk and the error message
        assert len(text_results) >= 2, f"Should have content + error, got: {text_results}"
        assert "Here is some text" in text_results[0]
        assert any("error" in r.lower() for r in text_results)

    def test_generic_exception_in_stream_yields_error_message(self):
        """Generic exceptions during stream iteration should also be caught."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=RuntimeError("Unexpected stream failure"))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message for generic stream exception"

    def test_botocore_read_timeout_yields_timeout_specific_message(self):
        """botocore ReadTimeoutError should yield a timeout-specific user message."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=ReadTimeoutError(
            endpoint_url="https://bedrock-agent-runtime.us-west-2.amazonaws.com"
        ))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message for botocore ReadTimeoutError"
        assert any("timed out" in r.lower() for r in text_results), \
            f"Should mention timeout specifically: {text_results}"

    def test_urllib3_read_timeout_yields_timeout_specific_message(self):
        """urllib3 ReadTimeoutError (the actual exception from streaming) should also be caught."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        # This is the actual exception type raised during event stream iteration
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=Urllib3ReadTimeoutError(
            pool="test-pool", url=None, message="Read timed out."
        ))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message for urllib3 ReadTimeoutError"
        assert any("timed out" in r.lower() for r in text_results), \
            f"Should mention timeout specifically: {text_results}"


class TestContinuationStreamRetry:
    """Tests for EventStreamError retry logic in _handle_continuation_response."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_event_stream_error_retried_then_succeeds(self, mock_sleep):
        """EventStreamError with no content yielded → retry succeeds on second attempt."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Success after retry")

        # First stream: raises EventStreamError immediately (no content yielded)
        failing_stream = MagicMock()
        failing_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {
                "Error": {
                    "Code": "dependencyFailedException",
                    "Message": "Dependency resource: bedrock failed to process."
                }
            },
            "InvokeAgent"
        ))

        # Second stream: succeeds with a text chunk
        success_events = [
            {"chunk": {"bytes": b"success data"}},
            {"sessionState": {"some": "state"}}
        ]

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = [
            {"completion": failing_stream},
            {"completion": iter(success_events)},
        ]

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert any("Success after retry" in r for r in text_results), \
            f"Should contain success text from retry: {text_results}"
        # No error message should be present
        assert not any("error" in r.lower() for r in text_results), \
            f"Should NOT have error message after successful retry: {text_results}"
        # invoke_agent called exactly 2 times (original + 1 retry)
        assert agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.call_count == 2
        # sleep called once for the retry delay
        assert mock_sleep.call_count >= 1

    def test_event_stream_error_with_content_yielded_no_retry(self):
        """Stream yields text chunk then EventStreamError → no retry."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Partial content")

        # Stream yields one chunk then raises
        def stream_events():
            yield {"chunk": {"bytes": b"data"}}
            raise EventStreamError(
                {
                    "Error": {
                        "Code": "dependencyFailedException",
                        "Message": "Failure after content"
                    }
                },
                "InvokeAgent"
            )

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=stream_events)

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        # Should have the partial content and an error message
        assert any("Partial content" in r for r in text_results)
        assert any("error" in r.lower() for r in text_results)
        # Should NOT have retried - only 1 invoke_agent call
        assert agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.call_count == 1

    def test_event_stream_error_with_file_yielded_no_retry(self):
        """Stream yields files_event then EventStreamError → no retry (file already sent)."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        # Stream yields a files event then raises
        def stream_events():
            yield {"files": {"files": [{"name": "test.pdf", "bytes": b"data"}]}}
            raise EventStreamError(
                {
                    "Error": {
                        "Code": "dependencyFailedException",
                        "Message": "Failure after file"
                    }
                },
                "InvokeAgent"
            )

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=stream_events)

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        dict_results = [r for r in results if isinstance(r, dict)]
        # Should have yielded the file event
        assert any('files_event' in r for r in dict_results), \
            f"Should have yielded files_event: {dict_results}"
        # Should have error message (no retry due to file yield)
        assert any("error" in r.lower() for r in text_results), \
            f"Should have error message: {text_results}"
        # Should NOT have retried - only 1 invoke_agent call
        assert agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.call_count == 1

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_event_stream_error_all_retries_exhausted(self, mock_sleep):
        """EventStreamError on all attempts → error message after exhausting retries."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        # All streams raise EventStreamError
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {
                "Error": {
                    "Code": "dependencyFailedException",
                    "Message": "Persistent failure"
                }
            },
            "InvokeAgent"
        ))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": mock_stream
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0, "Should yield error message after exhausting retries"
        assert any("transient error" in r.lower() for r in text_results), \
            f"Should mention transient error: {text_results}"
        # invoke_agent called 2 times (1 original + 1 retry = MAX_STREAM_RETRIES + 1)
        assert agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.call_count == 2

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_stream_retry_uses_exponential_backoff(self, mock_sleep):
        """Assert time.sleep called with correct delay value on stream retry."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Success")

        # First stream fails, second succeeds
        failing_stream = MagicMock()
        failing_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {
                "Error": {
                    "Code": "dependencyFailedException",
                    "Message": "Transient"
                }
            },
            "InvokeAgent"
        ))

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = [
            {"completion": failing_stream},
            {"completion": iter([{"chunk": {"bytes": b"ok"}}])},
        ]

        return_control = _make_return_control()
        list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        # Verify exponential backoff: INVOKE_RETRY_BASE_DELAY * (2 ** stream_attempt)
        # stream_attempt=0, so delay = 1.0 * (2 ** 0) = 1.0
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert 1.0 in sleep_calls, \
            f"Should have slept for 1.0s on first stream retry, got: {sleep_calls}"

    def test_stream_retry_with_nested_return_control_before_error(self):
        """Stream yields returnControl (nested tool call) then errors → no retry."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Nested text")

        nested_return_control = _make_return_control(invocation_id="inv-nested")

        # Depth-0 stream: yields returnControl then raises
        def depth0_events():
            yield {"returnControl": nested_return_control}
            raise EventStreamError(
                {
                    "Error": {
                        "Code": "dependencyFailedException",
                        "Message": "Failure after nested"
                    }
                },
                "InvokeAgent"
            )

        # Depth-1 stream: succeeds with text
        depth1_stream = iter([
            {"chunk": {"bytes": b"nested data"}},
            {"sessionState": {"some": "state"}}
        ])

        call_count = [0]
        def mock_invoke_agent(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (depth=0): stream with returnControl then error
                mock_stream = MagicMock()
                mock_stream.__iter__ = MagicMock(side_effect=depth0_events)
                return {"completion": mock_stream}
            elif call_count[0] == 2:
                # Second call (depth=1 nested): succeeds
                return {"completion": depth1_stream}
            else:
                # Should not be called again (no retry since nested yielded content)
                return {"completion": iter([])}

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = mock_invoke_agent

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        # Should have the nested text and an error (no retry because content was yielded)
        assert any("Nested text" in r for r in text_results), \
            f"Should have nested text: {text_results}"
        assert any("error" in r.lower() for r in text_results), \
            f"Should have error message (no retry): {text_results}"
        # invoke_agent called exactly 2 times (depth=0 + depth=1 nested, no retry)
        assert call_count[0] == 2, \
            f"Should have 2 invoke_agent calls (no retry), got: {call_count[0]}"


class TestContinuationNormalFlow:
    """Tests that normal continuation flow still works with the new error handling."""

    def test_successful_continuation_yields_text(self):
        """Normal flow: tool result → continuation → chunk events → text yielded."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="The answer is 42")

        # Create a stream with chunk events
        mock_stream = [
            {"chunk": {"bytes": b"chunk data"}},
            {"sessionState": {"some": "state"}}
        ]

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": iter(mock_stream)
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        dict_results = [r for r in results if isinstance(r, dict)]

        assert "The answer is 42" in text_results
        assert any(r.get("session_state") for r in dict_results), \
            "Should yield session state"

    def test_empty_continuation_stream_does_not_crash(self):
        """If continuation stream is empty (no events), should not crash."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {
            "completion": iter([])
        }

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        # Should complete without error (may have no text results)
        # The important thing is it doesn't hang or crash
        assert isinstance(results, list)

    def test_no_completion_stream_does_not_crash(self):
        """If invoke_agent response has no 'completion' key, should not crash."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.return_value = {}

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        assert isinstance(results, list)


class TestContinuationNestedReturnControl:
    """Tests for nested returnControl handling with error paths."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_nested_event_stream_error_caught_at_depth(self, mock_sleep):
        """EventStreamError at depth=1 should be caught and yield error message.

        The depth-1 handler has its own independent retry loop (any_content_yielded=False
        at depth=1), so it retries once before exhausting MAX_STREAM_RETRIES.
        Total invoke_agent calls: 1 (depth=0) + 2 (depth=1 original + retry) = 3.
        """
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Some initial text")

        # Depth-0 continuation stream: one chunk, then nested returnControl
        nested_return_control = _make_return_control(invocation_id="inv-nested")

        depth0_events = [
            {"chunk": {"bytes": b"data"}},
            {"returnControl": nested_return_control},
        ]

        # Depth-1 continuation: always raises EventStreamError (fails on both
        # the original attempt and the retry at depth=1)
        depth1_stream = MagicMock()
        depth1_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {
                "Error": {
                    "Code": "dependencyFailedException",
                    "Message": "Failure at depth 1"
                }
            },
            "InvokeAgent"
        ))

        call_count = [0]

        def mock_invoke_agent(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (depth=0): return stream with chunk + nested returnControl
                return {"completion": iter(depth0_events)}
            else:
                # All subsequent calls (depth=1 original + depth=1 retry): return erroring stream
                return {"completion": depth1_stream}

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = mock_invoke_agent

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        text_results = [r for r in results if isinstance(r, str)]
        # Should have the initial text from depth-0 and an error from depth-1
        assert any("Some initial text" in r for r in text_results), \
            f"Should preserve depth-0 text: {text_results}"
        assert any("error" in r.lower() for r in text_results), \
            f"Should have error message from depth-1: {text_results}"
        # 3 invoke_agent calls: 1 for depth=0, 2 for depth=1 (original + stream retry)
        assert call_count[0] == 3, \
            f"Expected 3 invoke_agent calls (depth=0 + depth=1 with retry), got: {call_count[0]}"

    def test_depth_limit_exceeded_yields_error(self):
        """Exceeding MAX_TOOL_CALL_DEPTH should yield error, not recurse infinitely."""
        agent = _make_agent()

        return_control = _make_return_control()
        results = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=agent.MAX_TOOL_CALL_DEPTH  # At the limit
        ))

        text_results = [r for r in results if isinstance(r, str)]
        assert len(text_results) > 0
        assert any("maximum tool call depth" in r.lower() for r in text_results)
