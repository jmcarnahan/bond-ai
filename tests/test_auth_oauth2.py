import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import jwt
from datetime import timedelta, datetime, timezone

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'

# Import after setting environment
from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from bondable.bond.auth import OAuth2ProviderFactory, OAuth2Provider, OAuth2UserInfo

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"

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

class TestOAuth2Provider:
    """Test OAuth2Provider abstract base class."""

    def test_oauth2_provider_is_abstract(self):
        """Test that OAuth2Provider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OAuth2Provider({})

    def test_oauth2_user_info(self):
        """Test OAuth2UserInfo data class."""
        user_info = OAuth2UserInfo(
            email="test@example.com",
            name="Test User",
            provider="google",
            raw_data={"extra": "data"}
        )

        assert user_info.email == "test@example.com"
        assert user_info.name == "Test User"
        assert user_info.provider == "google"
        assert user_info.raw_data["extra"] == "data"

        # Test to_dict method
        data = user_info.to_dict()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["provider"] == "google"

class TestOAuth2ProviderFactory:
    """Test OAuth2ProviderFactory functionality."""

    def test_get_available_providers(self):
        """Test listing available OAuth2 providers."""
        providers = OAuth2ProviderFactory.get_available_providers()
        assert isinstance(providers, list)
        assert "google" in providers

    def test_get_provider_info(self):
        """Test getting provider information."""
        info = OAuth2ProviderFactory.get_provider_info("google")
        assert info["name"] == "google"
        assert info["callback_path"] == "/auth/google/callback"
        assert "class" in info
        assert "module" in info

    def test_get_provider_info_invalid_provider(self):
        """Test getting info for invalid provider."""
        with pytest.raises(ValueError, match="Unknown OAuth2 provider"):
            OAuth2ProviderFactory.get_provider_info("invalid")

    def test_create_provider_invalid_provider(self):
        """Test creating invalid provider."""
        with pytest.raises(ValueError, match="Unknown OAuth2 provider"):
            OAuth2ProviderFactory.create_provider("invalid", {})

class TestGoogleOAuth2Provider:
    """Test Google OAuth2 provider implementation."""

    @pytest.fixture
    def mock_google_config(self):
        """Mock Google OAuth2 configuration."""
        return {
            "auth_creds": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            },
            "redirect_uri": "http://localhost:8080/auth/google/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": ["test@example.com"]
        }

    def test_google_provider_creation(self, mock_google_config):
        """Test Google provider can be created with valid config."""
        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        assert provider.provider_name == "google"
        assert provider.callback_path == "/auth/google/callback"

    def test_google_provider_missing_config(self):
        """Test Google provider creation with missing config."""
        with pytest.raises(ValueError, match="Missing required config keys"):
            OAuth2ProviderFactory.create_provider("google", {})

    @patch('bondable.bond.auth.google_oauth2.Flow')
    def test_google_get_auth_url(self, mock_flow, mock_google_config):
        """Test Google auth URL generation."""
        mock_flow_instance = MagicMock()
        mock_flow_instance.authorization_url.return_value = ("https://accounts.google.com/auth", "state")
        mock_flow.from_client_config.return_value = mock_flow_instance

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        auth_url = provider.get_auth_url()

        assert auth_url == "https://accounts.google.com/auth"
        mock_flow.from_client_config.assert_called_once()
        mock_flow_instance.authorization_url.assert_called_once()

    @patch('bondable.bond.auth.google_oauth2.Flow')
    @patch('bondable.bond.auth.google_oauth2.id_token')
    def test_google_get_user_info_success(self, mock_id_token, mock_flow, mock_google_config):
        """Test successful Google user info retrieval."""
        # Mock flow and credentials
        mock_creds = MagicMock()
        mock_creds.id_token = "mock_id_token"
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        # Mock ID token verification (include email_verified for T-O5)
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "123456",
            "email_verified": True
        }

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        user_info = provider.get_user_info_from_code("test_auth_code")

        assert user_info["email"] == "test@example.com"
        assert user_info["name"] == "Test User"
        mock_flow_instance.fetch_token.assert_called_once_with(code="test_auth_code")

    @patch('bondable.bond.auth.google_oauth2.Flow')
    @patch('bondable.bond.auth.google_oauth2.id_token')
    def test_google_user_validation_success(self, mock_id_token, mock_flow, mock_google_config):
        """Test Google user validation with valid email."""
        # Mock flow and credentials
        mock_creds = MagicMock()
        mock_creds.id_token = "mock_id_token"
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        # Mock ID token verification (include email_verified for T-O5)
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": True
        }

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        user_info = provider.get_user_info_from_code("test_auth_code")

        assert user_info["email"] == "test@example.com"

    @patch('bondable.bond.auth.google_oauth2.Flow')
    @patch('bondable.bond.auth.google_oauth2.id_token')
    def test_google_user_validation_failure(self, mock_id_token, mock_flow, mock_google_config):
        """Test Google user validation with invalid email."""
        # Mock flow and credentials
        mock_creds = MagicMock()
        mock_creds.id_token = "mock_id_token"
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        # Mock ID token verification with unauthorized email (but verified)
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "unauthorized@example.com",
            "name": "Unauthorized User",
            "email_verified": True
        }

        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)

        with pytest.raises(ValueError, match="is not authorized"):
            provider.get_user_info_from_code("test_auth_code")

    @patch.dict(os.environ, {"ALLOW_ALL_EMAILS": "true"})
    def test_google_user_validation_no_restriction(self, mock_google_config):
        """Test Google user validation with no email restrictions (ALLOW_ALL_EMAILS=true)."""
        # Remove valid_emails restriction
        config_no_restriction = mock_google_config.copy()
        config_no_restriction["valid_emails"] = []

        provider = OAuth2ProviderFactory.create_provider("google", config_no_restriction)

        # Test with any email — allowed because ALLOW_ALL_EMAILS=true
        user_info = {"email": "anyone@example.com", "name": "Anyone"}
        assert provider.validate_user(user_info) is True

class TestAuthenticationRoutes:
    """Test authentication routes with new OAuth2 system."""

    def test_list_auth_providers(self, test_client):
        """Test listing available authentication providers."""
        response = test_client.get("/providers")

        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "default" in data
        assert data["default"] == "cognito"

        # Check that cognito provider is listed
        provider_names = [p["name"] for p in data["providers"]]
        assert "cognito" in provider_names

    def test_login_default_redirect(self, test_client):
        """Test default login redirects to Cognito."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://example.auth.us-west-2.amazoncognito.com/oauth2/authorize"
            mock_create.return_value = mock_provider

            response = test_client.get("/login", follow_redirects=False)

            assert response.status_code == 307
            assert "cognito" in response.headers["location"].lower()

    def test_login_specific_provider(self, test_client):
        """Test login with specific provider."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://example.auth.us-west-2.amazoncognito.com/oauth2/authorize"
            mock_create.return_value = mock_provider

            response = test_client.get("/login/cognito", follow_redirects=False)

            assert response.status_code == 307
            assert "cognito" in response.headers["location"].lower()
            mock_create.assert_called_once_with("cognito", mock_create.call_args[0][1])

    def test_login_invalid_provider(self, test_client):
        """Test login with invalid provider."""
        response = test_client.get("/login/invalid_provider")

        assert response.status_code == 400
        assert "Invalid OAuth2 provider" in response.json()["detail"]

    def test_auth_callback_success(self, test_client):
        """Test successful OAuth callback with valid state (T-O2)."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider

            # Mock valid state lookup
            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
                "origin_host": None,
            }

            response = test_client.get("/auth/cognito/callback?code=test_code&state=test_state", follow_redirects=False)

            assert response.status_code == 307
            # Phase 3: callback now redirects with ?code= (opaque auth code) instead of ?token=
            assert "code=" in response.headers["location"]
            assert "token=" not in response.headers["location"]
            mock_provider.get_user_info_from_code.assert_called_once_with(
                "test_code", code_verifier="test_verifier", redirect_uri=None
            )

    def test_auth_callback_missing_code(self, test_client):
        """Test OAuth callback without code."""
        response = test_client.get("/auth/cognito/callback")

        assert response.status_code == 400
        assert "Authorization code missing" in response.json()["detail"]

    def test_auth_callback_invalid_code(self, test_client):
        """Test OAuth callback with invalid code but valid state."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.side_effect = ValueError("Invalid code")
            mock_create.return_value = mock_provider

            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
            }

            response = test_client.get("/auth/cognito/callback?code=invalid&state=test_state")

            assert response.status_code == 401
            assert "Invalid code" in response.json()["detail"]

    def test_auth_callback_invalid_state(self, test_client):
        """Test OAuth callback with missing/invalid state (T-O2 CSRF protection)."""
        response = test_client.get("/auth/cognito/callback?code=test_code")
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

class TestJWTWithProvider:
    """Test JWT token creation and validation with provider information."""

    def test_create_token_with_provider(self):
        """Test creating JWT token with provider information and standard claims (T3)."""
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "cognito"
        }

        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))

        # Decode and verify token with audience validation (T3)
        payload = jwt.decode(
            access_token, jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            audience="bond-ai-api"
        )
        assert payload["sub"] == TEST_USER_EMAIL
        assert payload["name"] == "Test User"
        assert payload["provider"] == "cognito"
        # Verify standard claims are present (T3)
        assert payload["iss"] == "bond-ai"
        assert "bond-ai-api" in payload["aud"]
        assert "mcp-server" in payload["aud"]
        assert "jti" in payload  # UUID for token revocation (T2 prep)

    def test_get_current_user_with_provider(self, test_client):
        """Test getting current user with provider information."""
        # Create token with provider and user_id
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "cognito",
            "user_id": TEST_USER_ID
        }
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        response = test_client.get("/users/me", headers=auth_headers)

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == TEST_USER_EMAIL
        assert user_data["name"] == "Test User"
        assert user_data["provider"] == "cognito"

    def test_get_current_user_legacy_token(self, test_client):
        """Test getting current user with legacy token (no user_id field)."""
        # Create token without user_id (legacy format)
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "cognito"
        }
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        response = test_client.get("/users/me", headers=auth_headers)

        # Should fail because user_id is required now
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

class TestBackwardsCompatibility:
    """Test backwards compatibility with existing GoogleAuth."""

    def test_legacy_google_auth_import(self):
        """Test that legacy GoogleAuth import still works."""
        from bondable.bond.auth import GoogleAuth

        # Should be able to access GoogleAuth (even if it's a lazy proxy)
        assert GoogleAuth is not None

    def test_legacy_auth_endpoints(self, test_client):
        """Test that legacy auth endpoints still work."""
        # Test legacy /login endpoint
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://example.auth.us-west-2.amazoncognito.com/oauth2/authorize"
            mock_create.return_value = mock_provider

            response = test_client.get("/login", follow_redirects=False)
            assert response.status_code == 307

        # Test /auth/cognito/callback endpoint (requires valid state now — T-O2)
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider
            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
            }

            response = test_client.get("/auth/cognito/callback?code=test&state=test_state", follow_redirects=False)
            assert response.status_code == 307


# ===========================================================================
# Dynamic Origin Host (ZPA Clientless / Multi-Domain Support)
# ===========================================================================

class TestGetValidatedOriginHost:
    """Unit tests for _get_validated_origin_host()."""

    def _make_request(self, headers: dict) -> "Request":
        """Create a minimal mock Request with given headers."""
        from starlette.requests import Request
        from starlette.datastructures import Headers
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/login/okta",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
        return Request(scope)

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com,agentstudio.zpa.mcafee.com"})
    def test_returns_host_when_in_allowed_domains(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "agentstudio.zpa.mcafee.com"})
        assert _get_validated_origin_host(req) == "agentstudio.zpa.mcafee.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_returns_none_for_unknown_domain(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "evil.com"})
        assert _get_validated_origin_host(req) is None

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_returns_none_for_localhost(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "localhost"})
        assert _get_validated_origin_host(req) is None

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_returns_none_for_127_0_0_1(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "127.0.0.1"})
        assert _get_validated_origin_host(req) is None

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_returns_none_for_empty_headers(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({})
        assert _get_validated_origin_host(req) is None

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.zpa.mcafee.com"})
    def test_x_forwarded_host_takes_precedence(self):
        """X-Forwarded-Host should be used over Host header."""
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({
            "host": "internal-alb-123.amazonaws.com",
            "x-forwarded-host": "agentstudio.zpa.mcafee.com",
        })
        assert _get_validated_origin_host(req) == "agentstudio.zpa.mcafee.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.zpa.mcafee.com"})
    def test_comma_separated_x_forwarded_host_uses_first(self):
        """When X-Forwarded-Host has multiple values, use the first."""
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({
            "x-forwarded-host": "agentstudio.zpa.mcafee.com, proxy.internal",
        })
        assert _get_validated_origin_host(req) == "agentstudio.zpa.mcafee.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_strips_port_from_host(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "agentstudio.dev.mcafee.com:443"})
        assert _get_validated_origin_host(req) == "agentstudio.dev.mcafee.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_case_insensitive_matching_returns_lowercase(self):
        """Host header with mixed case should match and return lowercase."""
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "AgentStudio.Dev.McAfee.COM"})
        assert _get_validated_origin_host(req) == "agentstudio.dev.mcafee.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_localhost_with_port_returns_none(self):
        from bondable.rest.routers.auth import _get_validated_origin_host
        req = self._make_request({"host": "localhost:8080"})
        assert _get_validated_origin_host(req) is None


class TestDynamicRedirectLogin:
    """Integration tests for the login endpoint with dynamic redirect URIs."""

    @pytest.fixture(autouse=True)
    def _mock_bond_provider(self):
        """Override get_bond_provider to avoid S3/AWS calls in tests."""
        from bondable.rest.dependencies.providers import get_bond_provider
        mock_bp = MagicMock()
        app.dependency_overrides[get_bond_provider] = lambda: mock_bp
        yield mock_bp
        app.dependency_overrides.pop(get_bond_provider, None)

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.zpa.mcafee.com"})
    def test_login_with_zpa_host_uses_dynamic_redirect(self, test_client):
        """Login from ZPA domain should build auth URL with ZPA redirect URI."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._save_auth_oauth_state') as mock_save:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://mcafee.okta.com/oauth2/v1/authorize?redirect_uri=https://agentstudio.zpa.mcafee.com/auth/cognito/callback"
            mock_create.return_value = mock_provider
            mock_save.return_value = True

            response = test_client.get(
                "/login/cognito",
                headers={"host": "agentstudio.zpa.mcafee.com"},
                follow_redirects=False,
            )

            assert response.status_code == 307

            # Verify get_auth_url was called with the ZPA redirect URI
            call_kwargs = mock_provider.get_auth_url.call_args
            assert call_kwargs.kwargs["redirect_uri"] == "https://agentstudio.zpa.mcafee.com/auth/cognito/callback"

            # Verify origin_host was saved in OAuth state
            save_kwargs = mock_save.call_args
            assert save_kwargs.kwargs["origin_host"] == "agentstudio.zpa.mcafee.com"

    def test_login_without_matching_host_uses_default(self, test_client):
        """Login from unrecognized host should use default redirect URI (None)."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._save_auth_oauth_state') as mock_save:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://mcafee.okta.com/oauth2/v1/authorize"
            mock_create.return_value = mock_provider
            mock_save.return_value = True

            response = test_client.get(
                "/login/cognito",
                headers={"host": "testserver"},  # default test client host
                follow_redirects=False,
            )

            assert response.status_code == 307

            # No dynamic redirect — should pass None
            call_kwargs = mock_provider.get_auth_url.call_args
            assert call_kwargs.kwargs["redirect_uri"] is None

            # origin_host should be empty
            save_kwargs = mock_save.call_args
            assert save_kwargs.kwargs["origin_host"] == ""

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "agentstudio.dev.mcafee.com"})
    def test_login_with_x_forwarded_host(self, test_client):
        """Login with X-Forwarded-Host should use that over Host."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._save_auth_oauth_state') as mock_save:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://mcafee.okta.com/oauth2/v1/authorize"
            mock_create.return_value = mock_provider
            mock_save.return_value = True

            response = test_client.get(
                "/login/cognito",
                headers={
                    "host": "internal-alb-123.amazonaws.com",
                    "x-forwarded-host": "agentstudio.dev.mcafee.com",
                },
                follow_redirects=False,
            )

            assert response.status_code == 307

            call_kwargs = mock_provider.get_auth_url.call_args
            assert call_kwargs.kwargs["redirect_uri"] == "https://agentstudio.dev.mcafee.com/auth/cognito/callback"


class TestDynamicRedirectCallback:
    """Tests for the callback using stored origin_host for token exchange and frontend redirect."""

    @pytest.fixture(autouse=True)
    def _mock_bond_provider(self):
        """Override get_bond_provider to avoid S3/AWS calls in tests."""
        from bondable.rest.dependencies.providers import get_bond_provider
        mock_bp = MagicMock()
        mock_bp.users.get_or_create_user.return_value = (TEST_USER_ID, False)
        app.dependency_overrides[get_bond_provider] = lambda: mock_bp
        yield mock_bp
        app.dependency_overrides.pop(get_bond_provider, None)

    def test_callback_with_origin_host_passes_dynamic_redirect_uri(self, test_client):
        """When origin_host is stored, token exchange should use the dynamic redirect URI."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider

            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
                "origin_host": "agentstudio.zpa.mcafee.com",
            }

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            # Verify get_user_info_from_code was called with the ZPA redirect URI
            mock_provider.get_user_info_from_code.assert_called_once_with(
                "test_code",
                code_verifier="test_verifier",
                redirect_uri="https://agentstudio.zpa.mcafee.com/auth/cognito/callback",
            )

    def test_callback_with_origin_host_redirects_to_origin_domain(self, test_client):
        """When origin_host is stored, post-login redirect should go to that domain."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider

            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
                "origin_host": "agentstudio.zpa.mcafee.com",
            }

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307
            location = response.headers["location"]
            # Should redirect to the ZPA domain with hash routing
            assert location.startswith("https://agentstudio.zpa.mcafee.com/#/auth-callback?code=")

    def test_callback_without_origin_host_uses_default_redirect(self, test_client):
        """When origin_host is empty/None, should fall back to JWT_REDIRECT_URI."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider

            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
                "origin_host": "",
            }

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            # redirect_uri should be None (fallback to config default)
            mock_provider.get_user_info_from_code.assert_called_once_with(
                "test_code",
                code_verifier="test_verifier",
                redirect_uri=None,
            )

    def test_callback_with_origin_host_none_in_state(self, test_client):
        """When origin_host key is missing from state (old records), should work like no origin."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create, \
             patch('bondable.rest.routers.auth._get_and_delete_auth_oauth_state') as mock_state:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "sub": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider

            # Simulate old state record without origin_host key
            mock_state.return_value = {
                "code_verifier": "test_verifier",
                "redirect_uri": "",
                "provider_name": "cognito",
                "platform": "",
            }

            response = test_client.get(
                "/auth/cognito/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            mock_provider.get_user_info_from_code.assert_called_once_with(
                "test_code",
                code_verifier="test_verifier",
                redirect_uri=None,
            )
