"""
Tests for groups API endpoints.

Verifies group CRUD, member management, authorization checks,
and error handling for all /groups routes.
"""
import pytest
import os
import tempfile
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from datetime import timedelta, datetime

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app, create_access_token, get_bond_provider
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import AgentProvider
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.vectorstores import VectorStoresProvider
from bondable.bond.groups import Groups
from bondable.bond.agent_folders import AgentFolders

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-for-groups"

# --- Test Data ---

def _make_test_group(**overrides):
    group = {
        "id": "group-1",
        "name": "Test Group",
        "description": "A test group",
        "owner_user_id": TEST_USER_ID,
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
    }
    group.update(overrides)
    return group


def _make_test_member(**overrides):
    member = {
        "user_id": "member-1",
        "email": "member@example.com",
        "name": "Test Member",
    }
    member.update(overrides)
    return member


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


# --- Tests ---

class TestGetUserGroups:
    def test_get_groups_empty(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.get_user_groups.return_value = []

        response = client.get("/groups", headers=headers)
        assert response.status_code == 200
        assert response.json() == []
        provider.groups.get_user_groups.assert_called_once_with(TEST_USER_ID)

    def test_get_groups_populated(self, authenticated_client):
        client, headers, provider = authenticated_client
        test_group = _make_test_group()
        provider.groups.get_user_groups.return_value = [test_group]

        response = client.get("/groups", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "group-1"
        assert data[0]["name"] == "Test Group"
        assert data[0]["description"] == "A test group"
        assert data[0]["owner_user_id"] == TEST_USER_ID

    def test_get_groups_unauthorized(self, test_client):
        response = test_client.get("/groups")
        assert response.status_code == 401

    def test_get_groups_server_error(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.get_user_groups.side_effect = Exception("DB connection failed")

        response = client.get("/groups", headers=headers)
        assert response.status_code == 500


class TestGetAllUsers:
    def test_get_all_users_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        test_member = _make_test_member()
        provider.groups.get_all_users.return_value = [test_member]

        response = client.get("/groups/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "member-1"
        assert data[0]["email"] == "member@example.com"
        assert data[0]["name"] == "Test Member"

    def test_get_all_users_empty(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.get_all_users.return_value = []

        response = client.get("/groups/users", headers=headers)
        assert response.status_code == 200
        assert response.json() == []


class TestCreateGroup:
    def test_create_group_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.create_group.return_value = "group-new"
        provider.groups.get_group.return_value = _make_test_group(id="group-new", name="New Group")

        response = client.post("/groups", json={"name": "New Group"}, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "group-new"
        assert data["name"] == "New Group"
        provider.groups.create_group.assert_called_once_with(
            name="New Group",
            description=None,
            owner_user_id=TEST_USER_ID
        )

    def test_create_group_with_description(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.create_group.return_value = "group-desc"
        provider.groups.get_group.return_value = _make_test_group(
            id="group-desc", name="Described Group", description="A detailed description"
        )

        response = client.post(
            "/groups",
            json={"name": "Described Group", "description": "A detailed description"},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "A detailed description"
        provider.groups.create_group.assert_called_once_with(
            name="Described Group",
            description="A detailed description",
            owner_user_id=TEST_USER_ID
        )

    def test_create_group_unauthorized(self, test_client):
        response = test_client.post("/groups", json={"name": "No Auth"})
        assert response.status_code == 401

    def test_create_group_server_error(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.create_group.side_effect = Exception("DB error")

        response = client.post("/groups", json={"name": "Fail Group"}, headers=headers)
        assert response.status_code == 500


class TestGetGroup:
    def test_get_group_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        test_group = _make_test_group()
        test_member = _make_test_member()
        provider.groups.get_group.return_value = test_group
        provider.groups.get_group_members.return_value = [test_member]

        response = client.get("/groups/group-1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "group-1"
        assert data["name"] == "Test Group"
        assert len(data["members"]) == 1
        assert data["members"][0]["user_id"] == "member-1"

    def test_get_group_not_found(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.get_group.return_value = None

        response = client.get("/groups/nonexistent", headers=headers)
        assert response.status_code == 404

    def test_get_group_forbidden(self, authenticated_client):
        client, headers, provider = authenticated_client
        test_group = _make_test_group()
        provider.groups.get_group.return_value = test_group
        provider.groups.get_group_members.return_value = None

        response = client.get("/groups/group-1", headers=headers)
        assert response.status_code == 403


class TestUpdateGroup:
    def test_update_group_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.update_group.return_value = True
        updated_group = _make_test_group(name="Updated Name", description="Updated desc")
        provider.groups.get_group.return_value = updated_group

        response = client.put(
            "/groups/group-1",
            json={"name": "Updated Name", "description": "Updated desc"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated desc"
        provider.groups.update_group.assert_called_once_with(
            group_id="group-1",
            user_id=TEST_USER_ID,
            name="Updated Name",
            description="Updated desc"
        )

    def test_update_group_not_found(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.update_group.return_value = False
        provider.groups.get_group.return_value = None

        response = client.put(
            "/groups/nonexistent",
            json={"name": "Nope"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_update_group_forbidden(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.update_group.return_value = False
        # Group exists but owned by someone else
        provider.groups.get_group.return_value = _make_test_group(owner_user_id="other-user-id")

        response = client.put(
            "/groups/group-1",
            json={"name": "Not Allowed"},
            headers=headers,
        )
        assert response.status_code == 403


class TestDeleteGroup:
    def test_delete_group_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.delete_group.return_value = True

        response = client.delete("/groups/group-1", headers=headers)
        assert response.status_code == 204
        provider.groups.delete_group.assert_called_once_with("group-1", TEST_USER_ID)

    def test_delete_group_not_found(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.delete_group.return_value = False
        provider.groups.get_group.return_value = None

        response = client.delete("/groups/nonexistent", headers=headers)
        assert response.status_code == 404

    def test_delete_group_forbidden(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.delete_group.return_value = False
        provider.groups.get_group.return_value = _make_test_group(owner_user_id="other-user-id")

        response = client.delete("/groups/group-1", headers=headers)
        assert response.status_code == 403


class TestAddGroupMember:
    def test_add_member_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = True

        response = client.post("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 201
        provider.groups.manage_group_member.assert_called_once_with(
            group_id="group-1",
            user_id=TEST_USER_ID,
            member_user_id="member-1",
            action="add"
        )

    def test_add_member_group_not_found(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        provider.groups.get_group.return_value = None

        response = client.post("/groups/nonexistent/members/member-1", headers=headers)
        assert response.status_code == 404

    def test_add_member_forbidden(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        provider.groups.get_group.return_value = _make_test_group(owner_user_id="other-user-id")

        response = client.post("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 403

    def test_add_member_conflict(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        # Group exists and is owned by the current user
        provider.groups.get_group.return_value = _make_test_group(owner_user_id=TEST_USER_ID)
        # Target user exists in the system
        provider.groups.get_all_users.return_value = [
            _make_test_member(user_id="member-1")
        ]

        response = client.post("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]


class TestRemoveGroupMember:
    def test_remove_member_success(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = True

        response = client.delete("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 204
        provider.groups.manage_group_member.assert_called_once_with(
            group_id="group-1",
            user_id=TEST_USER_ID,
            member_user_id="member-1",
            action="remove"
        )

    def test_remove_member_group_not_found(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        provider.groups.get_group.return_value = None

        response = client.delete("/groups/nonexistent/members/member-1", headers=headers)
        assert response.status_code == 404

    def test_remove_member_forbidden(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        provider.groups.get_group.return_value = _make_test_group(owner_user_id="other-user-id")

        response = client.delete("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 403

    def test_remove_member_not_in_group(self, authenticated_client):
        client, headers, provider = authenticated_client
        provider.groups.manage_group_member.return_value = False
        # Group exists and is owned by the current user
        provider.groups.get_group.return_value = _make_test_group(owner_user_id=TEST_USER_ID)

        response = client.delete("/groups/group-1/members/member-1", headers=headers)
        assert response.status_code == 404
        assert "not a member" in response.json()["detail"]
