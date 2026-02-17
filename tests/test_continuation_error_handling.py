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

    def test_nested_event_stream_error_caught_at_depth(self):
        """EventStreamError at depth=1 should be caught and yield error message."""
        agent = _make_agent()

        agent._handle_return_control = MagicMock(return_value=_make_tool_results())
        agent._handle_chunk_event = MagicMock(return_value="Some initial text")

        # Depth-0 continuation stream: one chunk, then nested returnControl
        nested_return_control = _make_return_control(invocation_id="inv-nested")

        depth0_events = [
            {"chunk": {"bytes": b"data"}},
            {"returnControl": nested_return_control},
        ]

        # Depth-1 continuation: raises EventStreamError
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
                # Second call (depth=1): return stream that errors
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
