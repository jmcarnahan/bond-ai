"""Tests for AgentRecord transaction handling in create_or_update_agent_resource.

Verifies that:
- AgentRecord is committed (not just flushed) before long-running AWS operations
- Orphaned AgentRecords are cleaned up when AWS operations fail for new agents
- Update path does not trigger orphan cleanup
- Cleanup failures do not mask the original error
"""

import pytest
from unittest.mock import MagicMock, patch
from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgentProvider, BedrockAgent
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockAgentOptions
from bondable.bond.providers.metadata import AgentRecord


class MockAgentDef:
    """Minimal AgentDefinition mock for transaction tests."""
    def __init__(self, id=None):
        self.id = id
        self.name = "Test Agent"
        self.description = "A test agent"
        self.instructions = "You are a test assistant"
        self.introduction = ""
        self.reminder = ""
        self.model = "us.anthropic.claude-sonnet-4-6"
        self.tools = {}
        self.tool_resources = {}
        self.mcp_tools = []
        self.mcp_resources = []
        self.temperature = 0.0
        self.metadata = {}
        self.file_storage = "direct"


def _make_provider():
    """Create a BedrockAgentProvider with mocked dependencies."""
    metadata = MagicMock()
    session = MagicMock()
    metadata.get_db_session.return_value = session
    provider = BedrockAgentProvider(
        bedrock_client=MagicMock(),
        bedrock_agent_client=MagicMock(),
        metadata=metadata,
    )
    return provider, session


def _mock_query_chain(return_value):
    """Create a mock query chain that returns the given value from .first()."""
    mock = MagicMock()
    mock.filter_by.return_value.first.return_value = return_value
    return mock


class TestAgentRecordCommitBeforeBedrockCalls:
    """Verify session.commit() is called after AgentRecord add but before create_bedrock_agent."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.BedrockAgent.__init__", return_value=None)
    @patch("bondable.bond.providers.bedrock.BedrockAgent.BedrockAgentProvider.select_material_icon")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.create_bedrock_agent")
    def test_new_agent_commits_agent_record_before_bedrock_calls(
        self, mock_create_bedrock, mock_select_icon, mock_agent_init
    ):
        mock_create_bedrock.return_value = ("bedrock-id-123", "alias-id-456")
        mock_select_icon.return_value = '{"icon": "smart_toy", "color": "#2196F3"}'

        provider, session = _make_provider()
        agent_def = MockAgentDef(id=None)  # New agent

        # Mock the query chain to return None for the initial AgentRecord check,
        # then return a mock BedrockAgentOptions for the post-commit re-query.
        mock_bedrock_options = MagicMock(spec=BedrockAgentOptions)
        mock_bedrock_options.bedrock_agent_id = "bedrock-id-123"
        mock_bedrock_options.bedrock_agent_alias_id = "alias-id-456"
        mock_bedrock_options.mcp_tools = []
        mock_bedrock_options.agent_metadata = {}
        session.query.return_value.filter_by.return_value.first.side_effect = [
            None,              # line 2878: no existing AgentRecord
            mock_bedrock_options,  # line 3016: re-query BedrockAgentOptions after commit
        ]

        provider.create_or_update_agent_resource(agent_def, owner_user_id="user-1")

        # session.add should be called before commit
        session.add.assert_called()
        # commit must be called (not just flush) — at least twice: once for AgentRecord, once for final
        assert session.commit.call_count >= 2

        # Verify ordering: add → commit happens before create_bedrock_agent
        all_calls = session.mock_calls
        add_indices = [i for i, c in enumerate(all_calls) if c[0] == "add"]
        commit_indices = [i for i, c in enumerate(all_calls) if c[0] == "commit"]
        assert len(add_indices) > 0, "session.add must be called"
        assert len(commit_indices) > 0, "session.commit must be called"
        assert add_indices[0] < commit_indices[0], "session.add must be called before session.commit"
        assert mock_create_bedrock.called, "create_bedrock_agent should have been called"


class TestOrphanCleanupOnFailure:
    """Verify orphaned AgentRecords are cleaned up when AWS operations fail."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.create_bedrock_agent")
    def test_new_agent_cleans_up_orphan_on_bedrock_failure(self, mock_create_bedrock):
        mock_create_bedrock.side_effect = RuntimeError("Bedrock API failed")

        provider, session = _make_provider()
        agent_def = MockAgentDef(id=None)  # New agent

        orphaned_record = MagicMock(spec=AgentRecord)

        # First query: check for existing AgentRecord → None (triggers creation)
        # Second query: orphan cleanup → returns the orphaned record
        session.query.side_effect = [
            _mock_query_chain(None),        # line 2878: no existing record
            _mock_query_chain(orphaned_record),  # line 3041: cleanup finds orphan
        ]

        with pytest.raises(RuntimeError, match="Bedrock API failed"):
            provider.create_or_update_agent_resource(agent_def, owner_user_id="user-1")

        # Verify rollback was called
        session.rollback.assert_called_once()
        # Verify orphan cleanup: delete + commit
        session.delete.assert_called_once_with(orphaned_record)
        # commit called twice: once for initial AgentRecord (line 2888), once for cleanup (line 3044)
        assert session.commit.call_count == 2

    @patch("bondable.bond.providers.bedrock.BedrockAgent.update_bedrock_agent")
    def test_update_agent_skips_orphan_cleanup(self, mock_update_bedrock):
        mock_update_bedrock.side_effect = RuntimeError("Bedrock API failed")

        provider, session = _make_provider()
        agent_def = MockAgentDef(id="existing-agent-id")  # Existing agent (update path)

        # For update path: BedrockAgentOptions query, AgentRecord query, get_agent
        mock_options = MagicMock()
        mock_options.bedrock_agent_id = "bedrock-123"
        mock_options.bedrock_agent_alias_id = "alias-456"
        mock_options.agent_metadata = {"icon_svg": "test"}

        mock_agent_record = MagicMock()
        mock_agent_record.name = "Test Agent"

        # Mock the bedrock_agent_client.get_agent for update path (line 2970)
        provider.bedrock_agent_client.get_agent.return_value = {
            "agent": {
                "description": "A test agent",
                "foundationModel": "us.anthropic.claude-sonnet-4-6",
                "instruction": "You are a test assistant",
            }
        }

        session.query.side_effect = [
            _mock_query_chain(mock_options),      # line 2923: BedrockAgentOptions
            _mock_query_chain(mock_agent_record),  # line 2948: AgentRecord for update
        ]

        with pytest.raises(RuntimeError, match="Bedrock API failed"):
            provider.create_or_update_agent_resource(agent_def, owner_user_id="user-1")

        # Verify rollback was called but delete was NOT (no orphan cleanup for updates)
        session.rollback.assert_called_once()
        session.delete.assert_not_called()

    @patch("bondable.bond.providers.bedrock.BedrockAgent.create_bedrock_agent")
    def test_orphan_cleanup_failure_does_not_mask_original_error(self, mock_create_bedrock):
        mock_create_bedrock.side_effect = RuntimeError("Original Bedrock error")

        provider, session = _make_provider()
        agent_def = MockAgentDef(id=None)  # New agent

        # First query: no existing record, second query: cleanup fails
        cleanup_query = MagicMock()
        cleanup_query.filter_by.return_value.first.side_effect = Exception("DB cleanup failed")

        session.query.side_effect = [
            _mock_query_chain(None),  # line 2878: no existing record
            cleanup_query,            # line 3041: cleanup query fails
        ]

        # The original error should be raised, not the cleanup error
        with pytest.raises(RuntimeError, match="Original Bedrock error"):
            provider.create_or_update_agent_resource(agent_def, owner_user_id="user-1")
