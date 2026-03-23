"""
Integration tests for AgentFolders business logic against a real SQLite database.

These tests exercise the actual SQL queries, cascade deletes, sort order reset,
and per-user isolation — unlike the API-level tests which mock the business logic.
"""
import pytest
import os
import tempfile

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_DB_URL

from bondable.bond.providers.metadata import (
    Base, AgentFolder, AgentFolderAssignment, UserAgentSortOrder, User
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from bondable.bond.agent_folders import AgentFolders

USER_A = "user-a-id"
USER_B = "user-b-id"


class FakeMetadata:
    """Minimal Metadata-like object for testing with a real SQLite DB."""
    def __init__(self, db_url):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self._session_factory = scoped_session(sessionmaker(bind=self.engine))

        # Create test users
        session = self._session_factory()
        for uid, email in [(USER_A, "a@test.com"), (USER_B, "b@test.com")]:
            if not session.query(User).filter(User.id == uid).first():
                session.add(User(id=uid, email=email, sign_in_method="test"))
        session.commit()
        session.close()

    def get_db_session(self):
        return self._session_factory()


@pytest.fixture(scope="module")
def agent_folders():
    metadata = FakeMetadata(TEST_DB_URL)
    return AgentFolders(metadata)


@pytest.fixture(scope="module", autouse=True)
def cleanup_db():
    yield
    db_path = TEST_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clear_tables(agent_folders):
    """Clear folder-related tables before each test."""
    session = agent_folders.metadata.get_db_session()
    session.query(UserAgentSortOrder).delete()
    session.query(AgentFolderAssignment).delete()
    session.query(AgentFolder).delete()
    session.commit()
    session.close()


class TestFolderCRUD:
    def test_create_and_list_folders(self, agent_folders):
        agent_folders.create_folder("Work", USER_A)
        agent_folders.create_folder("Personal", USER_A)
        folders = agent_folders.get_user_folders(USER_A)
        assert len(folders) == 2
        names = [f["name"] for f in folders]
        assert "Work" in names
        assert "Personal" in names

    def test_duplicate_name_raises_value_error(self, agent_folders):
        agent_folders.create_folder("Dupe", USER_A)
        with pytest.raises(ValueError, match="already exists"):
            agent_folders.create_folder("Dupe", USER_A)

    def test_same_name_different_users(self, agent_folders):
        agent_folders.create_folder("Shared Name", USER_A)
        agent_folders.create_folder("Shared Name", USER_B)
        assert len(agent_folders.get_user_folders(USER_A)) == 1
        assert len(agent_folders.get_user_folders(USER_B)) == 1

    def test_rename_folder(self, agent_folders):
        folder = agent_folders.create_folder("Old", USER_A)
        result = agent_folders.update_folder(folder["id"], USER_A, name="New")
        assert result["name"] == "New"

    def test_rename_to_duplicate_raises_value_error(self, agent_folders):
        agent_folders.create_folder("Taken", USER_A)
        folder2 = agent_folders.create_folder("Other", USER_A)
        with pytest.raises(ValueError, match="already exists"):
            agent_folders.update_folder(folder2["id"], USER_A, name="Taken")

    def test_delete_folder(self, agent_folders):
        folder = agent_folders.create_folder("ToDelete", USER_A)
        agent_folders.delete_folder(folder["id"], USER_A)
        assert len(agent_folders.get_user_folders(USER_A)) == 0

    def test_delete_nonexistent_folder_raises_key_error(self, agent_folders):
        with pytest.raises(KeyError):
            agent_folders.delete_folder("fake_id", USER_A)

    def test_cannot_delete_other_users_folder(self, agent_folders):
        folder = agent_folders.create_folder("Private", USER_A)
        with pytest.raises(KeyError):
            agent_folders.delete_folder(folder["id"], USER_B)


class TestAgentAssignment:
    def test_assign_and_get_assignments(self, agent_folders):
        folder = agent_folders.create_folder("Work", USER_A)
        agent_folders.assign_agent("agent_1", USER_A, folder["id"])
        assignments = agent_folders.get_user_folder_assignments(USER_A)
        assert assignments == {"agent_1": folder["id"]}

    def test_unassign_agent(self, agent_folders):
        folder = agent_folders.create_folder("Work", USER_A)
        agent_folders.assign_agent("agent_1", USER_A, folder["id"])
        agent_folders.assign_agent("agent_1", USER_A, None)
        assignments = agent_folders.get_user_folder_assignments(USER_A)
        assert "agent_1" not in assignments

    def test_reassign_between_folders(self, agent_folders):
        f1 = agent_folders.create_folder("Folder1", USER_A)
        f2 = agent_folders.create_folder("Folder2", USER_A)
        agent_folders.assign_agent("agent_1", USER_A, f1["id"])
        agent_folders.assign_agent("agent_1", USER_A, f2["id"])
        assignments = agent_folders.get_user_folder_assignments(USER_A)
        assert assignments["agent_1"] == f2["id"]

    def test_assign_to_nonexistent_folder_raises_key_error(self, agent_folders):
        with pytest.raises(KeyError):
            agent_folders.assign_agent("agent_1", USER_A, "fake_folder")

    def test_delete_folder_cascades_assignments(self, agent_folders):
        folder = agent_folders.create_folder("Temp", USER_A)
        agent_folders.assign_agent("agent_1", USER_A, folder["id"])
        agent_folders.assign_agent("agent_2", USER_A, folder["id"])
        agent_folders.delete_folder(folder["id"], USER_A)
        assignments = agent_folders.get_user_folder_assignments(USER_A)
        assert "agent_1" not in assignments
        assert "agent_2" not in assignments

    def test_folder_agent_count(self, agent_folders):
        folder = agent_folders.create_folder("Counted", USER_A)
        agent_folders.assign_agent("a1", USER_A, folder["id"])
        agent_folders.assign_agent("a2", USER_A, folder["id"])
        folders = agent_folders.get_user_folders(USER_A)
        assert folders[0]["agent_count"] == 2

    def test_per_user_isolation(self, agent_folders):
        f_a = agent_folders.create_folder("My Folder", USER_A)
        f_b = agent_folders.create_folder("My Folder", USER_B)
        agent_folders.assign_agent("shared_agent", USER_A, f_a["id"])
        agent_folders.assign_agent("shared_agent", USER_B, f_b["id"])

        assert agent_folders.get_user_folder_assignments(USER_A) == {"shared_agent": f_a["id"]}
        assert agent_folders.get_user_folder_assignments(USER_B) == {"shared_agent": f_b["id"]}


class TestSortOrderResetOnAssign:
    def test_assign_resets_sort_order(self, agent_folders):
        """Moving an agent to a folder should delete its sort_order row."""
        folder = agent_folders.create_folder("Work", USER_A)

        # Set a sort order for the agent
        agent_folders.reorder_agents(USER_A, ["agent_1", "agent_2"])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert orders["agent_1"] == 0

        # Move agent to folder — sort order should be cleared
        agent_folders.assign_agent("agent_1", USER_A, folder["id"])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert "agent_1" not in orders
        # agent_2's sort order should be unchanged
        assert orders["agent_2"] == 1

    def test_unassign_resets_sort_order(self, agent_folders):
        """Moving an agent back to main screen should delete its sort_order row."""
        folder = agent_folders.create_folder("Work", USER_A)
        agent_folders.assign_agent("agent_1", USER_A, folder["id"])

        # Set sort order while in folder
        agent_folders.reorder_agents(USER_A, ["agent_1"])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert orders["agent_1"] == 0

        # Move back to main — sort order should be cleared
        agent_folders.assign_agent("agent_1", USER_A, None)
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert "agent_1" not in orders


class TestReorderAgents:
    def test_reorder_sets_sort_orders(self, agent_folders):
        agent_folders.reorder_agents(USER_A, ["a3", "a1", "a2"])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert orders == {"a3": 0, "a1": 1, "a2": 2}

    def test_reorder_updates_existing(self, agent_folders):
        agent_folders.reorder_agents(USER_A, ["a1", "a2"])
        agent_folders.reorder_agents(USER_A, ["a2", "a1"])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert orders == {"a2": 0, "a1": 1}

    def test_reorder_empty_list(self, agent_folders):
        # Should not crash
        agent_folders.reorder_agents(USER_A, [])
        orders = agent_folders.get_user_agent_sort_orders(USER_A)
        assert orders == {}

    def test_reorder_isolation(self, agent_folders):
        agent_folders.reorder_agents(USER_A, ["a1", "a2"])
        agent_folders.reorder_agents(USER_B, ["a2", "a1"])
        assert agent_folders.get_user_agent_sort_orders(USER_A) == {"a1": 0, "a2": 1}
        assert agent_folders.get_user_agent_sort_orders(USER_B) == {"a2": 0, "a1": 1}


class TestReorderFolders:
    def test_reorder_folders(self, agent_folders):
        f1 = agent_folders.create_folder("Alpha", USER_A)
        f2 = agent_folders.create_folder("Beta", USER_A)
        f3 = agent_folders.create_folder("Gamma", USER_A)

        agent_folders.reorder_folders(USER_A, [f3["id"], f1["id"], f2["id"]])
        folders = agent_folders.get_user_folders(USER_A)
        assert [f["id"] for f in folders] == [f3["id"], f1["id"], f2["id"]]

    def test_reorder_nonexistent_folder_raises(self, agent_folders):
        with pytest.raises(KeyError):
            agent_folders.reorder_folders(USER_A, ["fake_id"])

    def test_reorder_other_users_folder_raises(self, agent_folders):
        folder = agent_folders.create_folder("Mine", USER_A)
        with pytest.raises(KeyError):
            agent_folders.reorder_folders(USER_B, [folder["id"]])
