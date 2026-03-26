"""
Unit tests for Bedrock connection resilience:
- boto3 client config (connect_timeout, tcp_keepalive, standard retries)
- Retry logic on initial invoke_agent calls
- User-friendly error handling for connection errors in stream_response
"""

import os
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from http.client import RemoteDisconnected
from botocore.exceptions import ClientError, ConnectionClosedError


class TestAgentRuntimeConfig:
    """Tests for BedrockProvider boto3 client configuration.

    Tests call the real _init_aws_clients method (where BotoConfig is used)
    with boto3 and BotoConfig mocked at the module level.
    """

    def _init_aws_clients(self, mock_boto3, mock_boto_config):
        """Call the real _init_aws_clients on a BedrockProvider instance."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()
        mock_boto_config.return_value = MagicMock()

        from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
        provider = BedrockProvider.__new__(BedrockProvider)
        provider._init_aws_clients()
        return provider

    @patch('bondable.bond.providers.bedrock.BedrockProvider.BotoConfig')
    @patch('bondable.bond.providers.bedrock.BedrockProvider.boto3')
    def test_agent_runtime_config_defaults(self, mock_boto3, mock_boto_config):
        """Config should use connect_timeout=10, tcp_keepalive=True, standard retries with max_attempts=3."""
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}, clear=False):
            os.environ.pop('BEDROCK_AGENT_RUNTIME_MAX_ATTEMPTS', None)
            os.environ.pop('BEDROCK_AGENT_RUNTIME_READ_TIMEOUT', None)

            self._init_aws_clients(mock_boto3, mock_boto_config)

            mock_boto_config.assert_called_once_with(
                read_timeout=300,
                connect_timeout=10,
                retries={'max_attempts': 3, 'mode': 'standard'},
                tcp_keepalive=True
            )

    @patch('bondable.bond.providers.bedrock.BedrockProvider.BotoConfig')
    @patch('bondable.bond.providers.bedrock.BedrockProvider.boto3')
    def test_agent_runtime_config_env_override(self, mock_boto3, mock_boto_config):
        """BEDROCK_AGENT_RUNTIME_MAX_ATTEMPTS env var should override the default."""
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'BEDROCK_AGENT_RUNTIME_MAX_ATTEMPTS': '5'}):
            self._init_aws_clients(mock_boto3, mock_boto_config)

            mock_boto_config.assert_called_once_with(
                read_timeout=300,
                connect_timeout=10,
                retries={'max_attempts': 5, 'mode': 'standard'},
                tcp_keepalive=True
            )


class TestInvokeAgentRetry:
    """Tests for retry logic on the initial invoke_agent call in _process_bedrock_invocation."""

    def _make_agent(self):
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
        agent.model = 'anthropic.claude-3-sonnet'
        agent.mcp_tools = []

        # Mock the provider and its client
        mock_provider = MagicMock()
        mock_provider.aws_region = 'us-east-1'
        agent.bond_provider = mock_provider

        return agent

    def _invoke_with_retry(self, agent, mock_invoke):
        """
        Call _process_bedrock_invocation and consume the generator.
        Returns a list of yielded strings.
        """
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = mock_invoke

        # Patch internal helper to isolate the invoke_agent retry logic
        agent._create_bond_message_tag = Mock(return_value='<tag>')

        results = list(agent._process_bedrock_invocation(
            prompt='Hello',
            thread_id='thread-1',
            session_id='session-1',
            session_state={},
            files=None,
            attachments=None,
            hidden=False,
            user_id='user-1',
        ))
        return results

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_succeeds_on_first_attempt(self, mock_time):
        """invoke_agent should be called once when it succeeds immediately."""
        agent = self._make_agent()
        mock_invoke = Mock(return_value={'completion': []})

        self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == 1
        mock_time.sleep.assert_not_called()

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_retries_on_remote_disconnected(self, mock_time):
        """invoke_agent should retry on RemoteDisconnected and succeed on second attempt."""
        agent = self._make_agent()
        normal_response = {'completion': []}
        mock_invoke = Mock(side_effect=[RemoteDisconnected('Remote end closed connection'), normal_response])

        self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == 2
        mock_time.sleep.assert_called_once_with(1.0)

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_retries_on_connection_closed_error(self, mock_time):
        """invoke_agent should retry on ConnectionClosedError."""
        agent = self._make_agent()
        normal_response = {'completion': []}
        mock_invoke = Mock(side_effect=[
            ConnectionClosedError(endpoint_url='https://bedrock.us-east-1.amazonaws.com'),
            normal_response
        ])

        self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == 2
        mock_time.sleep.assert_called_once_with(1.0)

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_retries_on_connection_reset(self, mock_time):
        """invoke_agent should retry on ConnectionResetError (subclass of ConnectionError/OSError)."""
        agent = self._make_agent()
        normal_response = {'completion': []}
        mock_invoke = Mock(side_effect=[
            ConnectionResetError('[Errno 54] Connection reset by peer'),
            normal_response
        ])

        self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == 2
        mock_time.sleep.assert_called_once_with(1.0)

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_succeeds_on_final_attempt(self, mock_time):
        """invoke_agent should succeed when the last allowed attempt works."""
        from bondable.bond.providers.bedrock.BedrockAgent import MAX_INVOKE_RETRIES
        agent = self._make_agent()
        normal_response = {'completion': []}
        # Fail on all attempts except the last one
        side_effects = [RemoteDisconnected('fail')] * MAX_INVOKE_RETRIES + [normal_response]
        mock_invoke = Mock(side_effect=side_effects)

        results = self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == MAX_INVOKE_RETRIES + 1
        # Should not raise — response is returned successfully

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_exhausts_retries_then_raises(self, mock_time):
        """invoke_agent should raise after exhausting all retry attempts."""
        from bondable.bond.providers.bedrock.BedrockAgent import MAX_INVOKE_RETRIES
        agent = self._make_agent()
        mock_invoke = Mock(side_effect=RemoteDisconnected('Remote end closed connection'))

        with pytest.raises(RemoteDisconnected):
            self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == MAX_INVOKE_RETRIES + 1

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_invoke_does_not_retry_on_client_error(self, mock_time):
        """Non-connection errors like ClientError should not be retried."""
        agent = self._make_agent()
        error_response = {'Error': {'Code': 'ValidationException', 'Message': 'Bad request'}}
        mock_invoke = Mock(side_effect=ClientError(error_response, 'InvokeAgent'))

        with pytest.raises(ClientError):
            self._invoke_with_retry(agent, mock_invoke)

        assert mock_invoke.call_count == 1
        mock_time.sleep.assert_not_called()

    @patch('bondable.bond.providers.bedrock.BedrockAgent.time')
    def test_retry_uses_exponential_backoff(self, mock_time):
        """Retries should use exponential backoff: 1s, 2s."""
        from bondable.bond.providers.bedrock.BedrockAgent import MAX_INVOKE_RETRIES
        agent = self._make_agent()
        mock_invoke = Mock(side_effect=RemoteDisconnected('Remote end closed connection'))

        with pytest.raises(RemoteDisconnected):
            self._invoke_with_retry(agent, mock_invoke)

        # Verify exponential backoff delays: 1.0 * 2^0 = 1s, 1.0 * 2^1 = 2s
        expected_calls = [call(1.0), call(2.0)]
        assert mock_time.sleep.call_args_list == expected_calls


class TestStreamResponseConnectionError:
    """Tests for connection error handling in stream_response."""

    def _make_agent(self):
        """Create a minimally-mocked BedrockAgent for testing stream_response."""
        from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent
        agent = BedrockAgent.__new__(BedrockAgent)
        agent.agent_id = 'test-agent-id'
        agent.bedrock_agent_id = 'bedrock-agent-123'
        agent.bedrock_agent_alias_id = 'alias-456'
        agent.name = 'Test Agent'
        agent.introduction = 'Hi'
        agent.reminder = ''
        agent.owner_user_id = 'user-1'
        agent.model = 'anthropic.claude-3-sonnet'
        agent.mcp_tools = []
        agent.file_storage = 'code_interpreter'
        agent.metadata = MagicMock()

        # Mock the provider with threads sub-provider
        mock_provider = MagicMock()
        mock_provider.aws_region = 'us-east-1'
        mock_provider.threads.get_thread_owner.return_value = 'user-1'
        mock_provider.threads.get_thread_session_id.return_value = 'session-1'
        mock_provider.threads.get_thread_session_state.return_value = {}
        mock_provider.threads.get_cross_agent_conversation_history.return_value = []
        mock_provider.threads.get_messages.return_value = {}
        agent.bond_provider = mock_provider

        # Mock create_user_message to avoid side effects
        agent.create_user_message = Mock()

        return agent

    def _run_stream_with_error(self, error):
        """Helper: run stream_response with _process_bedrock_invocation raising the given error."""
        agent = self._make_agent()

        with patch.object(agent, '_process_bedrock_invocation', side_effect=error):
            error_messages = []

            def capture_error(thread_id, message, error_code=None):
                error_messages.append(message)
                yield f'error:{message}'

            agent._yield_error_message = capture_error

            list(agent.stream_response(
                prompt='Hello',
                thread_id='thread-1',
                current_user=MagicMock(user_id='user-1'),
            ))

            return error_messages

    def test_stream_response_remote_disconnected_yields_friendly_message(self):
        """RemoteDisconnected in stream_response should yield a user-friendly retry message."""
        messages = self._run_stream_with_error(RemoteDisconnected('Remote end closed'))
        assert len(messages) == 1
        assert "trouble connecting" in messages[0]

    def test_stream_response_connection_closed_yields_friendly_message(self):
        """ConnectionClosedError in stream_response should yield a user-friendly retry message."""
        messages = self._run_stream_with_error(
            ConnectionClosedError(endpoint_url='https://bedrock.amazonaws.com')
        )
        assert len(messages) == 1
        assert "trouble connecting" in messages[0]

    def test_stream_response_connection_reset_yields_friendly_message(self):
        """ConnectionResetError (OSError subclass) should yield the friendly message, not raw error."""
        messages = self._run_stream_with_error(
            ConnectionResetError('[Errno 54] Connection reset by peer')
        )
        assert len(messages) == 1
        assert "trouble connecting" in messages[0]

    def test_stream_response_oserror_yields_friendly_message(self):
        """OSError from socket-level failures should yield the friendly message."""
        messages = self._run_stream_with_error(
            OSError('[Errno 32] Broken pipe')
        )
        assert len(messages) == 1
        assert "trouble connecting" in messages[0]
