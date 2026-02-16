"""
Tests for configurable code interpreter toggle.

Tests that code interpreter can be conditionally enabled/disabled when
creating or updating Bedrock agents, based on presence/absence of
{"type": "code_interpreter"} in the agent's tools list.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Test constants
MOCK_USER_ID = "test-user-123"
MOCK_AGENT_ROLE_ARN = "arn:aws:iam::000000000000:role/mock-test-role"


def _setup_mock_bedrock_client():
    """Create a standard mock Bedrock agent client for tests."""
    mock_bedrock = Mock()
    mock_bedrock.create_agent.return_value = {
        'agent': {'agentId': 'test-agent-id', 'agentStatus': 'PREPARED'}
    }
    mock_bedrock.prepare_agent.return_value = {}
    mock_bedrock.create_agent_action_group.return_value = {
        'agentActionGroup': {'actionGroupId': 'code-interpreter-id'}
    }
    mock_bedrock.create_agent_alias.return_value = {
        'agentAlias': {'agentAliasId': 'test-alias-id'}
    }
    return mock_bedrock


def _create_agent_def(tools=None, mcp_tools=None):
    """Create an AgentDefinition inside a patched context to avoid real AWS calls."""
    from bondable.bond.definition import AgentDefinition

    if tools is None:
        tools = [{"type": "code_interpreter"}, {"type": "file_search"}]

    return AgentDefinition(
        name="Test Agent",
        description="Test description",
        instructions="Test instructions for the agent that meets minimum length",
        model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        user_id=MOCK_USER_ID,
        tools=tools,
        mcp_tools=mcp_tools or [],
        mcp_resources=[]
    )


class TestCodeInterpreterHelperFunction:
    """Tests for the _has_code_interpreter helper function."""

    def test_has_code_interpreter_with_tool_present(self):
        """Returns True when code_interpreter is in tools list."""
        from bondable.bond.providers.bedrock.BedrockCRUD import _has_code_interpreter

        agent_def = Mock()
        agent_def.tools = [{"type": "code_interpreter"}, {"type": "file_search"}]
        assert _has_code_interpreter(agent_def) is True

    def test_has_code_interpreter_with_tool_absent(self):
        """Returns False when code_interpreter is not in tools list."""
        from bondable.bond.providers.bedrock.BedrockCRUD import _has_code_interpreter

        agent_def = Mock()
        agent_def.tools = [{"type": "file_search"}]
        assert _has_code_interpreter(agent_def) is False

    def test_has_code_interpreter_with_empty_tools(self):
        """Returns False when tools list is empty."""
        from bondable.bond.providers.bedrock.BedrockCRUD import _has_code_interpreter

        agent_def = Mock()
        agent_def.tools = []
        assert _has_code_interpreter(agent_def) is False

    def test_has_code_interpreter_with_none_tools(self):
        """Returns False when tools is None."""
        from bondable.bond.providers.bedrock.BedrockCRUD import _has_code_interpreter

        agent_def = Mock()
        agent_def.tools = None
        assert _has_code_interpreter(agent_def) is False


class TestCreateBedrockAgentCodeInterpreter:
    """Tests for code interpreter toggle in create_bedrock_agent."""

    def test_create_agent_with_code_interpreter_enabled(self):
        """Code interpreter action group IS created when tool is in tools list."""
        from bondable.bond.providers.bedrock.BedrockCRUD import create_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            agent_def = _create_agent_def(
                tools=[{"type": "code_interpreter"}, {"type": "file_search"}]
            )

            mock_bedrock = _setup_mock_bedrock_client()
            mock_client.return_value = mock_bedrock

            create_bedrock_agent(
                agent_id="test-bond-agent-id",
                agent_def=agent_def,
            )

            # Verify create_agent_action_group was called with CodeInterpreter
            calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_calls = [
                c for c in calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_calls) == 1
            assert ci_calls[0].kwargs['parentActionGroupSignature'] == 'AMAZON.CodeInterpreter'
            assert ci_calls[0].kwargs['actionGroupState'] == 'ENABLED'

    def test_create_agent_without_code_interpreter(self):
        """Code interpreter action group is NOT created when tool absent from tools list."""
        from bondable.bond.providers.bedrock.BedrockCRUD import create_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            agent_def = _create_agent_def(
                tools=[{"type": "file_search"}]  # No code_interpreter
            )

            mock_bedrock = _setup_mock_bedrock_client()
            mock_client.return_value = mock_bedrock

            create_bedrock_agent(
                agent_id="test-bond-agent-id",
                agent_def=agent_def,
            )

            # Verify create_agent_action_group was NOT called with CodeInterpreter
            calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_calls = [
                c for c in calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_calls) == 0

    def test_create_agent_with_empty_tools_skips_code_interpreter(self):
        """Code interpreter action group is NOT created when tools list is empty."""
        from bondable.bond.providers.bedrock.BedrockCRUD import create_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            agent_def = _create_agent_def(tools=[])

            mock_bedrock = _setup_mock_bedrock_client()
            mock_client.return_value = mock_bedrock

            create_bedrock_agent(
                agent_id="test-bond-agent-id",
                agent_def=agent_def,
            )

            # Verify create_agent_action_group was NOT called at all
            ci_calls = [
                c for c in mock_bedrock.create_agent_action_group.call_args_list
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_calls) == 0


class TestUpdateBedrockAgentCodeInterpreter:
    """Tests for code interpreter toggle in update_bedrock_agent."""

    def _setup_update_mocks(self, existing_action_groups=None):
        """Create standard mocks for update_bedrock_agent tests."""
        mock_bedrock = Mock()
        mock_bedrock.update_agent.return_value = {'agent': {'agentStatus': 'PREPARED'}}
        mock_bedrock.prepare_agent.return_value = {}
        mock_bedrock.list_agent_action_groups.return_value = {
            'actionGroupSummaries': existing_action_groups or []
        }
        mock_bedrock.get_agent_alias.return_value = {
            'agentAlias': {'agentAliasName': 'test-alias', 'agentAliasStatus': 'PREPARED'}
        }
        mock_bedrock.update_agent_alias.return_value = {}
        mock_bedrock.create_agent_action_group.return_value = {
            'agentActionGroup': {'actionGroupId': 'new-ci-id'}
        }
        mock_bedrock.delete_agent_action_group.return_value = {}
        return mock_bedrock

    def test_update_disable_code_interpreter(self):
        """Existing code interpreter action group is deleted when tool removed from tools."""
        from bondable.bond.providers.bedrock.BedrockCRUD import update_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            # Agent def WITHOUT code_interpreter
            agent_def = _create_agent_def(tools=[{"type": "file_search"}])
            agent_def.id = "test-bond-agent-id"

            # Existing action groups include CodeInterpreter
            existing_groups = [
                {
                    'actionGroupName': 'CodeInterpreterActionGroup',
                    'actionGroupId': 'existing-ci-id'
                }
            ]

            mock_bedrock = self._setup_update_mocks(existing_action_groups=existing_groups)
            mock_client.return_value = mock_bedrock

            update_bedrock_agent(
                agent_def=agent_def,
                bedrock_agent_id="bedrock-agent-id",
                bedrock_agent_alias_id="bedrock-alias-id",
            )

            # Verify delete_agent_action_group was called for the CI action group
            delete_calls = mock_bedrock.delete_agent_action_group.call_args_list
            ci_delete_calls = [
                c for c in delete_calls
                if c.kwargs.get('actionGroupId') == 'existing-ci-id'
            ]
            assert len(ci_delete_calls) == 1

            # Verify create_agent_action_group was NOT called for CodeInterpreter
            create_calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_create_calls = [
                c for c in create_calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_create_calls) == 0

    def test_update_enable_code_interpreter(self):
        """Code interpreter action group is created when tool added during update."""
        from bondable.bond.providers.bedrock.BedrockCRUD import update_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            # Agent def WITH code_interpreter
            agent_def = _create_agent_def(
                tools=[{"type": "code_interpreter"}, {"type": "file_search"}]
            )
            agent_def.id = "test-bond-agent-id"

            # No existing CI action group
            mock_bedrock = self._setup_update_mocks(existing_action_groups=[])
            mock_client.return_value = mock_bedrock

            update_bedrock_agent(
                agent_def=agent_def,
                bedrock_agent_id="bedrock-agent-id",
                bedrock_agent_alias_id="bedrock-alias-id",
            )

            # Verify create_agent_action_group was called for CodeInterpreter
            create_calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_create_calls = [
                c for c in create_calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_create_calls) == 1
            assert ci_create_calls[0].kwargs['parentActionGroupSignature'] == 'AMAZON.CodeInterpreter'

    def test_update_code_interpreter_unchanged_enabled(self):
        """No action group changes when code interpreter remains enabled."""
        from bondable.bond.providers.bedrock.BedrockCRUD import update_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            # Agent def WITH code_interpreter
            agent_def = _create_agent_def(
                tools=[{"type": "code_interpreter"}, {"type": "file_search"}]
            )
            agent_def.id = "test-bond-agent-id"

            # Existing CI action group already exists
            existing_groups = [
                {
                    'actionGroupName': 'CodeInterpreterActionGroup',
                    'actionGroupId': 'existing-ci-id'
                }
            ]

            mock_bedrock = self._setup_update_mocks(existing_action_groups=existing_groups)
            mock_client.return_value = mock_bedrock

            update_bedrock_agent(
                agent_def=agent_def,
                bedrock_agent_id="bedrock-agent-id",
                bedrock_agent_alias_id="bedrock-alias-id",
            )

            # Verify neither create nor delete was called for CodeInterpreter
            create_calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_create_calls = [
                c for c in create_calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_create_calls) == 0

            delete_calls = mock_bedrock.delete_agent_action_group.call_args_list
            ci_delete_calls = [
                c for c in delete_calls
                if c.kwargs.get('actionGroupId') == 'existing-ci-id'
            ]
            assert len(ci_delete_calls) == 0

    def test_update_code_interpreter_unchanged_disabled(self):
        """No action group changes when code interpreter remains disabled."""
        from bondable.bond.providers.bedrock.BedrockCRUD import update_bedrock_agent

        with patch('bondable.bond.providers.bedrock.BedrockCRUD._get_bedrock_agent_client') as mock_client, \
             patch('bondable.bond.providers.bedrock.BedrockCRUD._wait_for_resource_status'), \
             patch('bondable.bond.providers.bedrock.BedrockFiles.BedrockFilesProvider._ensure_bucket_exists'), \
             patch.dict('os.environ', {'BEDROCK_AGENT_ROLE_ARN': MOCK_AGENT_ROLE_ARN}):

            # Agent def WITHOUT code_interpreter
            agent_def = _create_agent_def(tools=[{"type": "file_search"}])
            agent_def.id = "test-bond-agent-id"

            # No existing CI action group
            mock_bedrock = self._setup_update_mocks(existing_action_groups=[])
            mock_client.return_value = mock_bedrock

            update_bedrock_agent(
                agent_def=agent_def,
                bedrock_agent_id="bedrock-agent-id",
                bedrock_agent_alias_id="bedrock-alias-id",
            )

            # Verify neither create nor delete was called for CodeInterpreter
            create_calls = mock_bedrock.create_agent_action_group.call_args_list
            ci_create_calls = [
                c for c in create_calls
                if c.kwargs.get('actionGroupName') == 'CodeInterpreterActionGroup'
            ]
            assert len(ci_create_calls) == 0

            # No CI action group to delete
            assert len(mock_bedrock.delete_agent_action_group.call_args_list) == 0


class TestAgentDefinitionCodeInterpreter:
    """Tests for AgentDefinition code_interpreter resource handling."""

    def _create_agent_def_with_mocks(self, tools):
        """Create AgentDefinition with fully mocked provider to isolate tool_resources logic."""
        from bondable.bond.definition import AgentDefinition

        mock_provider = Mock()
        mock_provider.vectorstores.get_or_create_default_vector_store_id.return_value = "mock-vs-id"
        mock_provider.vectorstores.update_vector_store_file_ids.return_value = None

        mock_config = Mock()
        mock_config.get_provider.return_value = mock_provider

        with patch('bondable.bond.definition.Config') as mock_config_class:
            mock_config_class.config.return_value = mock_config

            return AgentDefinition(
                name="Test Agent",
                description="Test",
                instructions="Test instructions",
                model="test-model",
                user_id=MOCK_USER_ID,
                tools=tools,
                tool_resources={},
            )

    def test_no_code_interpreter_tool_no_resource_created(self):
        """When code_interpreter is not in tools, tool_resources should not contain it."""
        agent_def = self._create_agent_def_with_mocks(tools=[{"type": "file_search"}])
        assert "code_interpreter" not in agent_def.tool_resources

    def test_with_code_interpreter_tool_creates_resource(self):
        """When code_interpreter is in tools, tool_resources should contain it."""
        agent_def = self._create_agent_def_with_mocks(
            tools=[{"type": "code_interpreter"}, {"type": "file_search"}]
        )
        assert "code_interpreter" in agent_def.tool_resources
        assert agent_def.tool_resources["code_interpreter"] == {"file_ids": []}

    def test_with_empty_tools_no_code_interpreter_resource(self):
        """When tools list is empty, code_interpreter should not be in tool_resources."""
        agent_def = self._create_agent_def_with_mocks(tools=[])
        assert "code_interpreter" not in agent_def.tool_resources
