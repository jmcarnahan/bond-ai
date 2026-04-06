"""
Integration tests for the 'Everyone' group feature.

Verifies that agents associated with the well-known Everyone group (grp_everyone)
are accessible to all authenticated users without explicit group_users membership.
"""
import pytest
import os
import tempfile

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_DB_URL

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from bondable.bond.providers.metadata import (
    Base, User, Group, AgentRecord, AgentGroup, GroupUser,
    EVERYONE_GROUP_ID,
)

USER_A = "everyone-test-user-a"
USER_B = "everyone-test-user-b"
SYSTEM_USER = "everyone-test-system"
AGENT_PUBLIC = "agent_public_001"
AGENT_PRIVATE = "agent_private_002"
AGENT_BOTH = "agent_both_003"


class FakeMetadata:
    """Minimal Metadata-like object with a real SQLite DB."""
    def __init__(self, db_url):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self._session_factory = scoped_session(sessionmaker(bind=self.engine))

    def get_db_session(self):
        return self._session_factory()


class FakeAgentProvider:
    """
    Minimal AgentProvider that exposes only the three access-control methods
    under test, using real SQL queries against a test database.
    """
    def __init__(self, metadata):
        self.metadata = metadata

    # Import the real implementations by delegation
    from bondable.bond.providers.agent import AgentProvider as _AP
    can_user_access_agent = _AP.can_user_access_agent
    get_agent_records = _AP.get_agent_records
    get_user_agent_permission = _AP.get_user_agent_permission


@pytest.fixture(scope="module")
def db():
    metadata = FakeMetadata(TEST_DB_URL)
    session = metadata.get_db_session()

    # Seed users (unique emails to avoid conflicts when running with other test files)
    for uid, email in [
        (SYSTEM_USER, "everyone-test-system@test.com"),
        (USER_A, "everyone-test-a@test.com"),
        (USER_B, "everyone-test-b@test.com"),
    ]:
        if not session.query(User).filter(User.id == uid).first():
            session.add(User(id=uid, email=email, sign_in_method="test"))

    # Seed Everyone group
    if not session.query(Group).filter(Group.id == EVERYONE_GROUP_ID).first():
        session.add(Group(
            id=EVERYONE_GROUP_ID,
            name="Everyone",
            description="Agents in this group are accessible to all users",
            owner_user_id=SYSTEM_USER,
        ))

    # Seed a private group for USER_A only
    private_group_id = "grp_private_test"
    if not session.query(Group).filter(Group.id == private_group_id).first():
        session.add(Group(id=private_group_id, name="Private Group", owner_user_id=USER_A))
        session.flush()
        session.add(GroupUser(group_id=private_group_id, user_id=USER_A))

    session.commit()
    session.close()
    return metadata


@pytest.fixture(scope="module")
def provider(db):
    return FakeAgentProvider(db)


@pytest.fixture(autouse=True)
def clear_agents(db):
    """Clear agent-related tables before each test."""
    session = db.get_db_session()
    session.query(AgentGroup).delete()
    session.query(AgentRecord).delete()
    session.commit()
    session.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup_db():
    yield
    db_path = TEST_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


def _create_agent(db, agent_id, name, owner_user_id):
    session = db.get_db_session()
    session.add(AgentRecord(
        agent_id=agent_id, name=name, owner_user_id=owner_user_id
    ))
    session.commit()
    session.close()


def _add_agent_to_group(db, agent_id, group_id, permission="can_use"):
    session = db.get_db_session()
    session.add(AgentGroup(agent_id=agent_id, group_id=group_id, permission=permission))
    session.commit()
    session.close()


class TestCanUserAccessAgent:
    """Test can_user_access_agent with Everyone group."""

    def test_everyone_group_grants_access(self, db, provider):
        """User NOT in any group can access agent in Everyone group."""
        _create_agent(db, AGENT_PUBLIC, "Public Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID)

        # USER_B has no group membership at all
        assert provider.can_user_access_agent(USER_B, AGENT_PUBLIC) is True

    def test_private_agent_not_accessible_without_group(self, db, provider):
        """Agent NOT in Everyone group is inaccessible to non-members."""
        _create_agent(db, AGENT_PRIVATE, "Private Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PRIVATE, "grp_private_test")

        # USER_B is not in the private group
        assert provider.can_user_access_agent(USER_B, AGENT_PRIVATE) is False

    def test_owner_still_has_access(self, db, provider):
        """Agent owner can access agent regardless of Everyone group."""
        _create_agent(db, AGENT_PRIVATE, "My Agent", USER_A)
        assert provider.can_user_access_agent(USER_A, AGENT_PRIVATE) is True


class TestGetAgentRecords:
    """Test get_agent_records includes Everyone group agents."""

    def test_everyone_agent_appears_in_list(self, db, provider):
        """Agent in Everyone group appears in any user's agent list."""
        _create_agent(db, AGENT_PUBLIC, "Public Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID)

        records = provider.get_agent_records(USER_B)
        agent_ids = [r["agent_id"] for r in records]
        assert AGENT_PUBLIC in agent_ids

    def test_everyone_agent_has_correct_permission(self, db, provider):
        """Everyone group agent shows with the permission from agent_groups."""
        _create_agent(db, AGENT_PUBLIC, "Public Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID, permission="can_use")

        records = provider.get_agent_records(USER_B)
        public_record = next(r for r in records if r["agent_id"] == AGENT_PUBLIC)
        assert public_record["permission"] == "can_use"
        assert public_record["owned"] is False

    def test_private_agent_not_in_list_for_non_member(self, db, provider):
        """Agent NOT in Everyone group does not appear for non-members."""
        _create_agent(db, AGENT_PRIVATE, "Private Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PRIVATE, "grp_private_test")

        records = provider.get_agent_records(USER_B)
        agent_ids = [r["agent_id"] for r in records]
        assert AGENT_PRIVATE not in agent_ids


class TestGetUserAgentPermission:
    """Test get_user_agent_permission with Everyone group."""

    def test_everyone_group_permission(self, db, provider):
        """User gets permission from Everyone group's agent_groups row."""
        _create_agent(db, AGENT_PUBLIC, "Public Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID, permission="can_use")

        perm = provider.get_user_agent_permission(USER_B, AGENT_PUBLIC)
        assert perm == "can_use"

    def test_no_permission_without_everyone_or_group(self, db, provider):
        """User gets None for agent they have no access to."""
        _create_agent(db, AGENT_PRIVATE, "Private Agent", SYSTEM_USER)
        # No group association at all

        perm = provider.get_user_agent_permission(USER_B, AGENT_PRIVATE)
        assert perm is None

    def test_permission_stacking_highest_wins(self, db, provider):
        """User in can_edit group + Everyone (can_use) gets can_edit."""
        _create_agent(db, AGENT_BOTH, "Both Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_BOTH, EVERYONE_GROUP_ID, permission="can_use")
        _add_agent_to_group(db, AGENT_BOTH, "grp_private_test", permission="can_edit")

        # USER_A is in grp_private_test with can_edit, plus Everyone with can_use
        perm = provider.get_user_agent_permission(USER_A, AGENT_BOTH)
        assert perm == "can_edit"

    def test_owner_permission_takes_precedence(self, db, provider):
        """Owner gets 'owner' even if agent is in Everyone group."""
        _create_agent(db, AGENT_PUBLIC, "Public Agent", USER_A)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID)

        perm = provider.get_user_agent_permission(USER_A, AGENT_PUBLIC)
        assert perm == "owner"


class TestSyncPreservesEveryoneGroup:
    """Test that sync_agent_groups preserves the Everyone group."""

    def test_sync_does_not_remove_everyone_group(self, db):
        """sync_agent_groups with preserve should keep Everyone group."""
        from bondable.bond.groups import Groups
        groups = Groups(db)

        _create_agent(db, AGENT_PUBLIC, "Public Agent", SYSTEM_USER)
        _add_agent_to_group(db, AGENT_PUBLIC, EVERYONE_GROUP_ID)

        # Sync with empty desired list, but preserve Everyone group
        groups.sync_agent_groups(
            agent_id=AGENT_PUBLIC,
            desired_group_ids=[],
            preserve_group_ids=[EVERYONE_GROUP_ID],
        )

        # Verify Everyone group association still exists
        session = db.get_db_session()
        remaining = session.query(AgentGroup).filter(
            AgentGroup.agent_id == AGENT_PUBLIC,
            AgentGroup.group_id == EVERYONE_GROUP_ID,
        ).first()
        session.close()
        assert remaining is not None


class TestEnsureEveryoneGroupAutoCreation:
    """Test that the Everyone group is auto-created on Metadata init."""

    def test_everyone_group_exists_after_init(self):
        """_ensure_everyone_group creates the group if missing."""
        # Use a fresh temp DB
        fresh_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        fresh_db_url = f"sqlite:///{fresh_db_file.name}"

        try:
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata
            metadata = BedrockMetadata(fresh_db_url)

            session = metadata.get_db_session()
            group = session.query(Group).filter(Group.id == EVERYONE_GROUP_ID).first()
            assert group is not None
            assert group.name == "Everyone"
            session.close()
            metadata.close()
        finally:
            if os.path.exists(fresh_db_file.name):
                os.remove(fresh_db_file.name)
