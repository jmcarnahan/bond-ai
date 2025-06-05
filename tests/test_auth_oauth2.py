import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import timedelta, datetime, timezone

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from bondable.bond.auth import OAuth2ProviderFactory, OAuth2Provider, OAuth2UserInfo

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"

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
        
        # Mock ID token verification
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "sub": "123456"
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
        
        # Mock ID token verification
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "test@example.com",
            "name": "Test User"
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
        
        # Mock ID token verification with unauthorized email
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "unauthorized@example.com",
            "name": "Unauthorized User"
        }
        
        provider = OAuth2ProviderFactory.create_provider("google", mock_google_config)
        
        with pytest.raises(ValueError, match="is not authorized"):
            provider.get_user_info_from_code("test_auth_code")
    
    def test_google_user_validation_no_restriction(self, mock_google_config):
        """Test Google user validation with no email restrictions."""
        # Remove valid_emails restriction
        config_no_restriction = mock_google_config.copy()
        config_no_restriction["valid_emails"] = []
        
        provider = OAuth2ProviderFactory.create_provider("google", config_no_restriction)
        
        # Test with any email
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
        assert data["default"] == "google"
        
        # Check that google provider is listed
        provider_names = [p["name"] for p in data["providers"]]
        assert "google" in provider_names
    
    def test_login_default_redirect(self, test_client):
        """Test default login redirects to Google."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://accounts.google.com/oauth/authorize"
            mock_create.return_value = mock_provider
            
            response = test_client.get("/login", follow_redirects=False)
            
            assert response.status_code == 307
            assert "google" in response.headers["location"].lower()
    
    def test_login_specific_provider(self, test_client):
        """Test login with specific provider."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://accounts.google.com/oauth/authorize"
            mock_create.return_value = mock_provider
            
            response = test_client.get("/login/google", follow_redirects=False)
            
            assert response.status_code == 307
            assert "google" in response.headers["location"].lower()
            mock_create.assert_called_once_with("google", mock_create.call_args[0][1])
    
    def test_login_invalid_provider(self, test_client):
        """Test login with invalid provider."""
        response = test_client.get("/login/invalid_provider")
        
        assert response.status_code == 400
        assert "Invalid OAuth2 provider" in response.json()["detail"]
    
    def test_auth_callback_success(self, test_client):
        """Test successful OAuth callback."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider
            
            response = test_client.get("/auth/google/callback?code=test_code", follow_redirects=False)
            
            assert response.status_code == 307
            assert "token=" in response.headers["location"]
            mock_provider.get_user_info_from_code.assert_called_once_with("test_code")
    
    def test_auth_callback_missing_code(self, test_client):
        """Test OAuth callback without code."""
        response = test_client.get("/auth/google/callback")
        
        assert response.status_code == 400
        assert "Authorization code missing" in response.json()["detail"]
    
    def test_auth_callback_invalid_code(self, test_client):
        """Test OAuth callback with invalid code."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.side_effect = ValueError("Invalid code")
            mock_create.return_value = mock_provider
            
            response = test_client.get("/auth/google/callback?code=invalid")
            
            assert response.status_code == 401
            assert "Invalid code" in response.json()["detail"]

class TestJWTWithProvider:
    """Test JWT token creation and validation with provider information."""
    
    def test_create_token_with_provider(self):
        """Test creating JWT token with provider information."""
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "google"
        }
        
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        
        # Decode and verify token
        payload = jwt.decode(access_token, jwt_config.JWT_SECRET_KEY, algorithms=[jwt_config.JWT_ALGORITHM])
        assert payload["sub"] == TEST_USER_EMAIL
        assert payload["name"] == "Test User"
        assert payload["provider"] == "google"
    
    def test_get_current_user_with_provider(self, test_client):
        """Test getting current user with provider information."""
        # Create token with provider
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "google"
        }
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        response = test_client.get("/users/me", headers=auth_headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == TEST_USER_EMAIL
        assert user_data["name"] == "Test User"
        assert user_data["provider"] == "google"
    
    def test_get_current_user_legacy_token(self, test_client):
        """Test getting current user with legacy token (no provider field)."""
        # Create token without provider (legacy format)
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": "Test User"
        }
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        response = test_client.get("/users/me", headers=auth_headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == TEST_USER_EMAIL
        assert user_data["name"] == "Test User"
        assert user_data["provider"] == "google"  # Should default to google

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
            mock_provider.get_auth_url.return_value = "https://accounts.google.com/oauth/authorize"
            mock_create.return_value = mock_provider
            
            response = test_client.get("/login", follow_redirects=False)
            assert response.status_code == 307
        
        # Test legacy /auth/google/callback endpoint
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "email": TEST_USER_EMAIL,
                "name": "Test User"
            }
            mock_create.return_value = mock_provider
            
            response = test_client.get("/auth/google/callback?code=test", follow_redirects=False)
            assert response.status_code == 307