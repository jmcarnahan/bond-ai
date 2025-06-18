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
from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider

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
def mock_bedrock_provider():
    """Mock Bedrock provider with get_available_models returning Bedrock models."""
    provider = MagicMock(spec=Provider)
    provider.agents = MagicMock(spec=AgentProvider)
    
    # Mock the get_available_models method to return Bedrock-style models
    provider.agents.get_available_models.return_value = [
        {
            'id': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
            'name': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
            'description': 'Anthropic - Claude 3.5 Sonnet v2',
            'is_default': False,
            'provider': 'Anthropic',
            'input_modalities': ['TEXT'],
            'output_modalities': ['TEXT'],
            'supports_streaming': True,
            'supports_tools': True,
            'max_tokens': 8192
        },
        {
            'id': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'name': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'description': 'Anthropic - Claude 3 Haiku',
            'is_default': True,
            'provider': 'Anthropic',
            'input_modalities': ['TEXT'],
            'output_modalities': ['TEXT'],
            'supports_streaming': True,
            'supports_tools': True,
            'max_tokens': 4096
        },
        {
            'id': 'amazon.titan-text-express-v1',
            'name': 'amazon.titan-text-express-v1',
            'description': 'Amazon - Titan Text Express v1',
            'is_default': False,
            'provider': 'Amazon',
            'input_modalities': ['TEXT'],
            'output_modalities': ['TEXT'],
            'supports_streaming': True,
            'supports_tools': False,
            'max_tokens': 8192
        }
    ]
    
    provider.get_default_model.return_value = "us.anthropic.claude-3-haiku-20240307-v1:0"
    return provider

@pytest.fixture
def authenticated_bedrock_client(test_client, mock_bedrock_provider):
    """Test client with authentication and mocked Bedrock provider."""
    # Override provider dependency
    app.dependency_overrides[get_bond_provider] = lambda: mock_bedrock_provider
    
    # Create valid JWT token with required fields
    token_data = {
        "sub": TEST_USER_EMAIL, 
        "name": "Test User",
        "provider": "google",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    
    yield test_client, auth_headers, mock_bedrock_provider
    
    # Clean up
    if get_bond_provider in app.dependency_overrides:
        del app.dependency_overrides[get_bond_provider]

# --- Model Endpoint Tests with Bedrock ---

class TestBedrockModelsEndpoint:
    
    def test_get_available_models_bedrock_format(self, authenticated_bedrock_client):
        """Test that Bedrock models are correctly transformed to REST API format."""
        client, auth_headers, mock_provider = authenticated_bedrock_client
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 3
        
        # Check that only the required fields are returned (extra fields stripped)
        for model in models:
            assert set(model.keys()) == {"name", "description", "is_default"}
            assert isinstance(model["name"], str)
            assert isinstance(model["description"], str)
            assert isinstance(model["is_default"], bool)
        
        # Check specific models
        model_names = [m["name"] for m in models]
        assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in model_names
        assert "us.anthropic.claude-3-haiku-20240307-v1:0" in model_names
        assert "amazon.titan-text-express-v1" in model_names
        
        # Check default model
        default_models = [m for m in models if m["is_default"]]
        assert len(default_models) == 1
        assert default_models[0]["name"] == "us.anthropic.claude-3-haiku-20240307-v1:0"
        
        mock_provider.agents.get_available_models.assert_called_once()
    
    def test_create_agent_with_bedrock_default_model(self, authenticated_bedrock_client):
        """Test creating agent without specifying model uses Bedrock default."""
        client, auth_headers, mock_provider = authenticated_bedrock_client
        
        # Setup mock
        mock_agent = MagicMock()
        mock_agent.get_agent_id.return_value = "bedrock_agent_id"
        mock_agent.get_name.return_value = "Bedrock Test Agent"
        mock_provider.agents.create_or_update_agent.return_value = mock_agent
        
        agent_data = {
            "name": "Bedrock Test Agent",
            "description": "Testing Bedrock model selection",
            "instructions": "You are a test agent using Bedrock",
            "tools": [{"type": "code_interpreter"}, {"type": "file_search"}]
            # Note: no model specified
        }
        
        response = client.post("/agents", headers=auth_headers, json=agent_data)
        
        assert response.status_code == 201
        result = response.json()
        assert result["agent_id"] == "bedrock_agent_id"
        assert result["name"] == "Bedrock Test Agent"
        
        # Check that the agent was created with Bedrock default model
        create_call = mock_provider.agents.create_or_update_agent.call_args
        agent_def = create_call.kwargs['agent_def']
        assert agent_def.model == "us.anthropic.claude-3-haiku-20240307-v1:0"
    
    def test_create_agent_with_explicit_bedrock_model(self, authenticated_bedrock_client):
        """Test creating agent with explicitly specified Bedrock model."""
        client, auth_headers, mock_provider = authenticated_bedrock_client
        
        # Setup mock
        mock_agent = MagicMock()
        mock_agent.get_agent_id.return_value = "bedrock_agent_id"
        mock_agent.get_name.return_value = "Bedrock Test Agent"
        mock_provider.agents.create_or_update_agent.return_value = mock_agent
        
        agent_data = {
            "name": "Bedrock Test Agent",
            "description": "Testing explicit Bedrock model",
            "instructions": "You are a test agent using Claude 3.5 Sonnet",
            "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "tools": [{"type": "code_interpreter"}]
        }
        
        response = client.post("/agents", headers=auth_headers, json=agent_data)
        
        assert response.status_code == 201
        
        # Check that the agent was created with specified model
        create_call = mock_provider.agents.create_or_update_agent.call_args
        agent_def = create_call.kwargs['agent_def']
        assert agent_def.model == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    
    def test_bedrock_models_empty_list(self, authenticated_bedrock_client):
        """Test handling empty models list from Bedrock."""
        client, auth_headers, mock_provider = authenticated_bedrock_client
        
        # Mock empty models list
        mock_provider.agents.get_available_models.return_value = []
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 0
    
    def test_bedrock_models_api_error(self, authenticated_bedrock_client):
        """Test handling error from Bedrock when getting models."""
        client, auth_headers, mock_provider = authenticated_bedrock_client
        
        # Mock exception
        mock_provider.agents.get_available_models.side_effect = Exception("Bedrock API error")
        
        response = client.get("/agents/models", headers=auth_headers)
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Could not fetch available models."