import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app
from bondable.bond.auth import OAuth2ProviderFactory

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
def mock_okta_config():
    """Mock Okta OAuth2 configuration."""
    return {
        "domain": "https://trial-9457917.okta.com",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "redirect_uri": "http://localhost:8080/auth/okta/callback",
        "scopes": ["openid", "profile", "email"],
        "valid_emails": ["test@example.com"]
    }

class TestOktaOAuth2Provider:
    """Test Okta OAuth2 provider implementation."""
    
    def test_okta_provider_creation(self, mock_okta_config):
        """Test Okta provider can be created with valid config."""
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        assert provider.provider_name == "okta"
        assert provider.callback_path == "/auth/okta/callback"
    
    def test_okta_provider_missing_config(self):
        """Test Okta provider creation with missing config."""
        with pytest.raises(ValueError, match="Missing required config keys"):
            OAuth2ProviderFactory.create_provider("okta", {})
    
    def test_okta_get_auth_url(self, mock_okta_config):
        """Test Okta auth URL generation."""
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        auth_url = provider.get_auth_url()
        
        assert "trial-9457917.okta.com" in auth_url
        assert "oauth2/default/v1/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=openid+profile+email" in auth_url
    
    @patch('bondable.bond.auth.okta_oauth2.requests.post')
    @patch('bondable.bond.auth.okta_oauth2.requests.get')
    def test_okta_get_user_info_success(self, mock_get, mock_post, mock_okta_config):
        """Test successful Okta user info retrieval."""
        # Mock token exchange response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "mock_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        # Mock user info response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": "test_user_id",
            "email": "test@example.com",
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "preferred_username": "testuser"
        }
        
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        user_info = provider.get_user_info_from_code("test_auth_code")
        
        assert user_info["email"] == "test@example.com"
        assert user_info["name"] == "Test User"
        assert user_info["sub"] == "test_user_id"
        
        # Verify the correct API calls were made
        mock_post.assert_called_once()
        mock_get.assert_called_once()
    
    @patch('bondable.bond.auth.okta_oauth2.requests.post')
    def test_okta_token_exchange_failure(self, mock_post, mock_okta_config):
        """Test Okta token exchange failure."""
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Invalid authorization code"
        
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        
        with pytest.raises(Exception, match="Token exchange failed"):
            provider.get_user_info_from_code("invalid_code")
    
    @patch('bondable.bond.auth.okta_oauth2.requests.post')
    @patch('bondable.bond.auth.okta_oauth2.requests.get')
    def test_okta_user_info_failure(self, mock_get, mock_post, mock_okta_config):
        """Test Okta user info fetch failure."""
        # Mock successful token exchange
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "mock_access_token"
        }
        
        # Mock failed user info request
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = "Invalid access token"
        
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        
        with pytest.raises(Exception, match="User info fetch failed"):
            provider.get_user_info_from_code("test_code")
    
    @patch('bondable.bond.auth.okta_oauth2.requests.post')
    @patch('bondable.bond.auth.okta_oauth2.requests.get')
    def test_okta_user_validation_failure(self, mock_get, mock_post, mock_okta_config):
        """Test Okta user validation with unauthorized email."""
        # Mock successful token and user info
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "email": "unauthorized@example.com",
            "name": "Unauthorized User"
        }
        
        provider = OAuth2ProviderFactory.create_provider("okta", mock_okta_config)
        
        with pytest.raises(ValueError, match="is not authorized"):
            provider.get_user_info_from_code("test_code")
    
    def test_okta_user_validation_no_restriction(self, mock_okta_config):
        """Test Okta user validation with no email restrictions."""
        # Remove valid_emails restriction
        config_no_restriction = mock_okta_config.copy()
        config_no_restriction["valid_emails"] = []
        
        provider = OAuth2ProviderFactory.create_provider("okta", config_no_restriction)
        
        # Test with any email
        user_info = {"email": "anyone@example.com", "name": "Anyone"}
        assert provider.validate_user(user_info) is True

class TestOktaAuthenticationRoutes:
    """Test Okta authentication routes."""
    
    def test_providers_endpoint_includes_okta(self, test_client):
        """Test that providers endpoint includes Okta."""
        response = test_client.get("/providers")
        
        assert response.status_code == 200
        data = response.json()
        
        provider_names = [p["name"] for p in data["providers"]]
        assert "okta" in provider_names
        
        # Find Okta provider details
        okta_provider = next(p for p in data["providers"] if p["name"] == "okta")
        assert okta_provider["login_url"] == "/login/okta"
        assert okta_provider["callback_url"] == "/auth/okta/callback"
    
    def test_okta_login_redirect(self, test_client):
        """Test Okta login redirect."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_auth_url.return_value = "https://trial-9457917.okta.com/oauth2/default/v1/authorize?..."
            mock_create.return_value = mock_provider
            
            response = test_client.get("/login/okta", follow_redirects=False)
            
            assert response.status_code == 307
            assert "trial-9457917.okta.com" in response.headers["location"]
    
    def test_okta_callback_success(self, test_client):
        """Test successful Okta OAuth callback."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.return_value = {
                "email": "test@example.com",
                "name": "Test User"
            }
            mock_create.return_value = mock_provider
            
            response = test_client.get("/auth/okta/callback?code=test_code", follow_redirects=False)
            
            assert response.status_code == 307
            assert "token=" in response.headers["location"]
    
    def test_okta_callback_invalid_code(self, test_client):
        """Test Okta callback with invalid code."""
        with patch('bondable.bond.auth.OAuth2ProviderFactory.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_provider.get_user_info_from_code.side_effect = Exception("Invalid authorization code")
            mock_create.return_value = mock_provider
            
            response = test_client.get("/auth/okta/callback?code=invalid")
            
            assert response.status_code == 500
            assert "Authentication failed" in response.json()["detail"]

class TestOktaIntegration:
    """Test Okta provider integration with existing system."""
    
    def test_okta_provider_available(self):
        """Test that Okta provider is available in factory."""
        providers = OAuth2ProviderFactory.get_available_providers()
        assert "okta" in providers
    
    def test_okta_provider_info(self):
        """Test Okta provider info."""
        info = OAuth2ProviderFactory.get_provider_info("okta")
        assert info["name"] == "okta"
        assert info["callback_path"] == "/auth/okta/callback"
        assert "OktaOAuth2Provider" in info["class"]
    
    def test_multiple_providers_available(self):
        """Test that both Google and Okta providers are available."""
        providers = OAuth2ProviderFactory.get_available_providers()
        assert "google" in providers
        assert "okta" in providers
        assert len(providers) >= 2