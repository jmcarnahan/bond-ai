import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import timedelta

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL

# Import after setting environment
from bondable.rest.main import app, create_access_token, get_bond_provider
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import AgentProvider

# Test configuration
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"

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
    """FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def mock_provider():
    """Mock provider with all sub-providers."""
    provider = MagicMock(spec=Provider)
    provider.agents = MagicMock(spec=AgentProvider)
    
    # Mock the get_available_models method
    provider.agents.get_available_models.return_value = [
        {
            'name': 'gpt-4o',
            'description': 'Most capable GPT-4 Omni model for complex tasks',
            'is_default': True
        }
    ]
    
    return provider

@pytest.fixture
def authenticated_client(test_client, mock_provider):
    """Test client with authentication and mocked provider."""
    # Override provider dependency
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    
    # Create valid JWT token with required fields
    token_data = {
        "sub": TEST_USER_EMAIL, 
        "name": "Test User",
        "provider": "google",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    
    yield test_client, auth_headers, mock_provider
    
    # Clean up
    if get_bond_provider in app.dependency_overrides:
        del app.dependency_overrides[get_bond_provider]

# --- Model Endpoint Tests ---

class TestModelsEndpoint:
    
    def test_get_available_models_success(self, authenticated_client):
        """Test getting available models successfully."""
        client, auth_headers, mock_provider = authenticated_client
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 1
        assert models[0]["name"] == "gpt-4o"
        assert models[0]["description"] == "Most capable GPT-4 Omni model for complex tasks"
        assert models[0]["is_default"] is True
        mock_provider.agents.get_available_models.assert_called_once()

    def test_get_available_models_unauthorized(self, test_client):
        """Test getting models without authentication."""
        response = test_client.get("/agents/models")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_get_available_models_multiple(self, authenticated_client):
        """Test getting multiple available models."""
        client, auth_headers, mock_provider = authenticated_client
        
        # Mock multiple models
        mock_provider.agents.get_available_models.return_value = [
            {
                'name': 'gpt-4o',
                'description': 'Most capable GPT-4 Omni model for complex tasks',
                'is_default': True
            },
            {
                'name': 'gpt-4o-mini',
                'description': 'Smaller, faster GPT-4 Omni model',
                'is_default': False
            },
            {
                'name': 'gpt-3.5-turbo',
                'description': 'Fast and efficient model for simple tasks',
                'is_default': False
            }
        ]
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 3
        
        # Check default model
        default_models = [m for m in models if m["is_default"]]
        assert len(default_models) == 1
        assert default_models[0]["name"] == "gpt-4o"
        
        # Check non-default models
        non_default_models = [m for m in models if not m["is_default"]]
        assert len(non_default_models) == 2
        assert any(m["name"] == "gpt-4o-mini" for m in non_default_models)
        assert any(m["name"] == "gpt-3.5-turbo" for m in non_default_models)

    def test_get_available_models_empty(self, authenticated_client):
        """Test getting models when none are available."""
        client, auth_headers, mock_provider = authenticated_client
        
        # Mock empty models list
        mock_provider.agents.get_available_models.return_value = []
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 0

    def test_get_available_models_error(self, authenticated_client):
        """Test handling error when getting models."""
        client, auth_headers, mock_provider = authenticated_client
        
        # Mock exception
        mock_provider.agents.get_available_models.side_effect = Exception("Provider error")
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Could not fetch available models."