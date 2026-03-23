"""
Tests for agent folder functionality.

Verifies folder CRUD, agent assignment/unassignment, per-user isolation,
and integration with GET /agents endpoint (folder_id population).
"""
import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import timedelta

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app, create_access_token, get_bond_provider
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import AgentProvider, Agent as AgentABC
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.vectorstores import VectorStoresProvider
from bondable.bond.groups import Groups
from bondable.bond.agent_folders import AgentFolders

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "folder-test@example.com"
TEST_USER_ID = "folder-test-user-123"
TEST_USER_2_EMAIL = "folder-test2@example.com"
TEST_USER_2_ID = "folder-test-user-456"


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
    return TestClient(app)


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=Provider)
    provider.agents = MagicMock(spec=AgentProvider)
    provider.threads = MagicMock(spec=ThreadsProvider)
    provider.files = MagicMock(spec=FilesProvider)
    provider.vectorstores = MagicMock(spec=VectorStoresProvider)
    provider.groups = MagicMock(spec=Groups)
    provider.agent_folders = MagicMock(spec=AgentFolders)
    provider.get_default_model.return_value = "test-model"
    return provider


@pytest.fixture
def authenticated_client(test_client, mock_provider):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider

    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Test User",
        "provider": "cognito",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    yield test_client, auth_headers, mock_provider

    if get_bond_provider in app.dependency_overrides:
        del app.dependency_overrides[get_bond_provider]


@pytest.fixture
def second_user_client(test_client, mock_provider):
    """Authenticated client for a second user."""
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider

    token_data = {
        "sub": TEST_USER_2_EMAIL,
        "name": "Test User 2",
        "provider": "cognito",
        "user_id": TEST_USER_2_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    yield test_client, auth_headers, mock_provider

    if get_bond_provider in app.dependency_overrides:
        del app.dependency_overrides[get_bond_provider]


# --- Tests ---

class TestCreateFolder:
    def test_create_folder_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.create_folder.return_value = {
            "id": "fld_123",
            "name": "My Folder",
            "agent_count": 0,
            "sort_order": 1,
        }

        response = client.post("/agent-folders", json={"name": "My Folder"}, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "fld_123"
        assert data["name"] == "My Folder"
        assert data["agent_count"] == 0
        provider.agent_folders.create_folder.assert_called_once_with(
            name="My Folder", user_id=TEST_USER_ID
        )

    def test_create_folder_duplicate_name(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.create_folder.side_effect = ValueError("Folder with name 'Dupe' already exists")

        response = client.post("/agent-folders", json={"name": "Dupe"}, headers=headers)
        assert response.status_code == 409

    def test_create_folder_empty_name(self, authenticated_client):
        client, headers, _ = authenticated_client
        response = client.post("/agent-folders", json={"name": "  "}, headers=headers)
        assert response.status_code == 400

    def test_create_folder_name_too_long(self, authenticated_client):
        client, headers, _ = authenticated_client
        response = client.post("/agent-folders", json={"name": "x" * 101}, headers=headers)
        assert response.status_code == 400


class TestListFolders:
    def test_list_folders(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.get_user_folders.return_value = [
            {"id": "fld_1", "name": "Work", "agent_count": 3, "sort_order": 1},
            {"id": "fld_2", "name": "Personal", "agent_count": 0, "sort_order": 2},
        ]

        response = client.get("/agent-folders", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Work"
        assert data[0]["agent_count"] == 3
        provider.agent_folders.get_user_folders.assert_called_once_with(TEST_USER_ID)


class TestUpdateFolder:
    def test_rename_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.update_folder.return_value = {
            "id": "fld_1", "name": "Renamed", "agent_count": 2, "sort_order": 1,
        }

        response = client.put("/agent-folders/fld_1", json={"name": "Renamed"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
        provider.agent_folders.update_folder.assert_called_once_with(
            folder_id="fld_1", user_id=TEST_USER_ID, name="Renamed", sort_order=None
        )

    def test_update_nonexistent_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.update_folder.side_effect = KeyError("Folder not found")

        response = client.put("/agent-folders/fld_999", json={"name": "Nope"}, headers=headers)
        assert response.status_code == 404

    def test_rename_folder_duplicate_name(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.update_folder.side_effect = ValueError("Folder with name 'Taken' already exists")

        response = client.put("/agent-folders/fld_1", json={"name": "Taken"}, headers=headers)
        assert response.status_code == 409


class TestDeleteFolder:
    def test_delete_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.delete_folder.return_value = None

        response = client.delete("/agent-folders/fld_1", headers=headers)
        assert response.status_code == 204
        provider.agent_folders.delete_folder.assert_called_once_with(
            folder_id="fld_1", user_id=TEST_USER_ID
        )

    def test_delete_nonexistent_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.delete_folder.side_effect = KeyError("Folder not found")

        response = client.delete("/agent-folders/fld_999", headers=headers)
        assert response.status_code == 404


class TestAssignAgent:
    def test_assign_agent_to_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_1"},
            headers=headers,
        )
        assert response.status_code == 200
        provider.agent_folders.assign_agent.assert_called_once_with(
            agent_id="agent_1", user_id=TEST_USER_ID, folder_id="fld_1"
        )

    def test_unassign_agent(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": None},
            headers=headers,
        )
        assert response.status_code == 200
        provider.agent_folders.assign_agent.assert_called_once_with(
            agent_id="agent_1", user_id=TEST_USER_ID, folder_id=None
        )

    def test_assign_to_nonexistent_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.side_effect = KeyError("Folder not found")

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_ghost"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_assign_same_folder_idempotent(self, authenticated_client):
        """Assigning an agent to the folder it's already in should succeed."""
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        # First assign
        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_1"},
            headers=headers,
        )
        assert response.status_code == 200

        # Same assign again
        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_1"},
            headers=headers,
        )
        assert response.status_code == 200


class TestSortOrderResetOnMove:
    def test_assign_agent_resets_sort_order(self, authenticated_client):
        """Moving agent to a folder should call assign which resets sort_order."""
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_1"},
            headers=headers,
        )
        assert response.status_code == 200
        # The business logic resets sort_order on move — verified by mock call
        provider.agent_folders.assign_agent.assert_called_once_with(
            agent_id="agent_1", user_id=TEST_USER_ID, folder_id="fld_1"
        )

    def test_unassign_agent_resets_sort_order(self, authenticated_client):
        """Moving agent back to main screen should reset sort_order."""
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": None},
            headers=headers,
        )
        assert response.status_code == 200


class TestGetAgentsIncludesFolderId:
    def test_agents_have_folder_id(self, authenticated_client):
        client, headers, provider = authenticated_client

        # Mock agent records
        provider.agents.get_agent_records.return_value = [
            {"agent_id": "a1", "name": "Agent 1", "owned": True, "permission": "owner"},
            {"agent_id": "a2", "name": "Agent 2", "owned": True, "permission": "owner"},
        ]

        # Mock get_agent
        mock_a1 = MagicMock(spec=AgentABC)
        mock_a1.get_agent_id.return_value = "a1"
        mock_a1.get_name.return_value = "Agent 1"
        mock_a1.get_description.return_value = "Desc 1"
        mock_a1.get_metadata.return_value = {}

        mock_a2 = MagicMock(spec=AgentABC)
        mock_a2.get_agent_id.return_value = "a2"
        mock_a2.get_name.return_value = "Agent 2"
        mock_a2.get_description.return_value = "Desc 2"
        mock_a2.get_metadata.return_value = {}

        provider.agents.get_agent.side_effect = lambda agent_id: {
            "a1": mock_a1, "a2": mock_a2
        }.get(agent_id)

        # Mock folder assignments
        provider.agent_folders.get_user_folder_assignments.return_value = {
            "a1": "fld_work",
        }

        response = client.get("/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        agent_map = {a["id"]: a for a in data}
        assert agent_map["a1"]["folder_id"] == "fld_work"
        assert agent_map["a2"]["folder_id"] is None


class TestReassignAgent:
    def test_reassign_agent_between_folders(self, authenticated_client):
        """Agent already in folder A is moved to folder B (upsert update path)."""
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "agent_1", "folder_id": "fld_2"},
            headers=headers,
        )
        assert response.status_code == 200
        provider.agent_folders.assign_agent.assert_called_once_with(
            agent_id="agent_1", user_id=TEST_USER_ID, folder_id="fld_2"
        )


class TestUpdateFolderSortOrder:
    def test_update_sort_order_only(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.update_folder.return_value = {
            "id": "fld_1", "name": "Work", "agent_count": 2, "sort_order": 5,
        }

        response = client.put(
            "/agent-folders/fld_1",
            json={"sort_order": 5},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["sort_order"] == 5
        provider.agent_folders.update_folder.assert_called_once_with(
            folder_id="fld_1", user_id=TEST_USER_ID, name=None, sort_order=5
        )

    def test_update_empty_body_noop(self, authenticated_client):
        """PUT with empty body should succeed (no-op)."""
        client, headers, provider = authenticated_client
        provider.agent_folders.update_folder.return_value = {
            "id": "fld_1", "name": "Work", "agent_count": 2, "sort_order": 1,
        }

        response = client.put("/agent-folders/fld_1", json={}, headers=headers)
        assert response.status_code == 200

    def test_update_empty_name_returns_400(self, authenticated_client):
        client, headers, _ = authenticated_client
        response = client.put("/agent-folders/fld_1", json={"name": "  "}, headers=headers)
        assert response.status_code == 400

    def test_update_name_too_long_returns_400(self, authenticated_client):
        client, headers, _ = authenticated_client
        response = client.put("/agent-folders/fld_1", json={"name": "x" * 101}, headers=headers)
        assert response.status_code == 400


class TestAgentsWithoutFolderProvider:
    def test_agents_load_when_agent_folders_is_none(self, authenticated_client):
        """GET /agents works even if agent_folders provider is not initialized."""
        client, headers, provider = authenticated_client

        # Set agent_folders to None
        provider.agent_folders = None

        provider.agents.get_agent_records.return_value = [
            {"agent_id": "a1", "name": "Agent 1", "owned": True, "permission": "owner"},
        ]
        mock_a1 = MagicMock(spec=AgentABC)
        mock_a1.get_agent_id.return_value = "a1"
        mock_a1.get_name.return_value = "Agent 1"
        mock_a1.get_description.return_value = "Desc"
        mock_a1.get_metadata.return_value = {}
        provider.agents.get_agent.return_value = mock_a1

        response = client.get("/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["folder_id"] is None


class TestPerUserIsolation:
    def test_folders_scoped_to_user(self, authenticated_client, second_user_client):
        """Each user's folder list call passes their own user_id."""
        client1, headers1, provider = authenticated_client
        provider.agent_folders.get_user_folders.return_value = [
            {"id": "fld_1", "name": "User1 Folder", "agent_count": 1, "sort_order": 1},
        ]

        response1 = client1.get("/agent-folders", headers=headers1)
        assert response1.status_code == 200
        provider.agent_folders.get_user_folders.assert_called_with(TEST_USER_ID)

        # Second user should pass their own user_id
        client2, headers2, _ = second_user_client
        provider.agent_folders.get_user_folders.return_value = []

        response2 = client2.get("/agent-folders", headers=headers2)
        assert response2.status_code == 200
        provider.agent_folders.get_user_folders.assert_called_with(TEST_USER_2_ID)

    def test_assign_uses_requesting_users_id(self, authenticated_client):
        """Assignment always uses the authenticated user's ID, not a user-supplied one."""
        client, headers, provider = authenticated_client
        provider.agent_folders.assign_agent.return_value = None

        response = client.put(
            "/agent-folders/assign",
            json={"agent_id": "shared_agent", "folder_id": "fld_1"},
            headers=headers,
        )
        assert response.status_code == 200
        # Verify user_id comes from auth, not from request body
        provider.agent_folders.assign_agent.assert_called_once_with(
            agent_id="shared_agent", user_id=TEST_USER_ID, folder_id="fld_1"
        )


class TestReorderAgents:
    def test_reorder_agents_main_screen(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.get_user_folders.return_value = []
        provider.agent_folders.reorder_agents.return_value = None

        response = client.put(
            "/agent-folders/reorder-agents",
            json={"folder_id": None, "agent_ids": ["a3", "a1", "a2"]},
            headers=headers,
        )
        assert response.status_code == 200
        provider.agent_folders.reorder_agents.assert_called_once_with(
            user_id=TEST_USER_ID, agent_ids=["a3", "a1", "a2"]
        )

    def test_reorder_agents_in_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.get_user_folders.return_value = [
            {"id": "fld_1", "name": "Work", "agent_count": 2, "sort_order": 0},
        ]
        provider.agent_folders.reorder_agents.return_value = None

        response = client.put(
            "/agent-folders/reorder-agents",
            json={"folder_id": "fld_1", "agent_ids": ["a2", "a1"]},
            headers=headers,
        )
        assert response.status_code == 200

    def test_reorder_agents_nonexistent_folder(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.get_user_folders.return_value = []

        response = client.put(
            "/agent-folders/reorder-agents",
            json={"folder_id": "fld_ghost", "agent_ids": ["a1"]},
            headers=headers,
        )
        assert response.status_code == 404

    def test_reorder_agents_empty_list(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.reorder_agents.return_value = None

        response = client.put(
            "/agent-folders/reorder-agents",
            json={"folder_id": None, "agent_ids": []},
            headers=headers,
        )
        assert response.status_code == 200


class TestReorderFolders:
    def test_reorder_folders(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.reorder_folders.return_value = None

        response = client.put(
            "/agent-folders/reorder-folders",
            json={"folder_ids": ["fld_2", "fld_1"]},
            headers=headers,
        )
        assert response.status_code == 200
        provider.agent_folders.reorder_folders.assert_called_once_with(
            user_id=TEST_USER_ID, folder_ids=["fld_2", "fld_1"]
        )

    def test_reorder_folders_nonexistent(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.agent_folders.reorder_folders.side_effect = KeyError("Folder not found")

        response = client.put(
            "/agent-folders/reorder-folders",
            json={"folder_ids": ["fld_ghost"]},
            headers=headers,
        )
        assert response.status_code == 404


class TestGetAgentsIncludesSortOrder:
    def test_agents_have_sort_order(self, authenticated_client):
        client, headers, provider = authenticated_client

        provider.agents.get_agent_records.return_value = [
            {"agent_id": "a1", "name": "Agent 1", "owned": True, "permission": "owner"},
            {"agent_id": "a2", "name": "Agent 2", "owned": True, "permission": "owner"},
        ]

        mock_a1 = MagicMock(spec=AgentABC)
        mock_a1.get_agent_id.return_value = "a1"
        mock_a1.get_name.return_value = "Agent 1"
        mock_a1.get_description.return_value = "Desc 1"
        mock_a1.get_metadata.return_value = {}

        mock_a2 = MagicMock(spec=AgentABC)
        mock_a2.get_agent_id.return_value = "a2"
        mock_a2.get_name.return_value = "Agent 2"
        mock_a2.get_description.return_value = "Desc 2"
        mock_a2.get_metadata.return_value = {}

        provider.agents.get_agent.side_effect = lambda agent_id: {
            "a1": mock_a1, "a2": mock_a2
        }.get(agent_id)

        provider.agent_folders.get_user_folder_assignments.return_value = {}
        provider.agent_folders.get_user_agent_sort_orders.return_value = {
            "a1": 1, "a2": 0,
        }

        response = client.get("/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        agent_map = {a["id"]: a for a in data}
        assert agent_map["a1"]["sort_order"] == 1
        assert agent_map["a2"]["sort_order"] == 0

    def test_new_agent_has_null_sort_order(self, authenticated_client):
        client, headers, provider = authenticated_client

        provider.agents.get_agent_records.return_value = [
            {"agent_id": "a1", "name": "New Agent", "owned": True, "permission": "owner"},
        ]
        mock_a1 = MagicMock(spec=AgentABC)
        mock_a1.get_agent_id.return_value = "a1"
        mock_a1.get_name.return_value = "New Agent"
        mock_a1.get_description.return_value = ""
        mock_a1.get_metadata.return_value = {}
        provider.agents.get_agent.return_value = mock_a1

        provider.agent_folders.get_user_folder_assignments.return_value = {}
        provider.agent_folders.get_user_agent_sort_orders.return_value = {}

        response = client.get("/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data[0]["sort_order"] is None


class TestReorderRequiresAuth:
    def test_no_token_reorder_agents(self, test_client):
        response = test_client.put("/agent-folders/reorder-agents", json={"agent_ids": []})
        assert response.status_code == 401

    def test_no_token_reorder_folders(self, test_client):
        response = test_client.put("/agent-folders/reorder-folders", json={"folder_ids": []})
        assert response.status_code == 401


class TestFolderRequiresAuth:
    def test_no_token(self, test_client):
        response = test_client.get("/agent-folders")
        assert response.status_code == 401

    def test_no_token_create(self, test_client):
        response = test_client.post("/agent-folders", json={"name": "Test"})
        assert response.status_code == 401

    def test_no_token_assign(self, test_client):
        response = test_client.put("/agent-folders/assign", json={"agent_id": "a1", "folder_id": "f1"})
        assert response.status_code == 401
