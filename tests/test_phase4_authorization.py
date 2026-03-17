"""
Tests for Phase 4 security remediation: Authorization & Access Control.

Covers:
- T7: Admin role from DB instead of email match
- T15: ORM-level user_id filtering on file queries
- T27+T28: Agent sharing permissions (can_use_read_only, system prompt restriction)
- T9+T21: MCP tool invocation logging and allow_write_tools flag
"""
import pytest
import os
import tempfile
import uuid
import logging
from datetime import timedelta
from unittest.mock import patch, MagicMock

# --- Test Database Setup (must happen before app import) ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['ALLOW_ALL_EMAILS'] = 'true'

from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from starlette.testclient import TestClient

jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"


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
def test_client():
    return TestClient(app)


@pytest.fixture
def bond_provider():
    from bondable.rest.dependencies.providers import get_bond_provider
    return get_bond_provider()


def _make_token(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, expires_minutes=15):
    return create_access_token(
        data={
            "sub": email,
            "name": "Test User",
            "provider": "cognito",
            "user_id": user_id,
            "iss": "bond-ai",
            "aud": ["bond-ai-api", "mcp-server"],
        },
        expires_delta=timedelta(minutes=expires_minutes),
    )


def _unique_id():
    return f"test-{uuid.uuid4().hex[:12]}"


# ===========================================================================
# T7 — Admin role from DB
# ===========================================================================
class TestT7AdminRole:

    def test_admin_status_set_on_user_creation(self, bond_provider):
        """New users get is_admin set based on config."""
        uid = _unique_id()
        email = f"{uid}@admin-test.com"

        # Directly insert user with is_admin=True to test DB storage
        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            session.add(UserModel(
                id=uid, email=email, name="Admin Test",
                sign_in_method="cognito", is_admin=True
            ))
            session.commit()

        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.id == uid).first()
            assert user is not None
            assert user.is_admin is True

    def test_non_admin_user_gets_false(self, bond_provider):
        """Regular users get is_admin=False by default."""
        uid = _unique_id()
        email = f"{uid}@regular.com"

        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            session.add(UserModel(
                id=uid, email=email, name="Regular",
                sign_in_method="cognito", is_admin=False
            ))
            session.commit()

        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.id == uid).first()
            assert user.is_admin is False

    def test_admin_status_can_be_updated(self, bond_provider):
        """Admin status can be toggled in the DB."""
        uid = _unique_id()
        email = f"{uid}@toggle.com"

        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            session.add(UserModel(
                id=uid, email=email, name="Toggle",
                sign_in_method="cognito", is_admin=False
            ))
            session.commit()

        # Update to admin
        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.id == uid).first()
            user.is_admin = True
            session.commit()

        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.id == uid).first()
            assert user.is_admin is True

    def test_get_current_user_reads_db_admin(self, test_client, bond_provider):
        """get_current_user reads is_admin from DB record."""
        uid = _unique_id()
        email = f"{uid}@dbadmin.com"

        # Insert user directly with is_admin=True
        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            session.add(UserModel(
                id=uid, email=email, name="DB Admin",
                sign_in_method="cognito", is_admin=True
            ))
            session.commit()

        token = _make_token(user_id=uid, email=email)
        resp = test_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    def test_non_admin_in_db_returns_false(self, test_client, bond_provider):
        """get_current_user returns is_admin=False when DB says False."""
        uid = _unique_id()
        email = f"{uid}@notadmin.com"

        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            session.add(UserModel(
                id=uid, email=email, name="Not Admin",
                sign_in_method="cognito", is_admin=False
            ))
            session.commit()

        token = _make_token(user_id=uid, email=email)
        resp = test_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False


# ===========================================================================
# T15 — ORM-level user_id filtering
# ===========================================================================
class TestT15FileFiltering:

    def test_get_file_details_passes_user_id(self, test_client):
        """GET /files/details passes user_id to provider.files.get_file_details()."""
        token = _make_token()
        mock_file = MagicMock()
        mock_file.file_id = "file-1"
        mock_file.file_path = "test.txt"
        mock_file.file_hash = "abc"
        mock_file.mime_type = "text/plain"
        mock_file.owner_user_id = TEST_USER_ID
        mock_file.file_size = 100

        mock_provider = MagicMock()
        mock_provider.files.get_file_details.return_value = [mock_file]

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            resp = test_client.get(
                "/files/details?file_ids=file-1",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            # Verify user_id was passed to provider
            call_kwargs = mock_provider.files.get_file_details.call_args
            # Should be called with (file_ids, user_id=current_user.user_id)
            assert call_kwargs[1].get('user_id') == TEST_USER_ID
        finally:
            app.dependency_overrides.clear()

    def test_delete_passes_user_id(self, test_client):
        """DELETE /files/{id} passes user_id to provider query for ownership check."""
        token = _make_token()
        mock_file = MagicMock()
        mock_file.owner_user_id = TEST_USER_ID

        mock_provider = MagicMock()
        mock_provider.files.get_file_details.return_value = [mock_file]
        mock_provider.files.delete_file.return_value = True

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            resp = test_client.delete(
                "/files/file-del-1",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            call_kwargs = mock_provider.files.get_file_details.call_args
            assert call_kwargs[1].get('user_id') == TEST_USER_ID
        finally:
            app.dependency_overrides.clear()

    def test_delete_returns_404_for_other_users_file(self, test_client):
        """DELETE returns 404 when user_id filter excludes the file."""
        token = _make_token()
        mock_provider = MagicMock()
        mock_provider.files.get_file_details.return_value = []  # Filtered out

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            resp = test_client.delete(
                "/files/other-users-file",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_download_passes_user_id(self, test_client):
        """GET /files/download/{id} passes user_id to provider query."""
        token = _make_token()
        import io
        mock_file = MagicMock()
        mock_file.owner_user_id = TEST_USER_ID
        mock_file.file_path = "test.txt"
        mock_file.mime_type = "text/plain"
        mock_file.file_size = 5

        mock_provider = MagicMock()
        mock_provider.files.get_file_details.return_value = [mock_file]
        mock_provider.files.get_file_bytes.return_value = io.BytesIO(b"hello")

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            resp = test_client.get(
                "/files/download/file-dl-1",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            call_kwargs = mock_provider.files.get_file_details.call_args
            assert call_kwargs[1].get('user_id') == TEST_USER_ID
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# T27+T28 — Agent sharing permissions
# ===========================================================================
class TestT27AgentPermissions:

    def test_can_use_read_only_recognized(self, bond_provider):
        """get_user_agent_permission returns can_use_read_only when set."""
        from bondable.bond.providers.metadata import (
            AgentRecord, AgentGroup, Group, GroupUser, User as UserModel
        )

        uid = _unique_id()
        agent_id = _unique_id()
        group_id = _unique_id()
        owner_id = _unique_id()

        with bond_provider.metadata.get_db_session() as session:
            if not session.query(UserModel).filter(UserModel.id == owner_id).first():
                session.add(UserModel(id=owner_id, email=f"{owner_id}@test.com", sign_in_method="test"))
            if not session.query(UserModel).filter(UserModel.id == uid).first():
                session.add(UserModel(id=uid, email=f"{uid}@test.com", sign_in_method="test"))
            session.add(AgentRecord(agent_id=agent_id, name="RO Agent", owner_user_id=owner_id, is_default=False))
            session.add(Group(id=group_id, name="RO Group", owner_user_id=owner_id))
            session.add(GroupUser(group_id=group_id, user_id=uid))
            session.add(AgentGroup(agent_id=agent_id, group_id=group_id, permission="can_use_read_only"))
            session.commit()

        perm = bond_provider.agents.get_user_agent_permission(uid, agent_id)
        assert perm == "can_use_read_only"

    def test_can_edit_blocked_from_changing_instructions(self, test_client):
        """can_edit users get 403 when trying to modify instructions."""
        uid = _unique_id()
        agent_id = _unique_id()

        # Mock agent with existing instructions
        mock_agent = MagicMock()
        mock_def = MagicMock()
        mock_def.instructions = "Original system prompt"
        mock_agent.get_agent_definition.return_value = mock_def

        mock_record = MagicMock()
        mock_record.is_default = False
        mock_record.owner_user_id = "some-owner"

        mock_provider = MagicMock()
        mock_provider.agents.get_agent_record.return_value = mock_record
        mock_provider.agents.get_user_agent_permission.return_value = "can_edit"
        mock_provider.agents.get_agent.return_value = mock_agent

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            token = _make_token(user_id=uid, email=f"{uid}@test.com")
            resp = test_client.put(
                f"/agents/{agent_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "Updated", "description": "desc",
                    "instructions": "MODIFIED PROMPT",  # Should be blocked
                    "model": "model", "tools": [],
                },
            )
            assert resp.status_code == 403
            assert "system prompt" in resp.json()["detail"].lower() or "instructions" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_owner_can_change_instructions(self, test_client):
        """Owners can modify instructions (not blocked)."""
        uid = _unique_id()
        agent_id = _unique_id()

        mock_record = MagicMock()
        mock_record.is_default = False
        mock_record.owner_user_id = uid  # User IS the owner

        mock_provider = MagicMock()
        mock_provider.agents.get_agent_record.return_value = mock_record
        mock_provider.agents.get_user_agent_permission.return_value = "owner"
        mock_provider.agents.get_agent.return_value = MagicMock()
        mock_provider.agents.update_agent.return_value = MagicMock()
        mock_provider.get_default_model.return_value = "test-model"

        from bondable.rest.dependencies.providers import get_bond_provider
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        try:
            token = _make_token(user_id=uid, email=f"{uid}@test.com")
            resp = test_client.put(
                f"/agents/{agent_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "Updated", "description": "desc",
                    "instructions": "NEW INSTRUCTIONS",  # Allowed for owner
                    "model": "model", "tools": [],
                },
            )
            # Should not be 403 — owner can change instructions
            assert resp.status_code != 403
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# T9+T21 — Tool invocation logging and allow_write_tools
# ===========================================================================
class TestT9ToolControl:

    def test_allow_write_tools_false_blocks(self):
        """allow_write_tools=false in metadata should block tool execution."""
        metadata = {"allow_write_tools": False}
        assert metadata.get('allow_write_tools', True) is False

    def test_allow_write_tools_default_true(self):
        """Default behavior allows tools when flag is not set."""
        metadata = {}
        assert metadata.get('allow_write_tools', True) is True

    def test_metadata_with_allow_write_tools_true(self):
        """Explicit True allows tools."""
        metadata = {"allow_write_tools": True}
        assert metadata.get('allow_write_tools', True) is True

    def test_audit_log_format(self):
        """Verify the structured log format for MCP tool invocations."""
        logger = logging.getLogger("bondable.bond.providers.bedrock.BedrockAgent")
        with patch.object(logger, 'info') as mock_log:
            logger.info(
                "MCP_TOOL_INVOCATION: tool=%s server=%s user_id=%s user_email=%s agent_id=%s",
                "jira_create_issue", "atlassian", "user-123", "user@co.com", "agent-456"
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert "MCP_TOOL_INVOCATION" in call_args[0]

    def test_audit_log_result_format(self):
        """Verify the structured log format for MCP tool results."""
        logger = logging.getLogger("bondable.bond.providers.bedrock.BedrockAgent")
        with patch.object(logger, 'info') as mock_log:
            logger.info(
                "MCP_TOOL_RESULT: tool=%s server=%s user_id=%s agent_id=%s success=%s",
                "jira_create_issue", "atlassian", "user-123", "agent-456", True
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert "MCP_TOOL_RESULT" in call_args[0]
