"""Tests for POST /auth/provision endpoint."""
import pytest
import os
import tempfile
import uuid
from datetime import timedelta

# --- Test Database Setup (must happen before app import) ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['ALLOW_ALL_EMAILS'] = 'true'

from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from starlette.testclient import TestClient

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


def _make_token(user_id, email, expires_minutes=15):
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


def _create_db_user(bond_provider, user_id, email, is_admin=False):
    """Insert a user directly into the DB."""
    from bondable.bond.providers.metadata import User as UserModel
    with bond_provider.metadata.get_db_session() as session:
        existing = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not existing:
            session.add(UserModel(
                id=user_id, email=email, name="Test User",
                sign_in_method="cognito", is_admin=is_admin,
            ))
            session.commit()


class TestProvisionEndpoint:
    """Tests for POST /auth/provision."""

    def test_provision_new_user(self, test_client, bond_provider):
        """Admin can provision a new user."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        target_email = f"{_unique_id()}@newuser.com"
        resp = test_client.post(
            "/auth/provision",
            json={"email": target_email, "name": "New User"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == target_email
        assert data["is_new"] is True
        assert len(data["user_id"]) > 0

    def test_provision_existing_user(self, test_client, bond_provider):
        """Provisioning the same email twice returns is_new=False with same user_id."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        target_email = f"{_unique_id()}@existing.com"
        resp1 = test_client.post(
            "/auth/provision",
            json={"email": target_email, "name": "User One"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["is_new"] is True

        resp2 = test_client.post(
            "/auth/provision",
            json={"email": target_email, "name": "User One"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["is_new"] is False
        assert data2["user_id"] == resp1.json()["user_id"]

    def test_provision_non_admin_forbidden(self, test_client, bond_provider):
        """Non-admin user gets 403."""
        user_id = _unique_id()
        user_email = f"{user_id}@regular.com"
        _create_db_user(bond_provider, user_id, user_email, is_admin=False)
        token = _make_token(user_id, user_email)

        resp = test_client.post(
            "/auth/provision",
            json={"email": "someone@example.com", "name": "Someone"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_provision_unauthenticated(self, test_client):
        """No auth header returns 401."""
        resp = test_client.post(
            "/auth/provision",
            json={"email": "someone@example.com", "name": "Someone"},
        )
        assert resp.status_code == 401

    def test_provision_missing_email(self, test_client, bond_provider):
        """Missing email field returns 422."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        resp = test_client.post(
            "/auth/provision",
            json={"name": "No Email"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_provision_missing_name(self, test_client, bond_provider):
        """Missing name field returns 422."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        resp = test_client.post(
            "/auth/provision",
            json={"email": "noname@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_provision_default_provider(self, test_client, bond_provider):
        """Omitting provider defaults to 'external'."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        target_email = f"{_unique_id()}@default.com"
        resp = test_client.post(
            "/auth/provision",
            json={"email": target_email, "name": "Default Provider"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        # Verify the user was created with sign_in_method="external"
        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.email == target_email).first()
            assert user is not None
            assert user.sign_in_method == "external"

    def test_provision_custom_provider(self, test_client, bond_provider):
        """Custom provider value is stored correctly."""
        admin_id = _unique_id()
        admin_email = f"{admin_id}@admin.com"
        _create_db_user(bond_provider, admin_id, admin_email, is_admin=True)
        token = _make_token(admin_id, admin_email)

        target_email = f"{_unique_id()}@saml.com"
        resp = test_client.post(
            "/auth/provision",
            json={"email": target_email, "name": "SAML User", "provider": "saml"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        from bondable.bond.providers.metadata import User as UserModel
        with bond_provider.metadata.get_db_session() as session:
            user = session.query(UserModel).filter(UserModel.email == target_email).first()
            assert user is not None
            assert user.sign_in_method == "saml"
