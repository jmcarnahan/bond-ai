"""
Tests for agent sharing functionality.

Verifies that the default_group_id is correctly stored, returned, and used
for agent sharing - especially with agent names containing special characters
like apostrophes.
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, ANY, PropertyMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import timedelta, datetime, timezone

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app, create_access_token, get_bond_provider
from bondable.rest.models import AgentCreateRequest, AgentUpdateRequest
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import AgentProvider, Agent as AgentABC
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.files import FilesProvider, FileDetails
from bondable.bond.providers.vectorstores import VectorStoresProvider
from bondable.bond.groups import Groups
from bondable.bond.definition import AgentDefinition

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"


def _make_mock_agent_definition(**kwargs):
    """Create a mock AgentDefinition without hitting real provider."""
    mock_def = MagicMock(spec=AgentDefinition)
    mock_def.id = kwargs.get('id')
    mock_def.name = kwargs.get('name', 'Test Agent')
    mock_def.description = kwargs.get('description', '')
    mock_def.instructions = kwargs.get('instructions', '')
    mock_def.introduction = kwargs.get('introduction', '')
    mock_def.reminder = kwargs.get('reminder', '')
    mock_def.model = kwargs.get('model', 'test-model')
    mock_def.tools = kwargs.get('tools', [])
    mock_def.tool_resources = kwargs.get('tool_resources', {})
    mock_def.metadata = kwargs.get('metadata', {})
    mock_def.mcp_tools = kwargs.get('mcp_tools', [])
    mock_def.mcp_resources = kwargs.get('mcp_resources', [])
    mock_def.file_storage = kwargs.get('file_storage', 'direct')
    mock_def.temperature = 0.0
    mock_def.top_p = 0.5
    return mock_def


# --- Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database after session."""
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_provider():
    """Mock provider with all sub-providers including groups."""
    provider = MagicMock(spec=Provider)
    provider.agents = MagicMock(spec=AgentProvider)
    provider.threads = MagicMock(spec=ThreadsProvider)
    provider.files = MagicMock(spec=FilesProvider)
    provider.vectorstores = MagicMock(spec=VectorStoresProvider)
    provider.groups = MagicMock(spec=Groups)
    provider.get_default_model.return_value = "gpt-4.1-nano"
    return provider


@pytest.fixture
def authenticated_client(test_client, mock_provider):
    """Test client with authentication and mocked provider."""
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider

    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Test User",
        "provider": "google",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    yield test_client, auth_headers, mock_provider

    if get_bond_provider in app.dependency_overrides:
        del app.dependency_overrides[get_bond_provider]


def _make_mock_agent(agent_id: str, name: str):
    """Helper to create a mock agent instance."""
    agent = MagicMock(spec=AgentABC)
    agent.get_agent_id.return_value = agent_id
    agent.get_name.return_value = name
    return agent


def _make_mock_agent_record(agent_id: str, name: str, owner_user_id: str, default_group_id=None):
    """Helper to create a mock agent record."""
    record = MagicMock()
    record.agent_id = agent_id
    record.name = name
    record.owner_user_id = owner_user_id
    record.default_group_id = default_group_id
    record.is_default = False
    return record


# --- Tests ---

class TestCreateAgentSetsDefaultGroupId:
    """Test that creating an agent stores default_group_id on the record."""

    @patch('bondable.rest.routers.agents.AgentDefinition')
    def test_create_agent_stores_default_group_id(self, mock_agent_def_cls, authenticated_client):
        """Creating an agent should call set_default_group_id after group creation."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_test123"
        group_id = "grp_test456"
        mock_agent = _make_mock_agent(agent_id, "Test Agent")

        # Mock AgentDefinition constructor to avoid real provider init
        mock_agent_def_cls.return_value = _make_mock_agent_definition(name="Test Agent")

        provider.agents.create_or_update_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.groups.create_default_group_and_associate.return_value = group_id

        response = client.post(
            "/agents",
            json={
                "name": "Test Agent",
                "instructions": "Test instructions",
            },
            headers=headers,
        )

        assert response.status_code == 201
        # Verify default group was created
        provider.groups.create_default_group_and_associate.assert_called_once_with(
            agent_name="Test Agent",
            agent_id=agent_id,
            user_id=TEST_USER_ID
        )
        # Verify default_group_id was stored on the agent record
        provider.agents.set_default_group_id.assert_called_once_with(
            agent_id=agent_id,
            default_group_id=group_id
        )

    @patch('bondable.rest.routers.agents.AgentDefinition')
    def test_create_agent_with_apostrophe_stores_default_group_id(self, mock_agent_def_cls, authenticated_client):
        """Agent with apostrophe in name should still get default_group_id stored."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_apostrophe"
        group_id = "grp_apostrophe_group"
        mock_agent = _make_mock_agent(agent_id, "john's prompt")

        mock_agent_def_cls.return_value = _make_mock_agent_definition(name="john's prompt")

        provider.agents.create_or_update_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.groups.create_default_group_and_associate.return_value = group_id

        response = client.post(
            "/agents",
            json={
                "name": "john's prompt",
                "instructions": "Test instructions with apostrophe",
            },
            headers=headers,
        )

        assert response.status_code == 201
        provider.groups.create_default_group_and_associate.assert_called_once_with(
            agent_name="john's prompt",
            agent_id=agent_id,
            user_id=TEST_USER_ID
        )
        provider.agents.set_default_group_id.assert_called_once_with(
            agent_id=agent_id,
            default_group_id=group_id
        )


class TestGetAgentDetailsReturnsDefaultGroupId:
    """Test that GET /agents/{id} returns default_group_id."""

    def test_get_agent_details_includes_default_group_id(self, authenticated_client):
        """Agent detail response should include default_group_id."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_detail_test"
        group_id = "grp_detail_test"

        mock_agent = _make_mock_agent(agent_id, "Detail Test Agent")
        mock_record = _make_mock_agent_record(
            agent_id, "Detail Test Agent", TEST_USER_ID, default_group_id=group_id
        )

        # get_agent_definition() is on the agent instance, not the provider
        mock_def = _make_mock_agent_definition(
            id=agent_id, name="Detail Test Agent",
            description="Test", instructions="Test instructions",
            model="test-model"
        )
        mock_agent.get_agent_definition.return_value = mock_def

        provider.agents.get_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record
        provider.groups.get_agent_group_ids.return_value = [group_id]

        response = client.get(f"/agents/{agent_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["default_group_id"] == group_id

    def test_get_agent_details_null_default_group_id_for_old_agents(self, authenticated_client):
        """Old agents without default_group_id should return null."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_old"
        mock_agent = _make_mock_agent(agent_id, "Old Agent")
        mock_record = _make_mock_agent_record(
            agent_id, "Old Agent", TEST_USER_ID, default_group_id=None
        )

        mock_def = _make_mock_agent_definition(
            id=agent_id, name="Old Agent",
            description="Test", instructions="Test instructions",
            model="test-model"
        )
        mock_agent.get_agent_definition.return_value = mock_def

        provider.agents.get_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record
        provider.groups.get_agent_group_ids.return_value = []

        response = client.get(f"/agents/{agent_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["default_group_id"] is None


class TestRenamedAgentStillShareable:
    """Test that renaming an agent doesn't break sharing.

    This is the actual bug scenario: create agent as "Pirate", rename to
    "Pirate's Agent". The default group is still "Pirate Default Group" but
    old code looked for "Pirate's Agent Default Group" which doesn't exist.
    """

    def test_get_renamed_agent_returns_correct_default_group_id(self, authenticated_client):
        """Renamed agent should still return its original default_group_id."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_renamed_get"
        original_group_id = "grp_pirate_default"

        # Agent renamed from "Pirate" to "Pirate's Agent"
        mock_agent = _make_mock_agent(agent_id, "Pirate's Agent")
        mock_record = _make_mock_agent_record(
            agent_id, "Pirate's Agent", TEST_USER_ID,
            default_group_id=original_group_id
        )

        mock_def = _make_mock_agent_definition(
            id=agent_id, name="Pirate's Agent",
            description="A pirate agent", instructions="Talk like a pirate",
            model="test-model"
        )
        mock_agent.get_agent_definition.return_value = mock_def

        provider.agents.get_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record
        provider.groups.get_agent_group_ids.return_value = [original_group_id]

        response = client.get(f"/agents/{agent_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # default_group_id should be the original group, not affected by rename
        assert data["default_group_id"] == original_group_id


class TestUpdateAgentPreservesDefaultGroup:
    """Test that updating an agent preserves the default group."""

    @patch('bondable.rest.routers.agents.AgentDefinition')
    def test_update_agent_preserves_default_group_via_id(self, mock_agent_def_cls, authenticated_client):
        """Update should use default_group_id (not name matching) to preserve the default group."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_update_test"
        default_group_id = "grp_default_preserve"
        additional_group_id = "grp_additional"

        mock_agent = _make_mock_agent(agent_id, "john's agent")
        mock_record = _make_mock_agent_record(
            agent_id, "john's agent", TEST_USER_ID, default_group_id=default_group_id
        )

        mock_agent_def_cls.return_value = _make_mock_agent_definition(name="john's agent")

        provider.agents.create_or_update_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record

        response = client.put(
            f"/agents/{agent_id}",
            json={
                "name": "john's agent",
                "instructions": "Updated instructions",
                "group_ids": [additional_group_id],
            },
            headers=headers,
        )

        assert response.status_code == 200
        # Verify sync_agent_groups was called with the default group in preserve_group_ids
        provider.groups.sync_agent_groups.assert_called_once_with(
            agent_id=agent_id,
            desired_group_ids=[additional_group_id],
            preserve_group_ids=[default_group_id]
        )

    @patch('bondable.rest.routers.agents.AgentDefinition')
    def test_update_renamed_agent_preserves_default_group(self, mock_agent_def_cls, authenticated_client):
        """Renaming an agent should still preserve the default group via ID, not name.

        This is the core bug scenario: agent created as "Pirate", then renamed
        to "Pirate's Agent". The old name-matching code would look for
        "Pirate's Agent Default Group" which doesn't exist — the actual group
        is "Pirate Default Group". Using default_group_id bypasses this entirely.
        """
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_renamed"
        default_group_id = "grp_original_default"
        additional_group_id = "grp_extra"

        # Agent was originally "Pirate", now renamed to "Pirate's Agent"
        mock_agent = _make_mock_agent(agent_id, "Pirate's Agent")
        mock_record = _make_mock_agent_record(
            agent_id, "Pirate's Agent", TEST_USER_ID, default_group_id=default_group_id
        )

        mock_agent_def_cls.return_value = _make_mock_agent_definition(name="Pirate's Agent")

        provider.agents.create_or_update_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record

        response = client.put(
            f"/agents/{agent_id}",
            json={
                "name": "Pirate's Agent",
                "instructions": "Updated instructions",
                "group_ids": [additional_group_id],
            },
            headers=headers,
        )

        assert response.status_code == 200
        # The default group ("Pirate Default Group") should be preserved via ID
        # even though no group named "Pirate's Agent Default Group" exists
        provider.groups.sync_agent_groups.assert_called_once_with(
            agent_id=agent_id,
            desired_group_ids=[additional_group_id],
            preserve_group_ids=[default_group_id]
        )

    @patch('bondable.rest.routers.agents.AgentDefinition')
    def test_update_agent_no_default_group_id_still_works(self, mock_agent_def_cls, authenticated_client):
        """Update should handle agents without default_group_id gracefully."""
        client, headers, provider = authenticated_client

        agent_id = "bedrock_agent_no_default"
        mock_agent = _make_mock_agent(agent_id, "No Default Group Agent")
        mock_record = _make_mock_agent_record(
            agent_id, "No Default Group Agent", TEST_USER_ID, default_group_id=None
        )

        mock_agent_def_cls.return_value = _make_mock_agent_definition(name="No Default Group Agent")

        provider.agents.create_or_update_agent.return_value = mock_agent
        provider.agents.can_user_access_agent.return_value = True
        provider.agents.get_agent_record.return_value = mock_record

        response = client.put(
            f"/agents/{agent_id}",
            json={
                "name": "No Default Group Agent",
                "instructions": "Updated",
                "group_ids": ["grp_some_group"],
            },
            headers=headers,
        )

        assert response.status_code == 200
        # preserve_group_ids should be empty when default_group_id is None
        provider.groups.sync_agent_groups.assert_called_once_with(
            agent_id=agent_id,
            desired_group_ids=["grp_some_group"],
            preserve_group_ids=[]
        )


class TestBackfillDefaultGroupIds:
    """Test the backfill migration logic."""

    def test_backfill_matches_by_name_and_owner(self):
        """Backfill should match default groups by name pattern and owner."""
        from bondable.bond.providers.metadata import (
            Metadata, Base, AgentRecord, Group, AgentGroup, GroupUser, User
        )

        # Create a temporary database for testing
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_url = f"sqlite:///{db_file.name}"

        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            engine = create_engine(db_url, echo=False)
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()

            # Create a user
            user = User(
                id="user_backfill",
                email="backfill@test.com",
                sign_in_method="test",
                name="Backfill User"
            )
            session.add(user)
            session.commit()

            # Create an agent with apostrophe in name (no default_group_id)
            agent = AgentRecord(
                agent_id="agent_apostrophe",
                name="john's prompt",
                owner_user_id="user_backfill",
                is_default=False,
                default_group_id=None
            )
            session.add(agent)

            # Create the default group
            group = Group(
                id="grp_backfill_default",
                name="john's prompt Default Group",
                owner_user_id="user_backfill"
            )
            session.add(group)

            # Link agent to group
            ag = AgentGroup(
                agent_id="agent_apostrophe",
                group_id="grp_backfill_default"
            )
            session.add(ag)
            session.commit()

            # Verify agent has no default_group_id
            agent_before = session.query(AgentRecord).filter_by(agent_id="agent_apostrophe").first()
            assert agent_before.default_group_id is None

            session.close()

            # Run backfill via a test Metadata instance
            class TestMetadata(Metadata):
                def __init__(self, db_url):
                    self.metadata_db_url = db_url
                    self.engine = engine
                    self.session = None

            metadata = TestMetadata(db_url)
            metadata._backfill_default_group_ids()

            # Verify backfill worked
            session2 = Session()
            agent_after = session2.query(AgentRecord).filter_by(agent_id="agent_apostrophe").first()
            assert agent_after.default_group_id == "grp_backfill_default"
            session2.close()

        finally:
            os.unlink(db_file.name)

    def test_backfill_skips_default_home_agent(self):
        """Backfill should skip the default Home agent."""
        from bondable.bond.providers.metadata import (
            Base, AgentRecord, User
        )
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_url = f"sqlite:///{db_file.name}"

        try:
            engine = create_engine(db_url, echo=False)
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()

            user = User(
                id="user_home",
                email="home@test.com",
                sign_in_method="test",
                name="Home User"
            )
            session.add(user)

            # Default Home agent (is_default=True) should be skipped
            home_agent = AgentRecord(
                agent_id="home_agent",
                name="Home",
                owner_user_id="user_home",
                is_default=True,
                default_group_id=None
            )
            session.add(home_agent)
            session.commit()
            session.close()

            from bondable.bond.providers.metadata import Metadata
            class TestMetadata(Metadata):
                def __init__(self, db_url):
                    self.metadata_db_url = db_url
                    self.engine = engine
                    self.session = None

            metadata = TestMetadata(db_url)
            metadata._backfill_default_group_ids()

            session2 = Session()
            home_after = session2.query(AgentRecord).filter_by(agent_id="home_agent").first()
            assert home_after.default_group_id is None  # Should remain None
            session2.close()

        finally:
            os.unlink(db_file.name)
