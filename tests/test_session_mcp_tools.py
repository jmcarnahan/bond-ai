"""Regression tests for MCP tools persistence through agent update flow.

Verifies that mcp_tools survive the full create_or_update_agent pipeline,
including the OAuth token lookups that previously rolled back uncommitted
changes on the shared scoped SQLite session.
"""
import pytest
import os
import tempfile
import uuid
from unittest.mock import patch, MagicMock

# --- Test Database Setup (must happen before app import) ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['ALLOW_ALL_EMAILS'] = 'true'

from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.metadata import AgentRecord
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockAgentOptions


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def provider():
    return Config.config().get_provider()


def _unique_id():
    return f"test_{uuid.uuid4().hex[:12]}"


def _seed_agent(provider, agent_id, user_id, mcp_tools=None):
    """Create an agent with BedrockAgentOptions directly in the DB."""
    session = provider.metadata.get_db_session()
    rec = AgentRecord(
        agent_id=agent_id,
        name="Test Agent",
        introduction="",
        reminder="",
        owner_user_id=user_id,
    )
    session.add(rec)
    session.flush()
    opts = BedrockAgentOptions(
        agent_id=agent_id,
        bedrock_agent_id=f"FAKE{agent_id[:8]}",
        bedrock_agent_alias_id=f"ALIAS{agent_id[:8]}",
        temperature=0.0,
        tools={},
        tool_resources={},
        mcp_tools=mcp_tools or [],
        mcp_resources=[],
        agent_metadata={},
        file_storage="direct",
    )
    session.add(opts)
    session.commit()
    return opts


class TestMcpToolsPersistence:
    """Regression: mcp_tools must survive the full create_or_update_agent flow."""

    def test_mcp_tools_persist_through_resource_update(self, provider):
        """mcp_tools set during update must be in the DB after create_or_update_agent_resource.

        This exercises the real DB session lifecycle (scoped session, commit ordering)
        while mocking only the external AWS calls.
        """
        agent_id = _unique_id()
        user_id = _unique_id()
        bedrock_agent_id = f"FAKE{agent_id[:8]}"
        bedrock_alias_id = f"ALIAS{agent_id[:8]}"
        _seed_agent(provider, agent_id, user_id, mcp_tools=[])

        agent_def = MagicMock()
        agent_def.id = agent_id
        agent_def.name = "Test Agent"
        agent_def.description = "Test"
        agent_def.instructions = "You are a test assistant."
        agent_def.introduction = ""
        agent_def.reminder = ""
        agent_def.tools = {}
        agent_def.tool_resources = {}
        agent_def.metadata = {}
        agent_def.model = "us.anthropic.claude-sonnet-4-6"
        agent_def.temperature = 0.0
        agent_def.mcp_tools = ["sbelcrm:search_contacts", "sbelcrm:get_contact"]
        agent_def.mcp_resources = []
        agent_def.file_storage = "direct"

        with patch("bondable.bond.providers.bedrock.BedrockAgent.update_bedrock_agent",
                    return_value=(bedrock_agent_id, bedrock_alias_id)), \
             patch("bondable.bond.providers.bedrock.BedrockAgent.BedrockAgent") as MockBA:
            mock_agent = MagicMock()
            mock_agent.get_agent_id.return_value = agent_id
            mock_agent.get_name.return_value = "Test Agent"
            MockBA.return_value = mock_agent

            # Mock the bedrock_agent_client.get_agent call inside create_or_update_agent_resource
            provider.agents.bedrock_agent_client = MagicMock()
            provider.agents.bedrock_agent_client.get_agent.return_value = {
                "agent": {"description": "Test", "foundationModel": "claude"}
            }

            provider.agents.create_or_update_agent_resource(agent_def, owner_user_id=user_id)

        # Verify directly in DB
        session = provider.metadata.get_db_session()
        session.expire_all()
        opts = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
        assert opts is not None
        assert opts.mcp_tools == ["sbelcrm:search_contacts", "sbelcrm:get_contact"], \
            f"mcp_tools silently lost during agent update: {opts.mcp_tools}"

    def test_mcp_tools_cleared_when_empty_list(self, provider):
        """Setting mcp_tools=[] should clear them in the DB."""
        agent_id = _unique_id()
        user_id = _unique_id()
        bedrock_agent_id = f"FAKE{agent_id[:8]}"
        bedrock_alias_id = f"ALIAS{agent_id[:8]}"
        _seed_agent(provider, agent_id, user_id, mcp_tools=["sbelcrm:old_tool"])

        agent_def = MagicMock()
        agent_def.id = agent_id
        agent_def.name = "Test Agent"
        agent_def.description = "Test"
        agent_def.instructions = "You are a test assistant."
        agent_def.introduction = ""
        agent_def.reminder = ""
        agent_def.tools = {}
        agent_def.tool_resources = {}
        agent_def.metadata = {}
        agent_def.model = "us.anthropic.claude-sonnet-4-6"
        agent_def.temperature = 0.0
        agent_def.mcp_tools = []
        agent_def.mcp_resources = []
        agent_def.file_storage = "direct"

        with patch("bondable.bond.providers.bedrock.BedrockAgent.update_bedrock_agent",
                    return_value=(bedrock_agent_id, bedrock_alias_id)), \
             patch("bondable.bond.providers.bedrock.BedrockAgent.BedrockAgent") as MockBA:
            mock_agent = MagicMock()
            mock_agent.get_agent_id.return_value = agent_id
            mock_agent.get_name.return_value = "Test Agent"
            MockBA.return_value = mock_agent

            provider.agents.bedrock_agent_client = MagicMock()
            provider.agents.bedrock_agent_client.get_agent.return_value = {
                "agent": {"description": "Test", "foundationModel": "claude"}
            }

            provider.agents.create_or_update_agent_resource(agent_def, owner_user_id=user_id)

        session = provider.metadata.get_db_session()
        session.expire_all()
        opts = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
        assert opts.mcp_tools == [], f"mcp_tools should be empty: {opts.mcp_tools}"

    def test_token_cache_query_does_not_rollback_pending_changes(self, provider):
        """Token cache reads must not rollback another module's uncommitted changes.

        This is the exact failure mode: the mcp_token_cache used to call
        session.close() on the shared scoped session, rolling back any
        pending UPDATE from the agent update flow.
        """
        agent_id = _unique_id()
        user_id = _unique_id()
        _seed_agent(provider, agent_id, user_id, mcp_tools=[])

        # Simulate: set mcp_tools but DON'T commit yet
        session = provider.metadata.get_db_session()
        opts = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
        opts.mcp_tools = ["sbelcrm:test_tool"]
        assert opts in session.dirty

        # Now simulate what _get_mcp_tool_definitions does: token cache lookup
        from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
        cache = get_mcp_token_cache()
        # This read should NOT rollback our pending change
        cache._load_from_database(user_id, "nonexistent_connection")

        # Now commit — the change should still be there
        session.commit()

        # Verify
        session.expire_all()
        opts2 = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
        assert opts2.mcp_tools == ["sbelcrm:test_tool"], \
            f"Token cache query rolled back pending mcp_tools change: {opts2.mcp_tools}"
