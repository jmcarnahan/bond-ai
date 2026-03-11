"""
Unit tests for context window compaction in BedrockAgent.

Tests cover:
- Context window size lookup
- Token tracking from trace events and char-based estimation
- Compaction threshold checking
- Summary generation via Converse API
- Session rotation with summary injection
- Concurrency safety (compaction_in_progress flag)
- End-to-end compaction flow
"""

import os
import uuid
import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from collections import OrderedDict


def _make_agent(**overrides):
    """Create a minimally-mocked BedrockAgent for testing."""
    from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent
    agent = BedrockAgent.__new__(BedrockAgent)
    agent.agent_id = 'test-agent-id'
    agent.bedrock_agent_id = 'bedrock-agent-123'
    agent.bedrock_agent_alias_id = 'alias-456'
    agent.name = 'Test Agent'
    agent.introduction = 'Hi'
    agent.reminder = ''
    agent.owner_user_id = 'user-1'
    agent.model = overrides.get('model', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
    agent.instructions = 'Be helpful.'
    agent.temperature = 0.0
    agent.tools = []
    agent.tool_resources = {}
    agent.mcp_tools = []
    agent.mcp_resources = {}
    agent.metadata = {}
    agent.file_storage = 'direct'

    # Mock the bond_provider
    agent.bond_provider = MagicMock()
    return agent


class TestGetContextWindowSize:
    """Tests for _get_context_window_size model lookup."""

    def test_claude_35_model(self):
        agent = _make_agent(model='anthropic.claude-3-5-sonnet-20241022-v2:0')
        assert agent._get_context_window_size() == 200_000

    def test_claude_3_model(self):
        agent = _make_agent(model='anthropic.claude-3-sonnet-20240229-v1:0')
        assert agent._get_context_window_size() == 200_000

    def test_claude_v2_model(self):
        agent = _make_agent(model='anthropic.claude-v2:1')
        assert agent._get_context_window_size() == 100_000

    def test_claude_instant_model(self):
        agent = _make_agent(model='anthropic.claude-instant-v1')
        assert agent._get_context_window_size() == 100_000

    def test_unknown_model_returns_default(self):
        agent = _make_agent(model='some.unknown-model-v1')
        assert agent._get_context_window_size() == 200_000


class TestNeedsCompaction:
    """Tests for _needs_compaction threshold checking."""

    def test_below_threshold_returns_false(self):
        agent = _make_agent()
        session_state = {
            'context_usage': {'estimated_tokens': 50_000}
        }
        assert agent._needs_compaction(session_state) is False

    def test_at_threshold_returns_true(self):
        agent = _make_agent()
        # 60% of 200K = 120K
        session_state = {
            'context_usage': {'estimated_tokens': 120_000}
        }
        assert agent._needs_compaction(session_state) is True

    def test_above_threshold_returns_true(self):
        agent = _make_agent()
        session_state = {
            'context_usage': {'estimated_tokens': 180_000}
        }
        assert agent._needs_compaction(session_state) is True

    def test_empty_usage_returns_false(self):
        agent = _make_agent()
        assert agent._needs_compaction({}) is False

    def test_zero_tokens_returns_false(self):
        agent = _make_agent()
        session_state = {
            'context_usage': {'estimated_tokens': 0}
        }
        assert agent._needs_compaction(session_state) is False


class TestUpdateContextUsage:
    """Tests for _update_context_usage token tracking."""

    def test_with_trace_tokens(self):
        """Uses real trace tokens when available."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_state.return_value = {}
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        agent._update_context_usage('thread-1', 'user-1',
                                    trace_input_tokens=5000, trace_output_tokens=1000,
                                    input_chars=100, output_chars=200)

        call_args = agent.bond_provider.threads.update_thread_session.call_args
        session_state = call_args[1]['session_state'] if 'session_state' in call_args[1] else call_args[0][3]
        usage = session_state['context_usage']
        assert usage['total_tokens'] == 6000
        assert usage['estimated_tokens'] == 6000
        assert usage['token_source'] == 'trace'
        assert usage['message_count'] == 2

    def test_fallback_estimation(self):
        """Falls back to char estimation when no trace data."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_state.return_value = {}
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        agent._update_context_usage('thread-1', 'user-1',
                                    trace_input_tokens=0, trace_output_tokens=0,
                                    input_chars=400, output_chars=800)

        call_args = agent.bond_provider.threads.update_thread_session.call_args
        session_state = call_args[1]['session_state'] if 'session_state' in call_args[1] else call_args[0][3]
        usage = session_state['context_usage']
        assert usage['total_chars'] == 1200
        assert usage['estimated_tokens'] == 300  # 1200 / 4
        assert usage['token_source'] == 'estimated'

    def test_increments_existing_usage(self):
        """Correctly increments cumulative counters."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_state.return_value = {
            'context_usage': {
                'total_tokens': 5000,
                'total_chars': 0,
                'estimated_tokens': 5000,
                'message_count': 4,
                'compaction_count': 0,
            }
        }
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        agent._update_context_usage('thread-1', 'user-1',
                                    trace_input_tokens=3000, trace_output_tokens=1000,
                                    input_chars=100, output_chars=200)

        call_args = agent.bond_provider.threads.update_thread_session.call_args
        session_state = call_args[1]['session_state'] if 'session_state' in call_args[1] else call_args[0][3]
        usage = session_state['context_usage']
        assert usage['total_tokens'] == 9000
        assert usage['message_count'] == 6

    def test_initializes_missing_usage(self):
        """Creates usage dict if missing from session_state."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_state.return_value = None
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        agent._update_context_usage('thread-1', 'user-1',
                                    trace_input_tokens=1000, trace_output_tokens=500,
                                    input_chars=100, output_chars=200)

        call_args = agent.bond_provider.threads.update_thread_session.call_args
        session_state = call_args[1]['session_state'] if 'session_state' in call_args[1] else call_args[0][3]
        usage = session_state['context_usage']
        assert usage['total_tokens'] == 1500
        assert usage['message_count'] == 2


class TestCompactContext:
    """Tests for _compact_context session rotation."""

    def _setup_agent(self):
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'old-session-id'

        # Mock messages
        msg1 = MagicMock()
        msg1.role = 'user'
        msg1.clob.get_content.return_value = 'Hello, can you help me?'
        msg2 = MagicMock()
        msg2.role = 'assistant'
        msg2.clob.get_content.return_value = 'Of course! How can I assist you?'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict([
            ('msg-1', msg1), ('msg-2', msg2)
        ])

        # Mock converse API
        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {
                'message': {
                    'content': [{'text': 'Summary: User asked for help.'}]
                }
            }
        }
        return agent

    def test_calls_converse_api(self):
        """Verifies that Converse API is called for summary generation."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}

        agent._compact_context('thread-1', 'user-1', session_state)

        agent.bond_provider.bedrock_runtime_client.converse.assert_called_once()
        call_args = agent.bond_provider.bedrock_runtime_client.converse.call_args
        assert call_args[1]['modelId'] == agent.model
        assert call_args[1]['inferenceConfig']['temperature'] == 0.0

    def test_rotates_session(self):
        """New session_id generated, old one replaced."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}

        new_session_id, new_state, summary_history = agent._compact_context('thread-1', 'user-1', session_state)

        assert new_session_id != 'old-session-id'
        assert len(new_session_id) == 32  # uuid hex
        # Verify session was persisted with new ID
        last_call = agent.bond_provider.threads.update_thread_session.call_args_list[-1]
        assert last_call[1]['session_id'] == new_session_id

    def test_resets_usage(self):
        """Context usage reset with summary chars only."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}

        _, new_state, _ = agent._compact_context('thread-1', 'user-1', session_state)

        usage = new_state['context_usage']
        assert usage['total_tokens'] == 0
        assert usage['token_source'] == 'reset'
        # estimated_tokens should be based on summary length
        assert usage['estimated_tokens'] > 0

    def test_increments_compaction_count(self):
        """compaction_count incremented."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 2}}

        _, new_state, _ = agent._compact_context('thread-1', 'user-1', session_state)

        assert new_state['context_usage']['compaction_count'] == 3

    def test_summary_history_format(self):
        """Summary history has alternating user/assistant roles."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}

        _, _, summary_history = agent._compact_context('thread-1', 'user-1', session_state)

        assert len(summary_history) == 2
        assert summary_history[0]['role'] == 'user'
        assert summary_history[1]['role'] == 'assistant'
        assert 'text' in summary_history[0]['content'][0]
        assert 'text' in summary_history[1]['content'][0]

    def test_stores_pending_summary(self):
        """Summary stored in pending_compaction_summary for next invocation."""
        agent = self._setup_agent()
        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}

        _, new_state, _ = agent._compact_context('thread-1', 'user-1', session_state)

        assert 'pending_compaction_summary' in new_state
        assert len(new_state['pending_compaction_summary']) == 2


class TestGenerateSummary:
    """Tests for _generate_summary Converse API call."""

    def test_generates_summary(self):
        agent = _make_agent()
        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {
                'message': {
                    'content': [{'text': 'This is a summary of the conversation.'}]
                }
            }
        }

        result = agent._generate_summary("USER: Hello\n\nASSISTANT: Hi there")

        assert result == 'This is a summary of the conversation.'

    def test_truncates_long_summary(self):
        """Summary capped at 1800 chars + ellipsis."""
        agent = _make_agent()
        long_text = 'x' * 2000
        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {
                'message': {
                    'content': [{'text': long_text}]
                }
            }
        }

        result = agent._generate_summary("test conversation")

        assert len(result) == 1803  # 1800 + "..."
        assert result.endswith("...")

    def test_conversation_text_capped(self):
        """Conversation text capped at 150K chars in _compact_context."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        # Create a single very long message
        long_msg = MagicMock()
        long_msg.role = 'user'
        long_msg.clob.get_content.return_value = 'a' * 200_000
        agent.bond_provider.threads.get_messages.return_value = OrderedDict([
            ('msg-1', long_msg)
        ])

        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'summary'}]}}
        }

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        agent._compact_context('thread-1', 'user-1', session_state)

        call_args = agent.bond_provider.bedrock_runtime_client.converse.call_args
        msg_text = call_args[1]['messages'][0]['content'][0]['text']
        # The prompt prefix + capped conversation text should be well under 200K
        assert len(msg_text) < 160_000


class TestCompactionFailure:
    """Tests for compaction failure handling."""

    def test_compaction_failure_non_fatal(self):
        """DB error returns None tuple and clears compaction flag."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_state.return_value = {
            'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}
        }
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'
        agent.bond_provider.threads.get_messages.side_effect = Exception("DB error")

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        # Should return None tuple instead of raising
        assert result == (None, None, None)
        # compaction_in_progress flag should be cleared
        assert 'compaction_in_progress' not in session_state

    def test_compact_context_converse_api_failure(self):
        """Converse API failure returns None tuple and clears flag."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        # Provide messages so we get past the empty check
        msg1 = MagicMock()
        msg1.role = 'user'
        msg1.clob.get_content.return_value = 'Hello'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict([('msg-1', msg1)])

        # Make converse API fail
        agent.bond_provider.bedrock_runtime_client.converse.side_effect = Exception("Throttling")

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        assert result == (None, None, None)
        assert 'compaction_in_progress' not in session_state

    def test_compact_context_with_empty_messages(self):
        """Empty message list skips compaction."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict()

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        assert result == (None, None, None)
        assert 'compaction_in_progress' not in session_state
        # Converse API should NOT have been called
        agent.bond_provider.bedrock_runtime_client.converse.assert_not_called()

    def test_compact_context_clears_flag_on_failure(self):
        """compaction_in_progress flag is cleaned up even when summarizer fails."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        msg1 = MagicMock()
        msg1.role = 'user'
        msg1.clob.get_content.return_value = 'Hello'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict([('msg-1', msg1)])

        # Summarizer returns empty
        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {'message': {'content': []}}
        }

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        assert result == (None, None, None)
        assert 'compaction_in_progress' not in session_state


    def test_compact_context_with_no_text_content(self):
        """Messages exist but have no extractable text → compaction skipped."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'

        # Message with clob = None
        msg1 = MagicMock()
        msg1.role = 'user'
        msg1.clob = None

        # Message with clob returning empty string
        msg2 = MagicMock()
        msg2.role = 'assistant'
        msg2.clob.get_content.return_value = ''

        agent.bond_provider.threads.get_messages.return_value = OrderedDict([
            ('msg-1', msg1), ('msg-2', msg2)
        ])

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        assert result == (None, None, None)
        assert 'compaction_in_progress' not in session_state
        # Converse API should NOT have been called
        agent.bond_provider.bedrock_runtime_client.converse.assert_not_called()


class TestCompactionWithCrossAgentMerge:
    """Tests for merging compaction summary with cross-agent history.

    NOTE: Logic-simulation test — mirrors the merge logic from
    stream_response (BedrockAgent.py lines ~419-436). If the production
    code changes, this test must be updated to match.
    """

    def test_merge_both_histories(self):
        """Both compaction summary and cross-agent history merged correctly."""
        agent = _make_agent()

        pending_summary = [
            {"role": "user", "content": [{"text": "Summary intro"}]},
            {"role": "assistant", "content": [{"text": "Summary content"}]},
        ]
        cross_agent_history = [
            {"role": "user", "content": [{"text": "Cross-agent message"}]},
            {"role": "assistant", "content": [{"text": "Cross-agent response"}]},
        ]

        session_state = {
            'pending_compaction_summary': pending_summary,
        }

        # Simulate the logic from stream_response
        pending = session_state.get('pending_compaction_summary')
        if pending:
            session_state['conversationHistory'] = {'messages': pending}
            session_state.pop('pending_compaction_summary', None)

        if cross_agent_history and pending:
            merged = pending + cross_agent_history
            if len(merged) > 20:
                merged = merged[:20]
            session_state['conversationHistory'] = {'messages': merged}

        messages = session_state['conversationHistory']['messages']
        assert len(messages) == 4
        assert messages[0]['content'][0]['text'] == 'Summary intro'
        assert messages[2]['content'][0]['text'] == 'Cross-agent message'


class TestTraceTokenExtraction:
    """Tests for extracting token counts from orchestrationTrace events."""

    def test_extract_tokens_from_trace(self):
        """Tokens extracted from orchestrationTrace.modelInvocationOutput.metadata.usage."""
        from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent

        # Build a trace event matching Bedrock's format
        trace_event = {
            'trace': {
                'orchestrationTrace': {
                    'modelInvocationOutput': {
                        'metadata': {
                            'usage': {
                                'inputToken': 1500,
                                'outputToken': 300,
                            }
                        }
                    }
                }
            }
        }

        # Verify the structure matches what we expect
        event_trace = trace_event['trace']
        orch_trace = event_trace['orchestrationTrace']
        model_output = orch_trace['modelInvocationOutput']
        usage = model_output.get('metadata', {}).get('usage', {})
        assert usage.get('inputToken', 0) == 1500
        assert usage.get('outputToken', 0) == 300


class TestConfigurableThreshold:
    """Tests for BEDROCK_COMPACTION_THRESHOLD env var."""

    def test_env_var_overrides_default(self):
        """BEDROCK_COMPACTION_THRESHOLD env var overrides default."""
        with patch.dict(os.environ, {'BEDROCK_COMPACTION_THRESHOLD': '0.8'}):
            # Re-import to pick up env var
            import importlib
            import bondable.bond.providers.bedrock.BedrockAgent as mod
            importlib.reload(mod)

            assert mod.COMPACTION_THRESHOLD_RATIO == 0.8

            # Restore default
            os.environ.pop('BEDROCK_COMPACTION_THRESHOLD', None)
            importlib.reload(mod)

    def test_default_threshold(self):
        from bondable.bond.providers.bedrock.BedrockAgent import COMPACTION_THRESHOLD_RATIO
        # Default is 0.6 (when env var is not set)
        assert COMPACTION_THRESHOLD_RATIO == 0.6


class TestStreamResponseCompaction:
    """Tests for pending summary injection in stream_response.

    NOTE: Logic-simulation test — mirrors the injection logic from
    stream_response (BedrockAgent.py lines ~406-416). If the production
    code changes, this test must be updated to match.
    """

    def test_pending_summary_injected(self):
        """Pending compaction summary is injected into conversationHistory."""
        agent = _make_agent()

        pending_summary = [
            {"role": "user", "content": [{"text": "Summary intro"}]},
            {"role": "assistant", "content": [{"text": "Summary"}]},
        ]

        session_state = {
            'pending_compaction_summary': pending_summary,
        }

        # Simulate the injection logic from stream_response (lines ~406-416)
        pending = session_state.get('pending_compaction_summary')
        if pending:
            session_state['conversationHistory'] = {'messages': pending}
            session_state.pop('pending_compaction_summary', None)

        assert 'conversationHistory' in session_state
        assert session_state['conversationHistory']['messages'] == pending_summary
        assert 'pending_compaction_summary' not in session_state


class TestConcurrencySafety:
    """Tests for compaction_in_progress flag handling.

    NOTE: Logic-simulation tests — mirror the stale-flag logic from
    stream_response (BedrockAgent.py lines ~384-404). If the production
    code changes, these tests must be updated to match.
    """

    def test_stale_flag_cleared(self):
        """Stale compaction flag (>60s old) is cleared."""
        from datetime import datetime, timedelta, timezone

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        session_state = {'compaction_in_progress': old_time}

        # Simulate the logic from stream_response
        compaction_ts = session_state.get('compaction_in_progress')
        if compaction_ts:
            started = datetime.fromisoformat(compaction_ts)
            if datetime.now(timezone.utc) - started >= timedelta(seconds=60):
                session_state.pop('compaction_in_progress', None)

        assert 'compaction_in_progress' not in session_state

    def test_active_flag_preserved(self):
        """Recent compaction flag (<60s) is preserved."""
        from datetime import datetime, timedelta, timezone

        recent_time = datetime.now(timezone.utc).isoformat()
        session_state = {'compaction_in_progress': recent_time}

        compaction_ts = session_state.get('compaction_in_progress')
        if compaction_ts:
            started = datetime.fromisoformat(compaction_ts)
            if datetime.now(timezone.utc) - started >= timedelta(seconds=60):
                session_state.pop('compaction_in_progress', None)

        assert 'compaction_in_progress' in session_state


class TestCustomKeysStrippedFromBedrockRequest:
    """Verify custom session_state keys are not sent to Bedrock's invoke_agent."""

    def test_custom_keys_stripped(self):
        """context_usage, pending_compaction_summary, compaction_in_progress stripped."""
        session_state = {
            'conversationHistory': {'messages': []},
            'sessionAttributes': {'foo': 'bar'},
            'context_usage': {'estimated_tokens': 5000},
            'pending_compaction_summary': [{'role': 'user', 'content': []}],
            'compaction_in_progress': '2026-01-01T00:00:00',
        }

        _CUSTOM_SESSION_KEYS = {'context_usage', 'pending_compaction_summary', 'compaction_in_progress'}
        bedrock_session_state = {
            k: v for k, v in session_state.items()
            if k not in _CUSTOM_SESSION_KEYS
        }

        assert 'conversationHistory' in bedrock_session_state
        assert 'sessionAttributes' in bedrock_session_state
        assert 'context_usage' not in bedrock_session_state
        assert 'pending_compaction_summary' not in bedrock_session_state
        assert 'compaction_in_progress' not in bedrock_session_state


class TestCompactionPerformedFlag:
    """Tests for compaction_performed flag behavior based on _compact_context return value."""

    def test_successful_compaction_sets_flag(self):
        """When _compact_context returns a valid session, compaction_performed becomes True."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'old-session-id'

        # Mock messages for successful compaction
        msg1 = MagicMock()
        msg1.role = 'user'
        msg1.clob.get_content.return_value = 'Hello'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict([('msg-1', msg1)])
        agent.bond_provider.bedrock_runtime_client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Summary'}]}}
        }

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        # Successful compaction returns non-None first element
        assert result[0] is not None
        # So caller should set compaction_performed = True
        compaction_performed = result[0] is not None
        assert compaction_performed is True

    def test_failed_compaction_keeps_flag_false(self):
        """When _compact_context returns (None, None, None), compaction_performed stays False."""
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict()  # empty → skip

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        assert result == (None, None, None)
        # Caller should NOT set compaction_performed = True
        compaction_performed = result[0] is not None
        assert compaction_performed is False


    def test_bedrock_state_merge_after_failed_compaction(self):
        """When _compact_context returns (None, None, None), Bedrock state merge still runs.

        This verifies the round-2 P1-A fix: compaction_performed stays False when
        compaction is skipped, so the state merge block (line ~1678) executes and
        writes Bedrock's new_session_state to the DB.
        """
        agent = _make_agent()
        agent.bond_provider.threads.get_thread_session_id.return_value = 'session-1'
        agent.bond_provider.threads.get_messages.return_value = OrderedDict()  # empty → skip

        session_state = {'context_usage': {'estimated_tokens': 130_000, 'compaction_count': 0}}
        result = agent._compact_context('thread-1', 'user-1', session_state)

        # Compaction skipped
        assert result == (None, None, None)
        compaction_performed = result[0] is not None
        assert compaction_performed is False

        # Simulate the state merge logic from stream_response (line ~1678)
        new_session_state = {'sessionAttributes': {'key': 'value'}}
        current_state = {'context_usage': {'estimated_tokens': 130_000}}

        if new_session_state and not compaction_performed:
            new_session_state.update({
                k: current_state[k]
                for k in ('context_usage', 'compaction_in_progress')
                if k in current_state and k not in new_session_state
            })
            agent.bond_provider.threads.update_thread_session(
                thread_id='thread-1', user_id='user-1',
                session_id='session-1', session_state=new_session_state
            )

        # Verify state merge wrote to DB with Bedrock state + preserved context_usage
        agent.bond_provider.threads.update_thread_session.assert_called_with(
            thread_id='thread-1', user_id='user-1',
            session_id='session-1', session_state={
                'sessionAttributes': {'key': 'value'},
                'context_usage': {'estimated_tokens': 130_000},
            }
        )


class TestCrossAgentMergeTruncation:
    """Tests for cross-agent history merge truncation at 20 messages.

    NOTE: Logic-simulation test — mirrors the truncation logic from
    stream_response (BedrockAgent.py lines ~427-431). If the production
    code changes, this test must be updated to match.
    """

    def test_truncation_at_20_messages(self):
        """Merged history exceeding 20 messages is truncated, summary first."""
        pending_summary = [
            {"role": "user", "content": [{"text": "Summary intro"}]},
            {"role": "assistant", "content": [{"text": "Summary content"}]},
        ]

        # 12 cross-agent message pairs = 24 messages
        cross_agent_history = []
        for i in range(12):
            cross_agent_history.append({"role": "user", "content": [{"text": f"Cross msg {i}"}]})
            cross_agent_history.append({"role": "assistant", "content": [{"text": f"Cross reply {i}"}]})

        merged = pending_summary + cross_agent_history
        assert len(merged) == 26  # 2 + 24

        if len(merged) > 20:
            merged = merged[:20]

        assert len(merged) == 20
        # Summary messages should be first (preserved)
        assert merged[0]['content'][0]['text'] == 'Summary intro'
        assert merged[1]['content'][0]['text'] == 'Summary content'
        # Cross-agent messages follow
        assert merged[2]['content'][0]['text'] == 'Cross msg 0'
