"""
Comprehensive security tests for Phase 1 and Phase 2 threat model remediation.

Covers:
- T13: File delete ownership check
- T-O5: email_verified enforcement
- T-O6: ALLOW_ALL_EMAILS behavior
- T3: JWT aud/iss validation
- T10+T12: Security headers middleware
- T11: Rate limiting configuration
- T-O1: Open redirect prevention
- T-O2: OAuth state validation
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import jwt
from datetime import timedelta, datetime, timezone
from dataclasses import dataclass

# --- Test Database Setup (must happen before app import) ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'

# Import after setting environment
from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from bondable.bond.auth import OAuth2ProviderFactory

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"
OTHER_USER_ID = "other-user-id-456"


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
def auth_headers():
    """Create valid auth headers for test user."""
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Test User",
        "provider": "cognito",
        "user_id": TEST_USER_ID,
        "iss": "bond-ai",
        "aud": ["bond-ai-api", "mcp-server"],
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def mock_file_details_own():
    """FileDetails object owned by the test user."""
    from bondable.bond.providers.files import FileDetails
    return FileDetails(
        file_id="s3://bond-bedrock-files-000000000000/files/bond_file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        file_path="test_document.pdf",
        file_hash="abc123hash",
        mime_type="application/pdf",
        owner_user_id=TEST_USER_ID,
    )


@pytest.fixture
def mock_file_details_other():
    """FileDetails object owned by another user."""
    from bondable.bond.providers.files import FileDetails
    return FileDetails(
        file_id="s3://bond-bedrock-files-000000000000/files/bond_file_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        file_path="other_document.pdf",
        file_hash="xyz789hash",
        mime_type="application/pdf",
        owner_user_id=OTHER_USER_ID,
    )


# ---------------------------------------------------------------------------
# T13 - File delete ownership check
# ---------------------------------------------------------------------------
class TestT13FileDeleteOwnership:
    """T13: Verify that users can only delete their own files."""

    def test_delete_file_returns_403_for_non_owner(
        self, test_client, auth_headers, mock_file_details_other
    ):
        """Attempting to delete another user's file must return 403."""
        with patch("bondable.rest.routers.files.get_bond_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.files.get_file_details.return_value = [mock_file_details_other]
            mock_provider.files.bucket_name = "bond-bedrock-files-000000000000"
            mock_get_provider.return_value = mock_provider

            # Override the dependency
            app.dependency_overrides[
                __import__(
                    "bondable.rest.dependencies.providers", fromlist=["get_bond_provider"]
                ).get_bond_provider
            ] = lambda: mock_provider

            try:
                # Use opaque file ID (bond_file_xxx) as clients would
                response = test_client.delete(
                    "/files/bond_file_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", headers=auth_headers
                )
                assert response.status_code == 403
                assert "permission" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()

    def test_delete_file_succeeds_for_owner(
        self, test_client, auth_headers, mock_file_details_own
    ):
        """File owner should be able to delete their own file."""
        with patch("bondable.rest.routers.files.get_bond_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.files.get_file_details.return_value = [mock_file_details_own]
            mock_provider.files.delete_file.return_value = True
            mock_provider.files.bucket_name = "bond-bedrock-files-000000000000"
            mock_get_provider.return_value = mock_provider

            from bondable.rest.dependencies.providers import get_bond_provider

            app.dependency_overrides[get_bond_provider] = lambda: mock_provider

            try:
                # Use opaque file ID as clients would
                response = test_client.delete(
                    "/files/bond_file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", headers=auth_headers
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "deleted"
                mock_provider.files.delete_file.assert_called_once_with(
                    file_id="s3://bond-bedrock-files-000000000000/files/bond_file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                )
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T-O5 - email_verified enforcement
# ---------------------------------------------------------------------------
class TestTO5EmailVerified:
    """T-O5: Providers must reject users with unverified email addresses."""

    @pytest.fixture
    def mock_okta_config(self):
        return {
            "domain": "https://trial-123.okta.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "redirect_uri": "http://localhost:8080/auth/okta/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": ["test@example.com"],
        }

    @pytest.fixture
    def mock_google_config(self):
        return {
            "auth_creds": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            "redirect_uri": "http://localhost:8080/auth/google/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": ["test@example.com"],
        }

    def test_okta_rejects_unverified_email(self, mock_okta_config):
        """Okta provider must reject users whose email is not verified."""
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)

        # Mock the internal HTTP calls to return unverified email
        with patch.object(provider, "_exchange_code_for_tokens") as mock_tokens, \
             patch.object(provider, "_get_user_info_from_token") as mock_userinfo:
            mock_tokens.return_value = {"access_token": "fake_token"}
            mock_userinfo.return_value = {
                "email": "test@example.com",
                "preferred_username": "Test User",
                "sub": "okta-sub-123",
                "email_verified": False,
            }

            with pytest.raises(ValueError, match="has not been verified"):
                provider.get_user_info_from_code("test_auth_code")

    @patch("bondable.bond.auth.google_oauth2.Flow")
    @patch("bondable.bond.auth.google_oauth2.id_token")
    def test_google_rejects_unverified_email(
        self, mock_id_token, mock_flow, mock_google_config
    ):
        """Google provider must reject users whose email is not verified."""
        mock_creds = MagicMock()
        mock_creds.id_token = "mock_id_token"
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "google-sub-123",
            "email_verified": False,
        }

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)

        with pytest.raises(ValueError, match="has not been verified"):
            provider.get_user_info_from_code("test_auth_code")

    @patch("bondable.bond.auth.google_oauth2.Flow")
    @patch("bondable.bond.auth.google_oauth2.id_token")
    def test_google_accepts_verified_email(
        self, mock_id_token, mock_flow, mock_google_config
    ):
        """Google provider must accept users with verified emails."""
        mock_creds = MagicMock()
        mock_creds.id_token = "mock_id_token"
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "google-sub-123",
            "email_verified": True,
        }

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        user_info = provider.get_user_info_from_code("test_auth_code")

        assert user_info["email"] == "test@example.com"

    def test_okta_accepts_verified_email(self, mock_okta_config):
        """Okta provider must accept users with verified emails."""
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)

        with patch.object(provider, "_exchange_code_for_tokens") as mock_tokens, \
             patch.object(provider, "_get_user_info_from_token") as mock_userinfo:
            mock_tokens.return_value = {"access_token": "fake_token"}
            mock_userinfo.return_value = {
                "email": "test@example.com",
                "preferred_username": "Test User",
                "sub": "okta-sub-123",
                "email_verified": True,
            }

            user_info = provider.get_user_info_from_code("test_auth_code")
            assert user_info["email"] == "test@example.com"


# ---------------------------------------------------------------------------
# T-O6 - ALLOW_ALL_EMAILS behavior
# ---------------------------------------------------------------------------
class TestTO6AllowAllEmails:
    """T-O6: Empty valid_emails must block login unless ALLOW_ALL_EMAILS=true."""

    @pytest.fixture
    def okta_config_no_allowlist(self):
        return {
            "domain": "https://trial-123.okta.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "redirect_uri": "http://localhost:8080/auth/okta/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": [],
        }

    @pytest.fixture
    def google_config_no_allowlist(self):
        return {
            "auth_creds": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            "redirect_uri": "http://localhost:8080/auth/google/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": [],
        }

    def test_empty_valid_emails_blocks_login_by_default(self, okta_config_no_allowlist):
        """When valid_emails is empty and ALLOW_ALL_EMAILS is not set, login must fail."""
        provider = OAuth2ProviderFactory.create_provider("okta", okta_config_no_allowlist)

        # Ensure ALLOW_ALL_EMAILS is not set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOW_ALL_EMAILS", None)
            user_info = {"email": "anyone@example.com", "name": "Anyone"}
            assert provider.validate_user(user_info) is False

    @patch.dict(os.environ, {"ALLOW_ALL_EMAILS": "true"})
    def test_allow_all_emails_true_permits_login(self, okta_config_no_allowlist):
        """When ALLOW_ALL_EMAILS=true and valid_emails is empty, any email is accepted."""
        provider = OAuth2ProviderFactory.create_provider("okta", okta_config_no_allowlist)
        user_info = {"email": "anyone@example.com", "name": "Anyone"}
        assert provider.validate_user(user_info) is True

    def test_google_empty_valid_emails_blocks_login(self, google_config_no_allowlist):
        """Google provider: empty valid_emails blocks login by default."""
        provider = OAuth2ProviderFactory.create_provider("google", google_config_no_allowlist)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOW_ALL_EMAILS", None)
            user_info = {"email": "anyone@example.com", "name": "Anyone"}
            assert provider.validate_user(user_info) is False

    @patch.dict(os.environ, {"ALLOW_ALL_EMAILS": "true"})
    def test_google_allow_all_emails_true_permits_login(self, google_config_no_allowlist):
        """Google provider: ALLOW_ALL_EMAILS=true allows any email."""
        provider = OAuth2ProviderFactory.create_provider("google", google_config_no_allowlist)
        user_info = {"email": "anyone@example.com", "name": "Anyone"}
        assert provider.validate_user(user_info) is True


# ---------------------------------------------------------------------------
# T3 - JWT aud/iss validation
# ---------------------------------------------------------------------------
class TestT3JwtAudIssValidation:
    """T3: get_current_user must reject tokens missing or with wrong aud/iss."""

    def _make_token(self, **overrides):
        """Create a raw JWT with full control over claims."""
        payload = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "cognito",
            "user_id": TEST_USER_ID,
            "iss": "bond-ai",
            "aud": ["bond-ai-api", "mcp-server"],
            "jti": "test-jti-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        payload.update(overrides)
        return jwt.encode(payload, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)

    def test_token_without_aud_rejected(self, test_client):
        """Token with no aud claim must be rejected."""
        # Build payload manually without aud
        payload = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "cognito",
            "user_id": TEST_USER_ID,
            "iss": "bond-ai",
            "jti": "test-jti-no-aud",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        headers = {"Authorization": f"Bearer {token}"}

        response = test_client.get("/users/me", headers=headers)
        assert response.status_code == 401

    def test_token_with_wrong_aud_rejected(self, test_client):
        """Token with incorrect aud must be rejected."""
        token = self._make_token(aud=["wrong-audience"])
        headers = {"Authorization": f"Bearer {token}"}

        response = test_client.get("/users/me", headers=headers)
        assert response.status_code == 401

    def test_token_with_wrong_iss_rejected(self, test_client):
        """Token with incorrect iss must be rejected."""
        token = self._make_token(iss="wrong-issuer")
        headers = {"Authorization": f"Bearer {token}"}

        response = test_client.get("/users/me", headers=headers)
        assert response.status_code == 401

    def test_properly_formatted_token_accepted(self, test_client):
        """Token with correct aud and iss must be accepted."""
        token = self._make_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = test_client.get("/users/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == TEST_USER_EMAIL

    def test_create_access_token_adds_default_claims(self):
        """create_access_token must add iss, aud, and jti when not provided."""
        token = create_access_token(
            data={"sub": TEST_USER_EMAIL, "name": "Test", "provider": "cognito", "user_id": TEST_USER_ID},
            expires_delta=timedelta(minutes=15),
        )
        payload = jwt.decode(
            token,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            audience="bond-ai-api",
        )
        assert payload["iss"] == "bond-ai"
        assert "bond-ai-api" in payload["aud"]
        assert "mcp-server" in payload["aud"]
        assert "jti" in payload


# ---------------------------------------------------------------------------
# T10+T12 - Security headers
# ---------------------------------------------------------------------------
class TestT10T12SecurityHeaders:
    """T10+T12: All API responses must include security headers."""

    def test_health_endpoint_has_security_headers(self, test_client):
        """GET /health must include Referrer-Policy, Permissions-Policy, HSTS, etc."""
        response = test_client.get("/health")

        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
        assert "max-age=" in response.headers.get("Strict-Transport-Security", "")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_security_headers_present_on_error_response(self, test_client):
        """Security headers must be present even on 4xx responses."""
        response = test_client.get("/users/me")  # No auth header -> 401

        # Middleware should still attach headers to error responses
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# T11 - Rate limiting sanity check
# ---------------------------------------------------------------------------
class TestT11RateLimiting:
    """T11: Rate limiter must be configured on the application."""

    def test_rate_limiter_is_configured(self):
        """app.state.limiter must be set (slowapi Limiter instance)."""
        assert hasattr(app.state, "limiter"), "Rate limiter not found on app.state"
        from slowapi import Limiter
        assert isinstance(app.state.limiter, Limiter)


# ---------------------------------------------------------------------------
# T-O1 - Open redirect prevention
# ---------------------------------------------------------------------------
class TestTO1OpenRedirect:
    """T-O1: Login and callback must reject unsafe redirect_uri values."""

    def test_login_rejects_unsafe_redirect_uri(self, test_client):
        """Login with an external redirect_uri must return 400."""
        with patch("bondable.bond.auth.OAuth2ProviderFactory.create_provider") as mock_create, \
             patch("bondable.rest.routers.auth._save_auth_oauth_state", return_value=True):
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://example.auth.amazoncognito.com/oauth2/authorize"
            mock_create.return_value = mock_provider

            response = test_client.get(
                "/login/cognito?platform=mobile&redirect_uri=https://evil.com/steal",
                follow_redirects=False,
            )
            assert response.status_code == 400
            assert "redirect_uri" in response.json()["detail"].lower() or \
                   "domain" in response.json()["detail"].lower()

    def test_callback_rejects_unsafe_redirect_uri_in_state(self, test_client):
        """Callback with unsafe redirect_uri stored in state must return 400."""
        with patch("bondable.bond.auth.OAuth2ProviderFactory.create_provider") as mock_create, \
             patch("bondable.rest.routers.auth._get_and_delete_auth_oauth_state") as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User",
            }
            mock_create.return_value = mock_provider

            # Simulate state with an unsafe redirect_uri and mobile platform
            mock_state.return_value = {
                                "code_verifier": "test_verifier",
                "redirect_uri": "https://evil.com/steal",
                "provider_name": "cognito",
                "platform": "mobile",
            }

            # Mock the users service for get_or_create_user
            from bondable.rest.dependencies.providers import get_bond_provider

            mock_bond_provider = MagicMock()
            mock_bond_provider.users.get_or_create_user.return_value = (TEST_USER_ID, False)
            app.dependency_overrides[get_bond_provider] = lambda: mock_bond_provider

            try:
                response = test_client.get(
                    "/auth/cognito/callback?code=test_code&state=valid_state",
                    follow_redirects=False,
                )
                assert response.status_code == 400
                assert "redirect_uri" in response.json()["detail"].lower() or \
                       "domain" in response.json()["detail"].lower()
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T-O2 - OAuth state validation
# ---------------------------------------------------------------------------
class TestTO2OAuthStateValidation:
    """T-O2: Callback must validate the OAuth state parameter to prevent CSRF."""

    def test_callback_without_state_returns_400(self, test_client):
        """Missing state parameter in callback must return 400."""
        response = test_client.get("/auth/cognito/callback?code=test_code")
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

    def test_callback_with_invalid_state_returns_400(self, test_client):
        """State not found in database (expired or forged) must return 400."""
        with patch("bondable.rest.routers.auth._get_and_delete_auth_oauth_state") as mock_state:
            mock_state.return_value = None  # State not found / invalid

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=forged_state"
            )
            assert response.status_code == 400
            assert "state" in response.json()["detail"].lower()

    def test_callback_with_valid_state_succeeds(self, test_client):
        """Valid state should allow the callback to proceed."""
        with patch("bondable.bond.auth.OAuth2ProviderFactory.create_provider") as mock_create, \
             patch("bondable.rest.routers.auth._get_and_delete_auth_oauth_state") as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User",
            }
            mock_create.return_value = mock_provider

            mock_state.return_value = {
                                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
            }

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=valid_state",
                follow_redirects=False,
            )
            # Should redirect with auth code (307) — Phase 3 changed from ?token= to ?code=
            assert response.status_code == 307
            assert "code=" in response.headers["location"]
