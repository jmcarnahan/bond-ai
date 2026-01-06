"""Tests for the default agent functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from bondable.bond.providers.agent import AgentProvider, Agent
from bondable.bond.providers.metadata import Metadata, AgentRecord, User


class MockAgentDefinition:
    """Simple mock of AgentDefinition to avoid provider dependencies."""
    def __init__(self, user_id, id, name, description, instructions, model,
                 introduction="", reminder="", tools=None, metadata=None, **kwargs):
        self.user_id = user_id
        self.id = id
        self.name = name
        self.description = description
        self.instructions = instructions
        self.model = model
        self.introduction = introduction
        self.reminder = reminder
        self.tools = tools or []
        self.metadata = metadata or {}
        self.tool_resources = {"code_interpreter": {"file_ids": []}, "file_search": {"vector_store_ids": []}}


class MockAgent(Agent):
    """Mock implementation of Agent for testing."""

    def __init__(self, agent_id, agent_def):
        self.agent_id = agent_id
        self.agent_def = agent_def

    def get_agent_id(self):
        return self.agent_id

    def get_agent_definition(self):
        return self.agent_def

    def get_name(self):
        return self.agent_def.name

    def get_description(self):
        return self.agent_def.instructions[:100] if self.agent_def.instructions else ""

    def get_metadata_value(self, key, default_value=None):
        return self.agent_def.metadata.get(key, default_value)

    def get_metadata(self):
        return self.agent_def.metadata

    def create_user_message(self, prompt, thread_id, attachments=None, override_role="user"):
        return f"msg-{self.agent_id}-{thread_id}"

    def stream_response(self, prompt=None, thread_id=None, attachments=None, override_role="user"):
        yield f"Response from {self.agent_id}"


class MockAgentProvider(AgentProvider):
    """Mock implementation of AgentProvider for testing."""

    def __init__(self, metadata):
        super().__init__(metadata)
        self.agents_db = {}  # Simple in-memory storage

    def delete_agent_resource(self, agent_id):
        if agent_id in self.agents_db:
            del self.agents_db[agent_id]
            return True
        return False

    def create_or_update_agent_resource(self, agent_def, owner_user_id):
        agent = MockAgent(agent_def.id, agent_def)
        self.agents_db[agent_def.id] = agent
        return agent

    def get_agent(self, agent_id):
        agent = self.agents_db.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return agent

    def get_available_models(self):
        return [
            {"name": "gpt-4", "description": "GPT-4 model", "is_default": False},
            {"name": "gpt-4o-mini", "description": "GPT-4 Optimized Mini", "is_default": True},
            {"name": "gpt-3.5-turbo", "description": "GPT-3.5 Turbo", "is_default": False}
        ]


class TestDefaultAgent:
    """Test cases for default agent functionality."""

    @pytest.fixture
    def mock_metadata(self):
        """Create a mock metadata instance."""
        metadata = Mock(spec=Metadata)
        metadata.get_db_session = MagicMock()
        return metadata

    @pytest.fixture
    def mock_session(self, mock_metadata):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=None)
        mock_metadata.get_db_session.return_value = session
        return session

    @pytest.fixture
    def agent_provider(self, mock_metadata):
        """Create an agent provider instance."""
        return MockAgentProvider(mock_metadata)

    def test_get_default_agent_when_exists(self, agent_provider, mock_session, mock_metadata):
        """Test getting default agent when one already exists."""
        # Create a mock default agent record
        default_agent_record = Mock(spec=AgentRecord)
        default_agent_record.agent_id = "existing-default-agent"
        default_agent_record.is_default = True

        # Set up the query to return the default agent
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = default_agent_record
        mock_session.query.return_value = mock_query

        # Create the actual agent in the provider
        agent_def = MockAgentDefinition(
            user_id="user-123",
            id="existing-default-agent",
            name="Existing Default",
            description="Existing default agent",
            model="gpt-4",
            instructions="I am the existing default agent"
        )
        existing_agent = agent_provider.create_or_update_agent_resource(agent_def, "user-123")

        # Get the default agent
        result = agent_provider.get_default_agent()

        # Verify the result
        assert result is not None
        assert result.get_agent_id() == "existing-default-agent"
        assert result.get_name() == "Existing Default"

        # Verify the query was made correctly
        mock_session.query.assert_called_with(AgentRecord)
        mock_query.filter.assert_called()

    @patch('bondable.bond.providers.agent.AgentDefinition', MockAgentDefinition)
    def test_get_default_agent_creates_new_when_none_exists(self, agent_provider, mock_session, mock_metadata):
        """Test creating a new default agent when none exists."""
        # Set up the query to return no default agent
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        # Mock the system user
        system_user = Mock(spec=User)
        system_user.id = "system-user-123"
        system_user.email = "system@bondableai.com"
        mock_metadata.get_or_create_system_user.return_value = system_user

        # Mock the agent record for marking as default
        new_agent_record = Mock(spec=AgentRecord)
        new_agent_record.agent_id = "default-home-agent"

        # Set up query for finding the created agent record
        def query_side_effect(model):
            query = Mock()
            if mock_session.query.call_count <= 1:
                # First call - no default agent
                query.filter.return_value.first.return_value = None
            else:
                # Subsequent calls - return the new agent record
                query.filter.return_value.first.return_value = new_agent_record
            return query

        mock_session.query.side_effect = query_side_effect

        # Get the default agent (should create new one)
        result = agent_provider.get_default_agent()

        # Verify the result
        assert result is not None
        assert result.get_agent_id() == "default-home-agent"
        assert result.get_name() == "Home"
        assert result.get_agent_definition().model == "gpt-4o-mini"  # Default model
        tools = result.get_agent_definition().tools
        assert any(tool.get("type") == "code_interpreter" for tool in tools)
        assert any(tool.get("type") == "file_search" for tool in tools)

        # Verify system user was created/retrieved
        mock_metadata.get_or_create_system_user.assert_called_once()

        # Verify the agent record was marked as default
        assert new_agent_record.is_default == True
        mock_session.commit.assert_called()

    @patch('bondable.bond.providers.agent.AgentDefinition', MockAgentDefinition)
    def test_get_default_agent_handles_retrieval_error(self, agent_provider, mock_session, mock_metadata):
        """Test handling errors when retrieving existing default agent."""
        # Create a mock default agent record
        default_agent_record = Mock(spec=AgentRecord)
        default_agent_record.agent_id = "broken-default-agent"
        default_agent_record.is_default = True

        # Set up the query to return the default agent
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = default_agent_record
        mock_session.query.return_value = mock_query

        # Don't create the agent in the provider, so get_agent will fail

        # Mock the system user for creating new default
        system_user = Mock(spec=User)
        system_user.id = "system-user-123"
        mock_metadata.get_or_create_system_user.return_value = system_user

        # Set up for creating new default agent
        new_agent_record = Mock(spec=AgentRecord)
        new_agent_record.agent_id = "default-home-agent"

        def query_side_effect(model):
            query = Mock()
            if mock_session.query.call_count <= 1:
                # First call - broken default agent
                query.filter.return_value.first.return_value = default_agent_record
            else:
                # Subsequent calls - return the new agent record
                query.filter.return_value.first.return_value = new_agent_record
            return query

        mock_session.query.side_effect = query_side_effect

        # Get the default agent (should create new one after failure)
        result = agent_provider.get_default_agent()

        # Verify a new default agent was created
        assert result is not None
        assert result.get_agent_id() == "default-home-agent"
        assert result.get_name() == "Home"

    @patch('bondable.bond.providers.agent.AgentDefinition', MockAgentDefinition)
    def test_get_default_agent_returns_none_on_creation_failure(self, agent_provider, mock_session, mock_metadata):
        """Test returning None when default agent creation fails."""
        # Set up the query to return no default agent
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        # Mock the system user
        system_user = Mock(spec=User)
        system_user.id = "system-user-123"
        mock_metadata.get_or_create_system_user.return_value = system_user

        # Make create_or_update_agent fail
        with patch.object(agent_provider, 'create_or_update_agent', side_effect=Exception("Creation failed")):
            result = agent_provider.get_default_agent()

        # Verify None is returned
        assert result is None

    def test_get_default_model(self, agent_provider):
        """Test getting the default model from available models."""
        # Test with default model marked
        default_model = agent_provider.get_default_model()
        assert default_model == "gpt-4o-mini"

        # Test with no default marked (should return first)
        agent_provider.get_available_models = lambda: [
            {"name": "model-1", "description": "Model 1", "is_default": False},
            {"name": "model-2", "description": "Model 2", "is_default": False}
        ]
        default_model = agent_provider.get_default_model()
        assert default_model == "model-1"

        # Test with no models (should raise exception)
        agent_provider.get_available_models = lambda: []
        with pytest.raises(RuntimeError, match="No models were found"):
            agent_provider.get_default_model()


class TestDefaultAgentEndpoint:
    """Test cases for the default agent REST endpoint."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider with agent provider."""
        provider = Mock()
        provider.agents = Mock()
        return provider

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Mock()
        agent.get_agent_id.return_value = "default-home-agent"
        agent.get_name.return_value = "Home"
        return agent

    @pytest.fixture
    def client(self, mock_provider):
        """Create a test client with mocked dependencies."""
        from fastapi.testclient import TestClient
        from bondable.rest.main import app
        from bondable.rest.dependencies.providers import get_bond_provider
        from bondable.rest.dependencies.auth import get_current_user

        # Mock the current user
        mock_user = Mock()
        mock_user.user_id = "test-user-123"
        mock_user.email = "test@example.com"

        # Override dependencies
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider
        app.dependency_overrides[get_current_user] = lambda: mock_user

        client = TestClient(app)
        yield client

        # Clean up
        app.dependency_overrides.clear()

    def test_get_default_agent_success(self, client, mock_provider, mock_agent):
        """Test successful retrieval of default agent."""
        # Set up the mock to return the default agent
        mock_provider.agents.get_default_agent.return_value = mock_agent

        # Make the request
        response = client.get("/agents/default")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "default-home-agent"
        assert data["name"] == "Home"

        # Verify get_default_agent was called
        mock_provider.agents.get_default_agent.assert_called_once()

    def test_get_default_agent_creates_new(self, client, mock_provider, mock_agent):
        """Test that endpoint creates a new default agent if none exists."""
        # Simulate creating a new agent by returning the mock after "creation"
        mock_provider.agents.get_default_agent.return_value = mock_agent

        # Make the request
        response = client.get("/agents/default")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "default-home-agent"
        assert data["name"] == "Home"

    def test_get_default_agent_returns_none(self, client, mock_provider):
        """Test handling when get_default_agent returns None."""
        # Set up the mock to return None
        mock_provider.agents.get_default_agent.return_value = None

        # Make the request
        response = client.get("/agents/default")

        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get or create default agent" in data["detail"]

    def test_get_default_agent_exception(self, client, mock_provider):
        """Test handling exceptions from get_default_agent."""
        # Set up the mock to raise an exception
        mock_provider.agents.get_default_agent.side_effect = Exception("Database error")

        # Make the request
        response = client.get("/agents/default")

        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "Error getting default agent: Database error" in data["detail"]

    def test_get_default_agent_requires_auth(self, mock_provider):
        """Test that the endpoint requires authentication."""
        from fastapi.testclient import TestClient
        from bondable.rest.main import app
        from bondable.rest.dependencies.providers import get_bond_provider

        # Only override the provider, not the auth
        app.dependency_overrides[get_bond_provider] = lambda: mock_provider

        client = TestClient(app)

        # Make request without auth
        response = client.get("/agents/default")

        # Should get unauthorized
        assert response.status_code == 401

        # Clean up
        app.dependency_overrides.clear()

    def test_integration_default_agent_flow(self, client, mock_provider):
        """Integration test for the complete default agent flow."""
        # First call returns None (no default exists)
        # Second call (after internal creation) returns the agent
        mock_agent = Mock()
        mock_agent.get_agent_id.return_value = "default-home-agent"
        mock_agent.get_name.return_value = "Home"

        # Simulate the agent being created on first call
        mock_provider.agents.get_default_agent.return_value = mock_agent

        # First request - should create and return default
        response1 = client.get("/agents/default")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["agent_id"] == "default-home-agent"

        # Second request - should return existing default
        response2 = client.get("/agents/default")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["agent_id"] == "default-home-agent"

        # Verify get_default_agent was called twice
        assert mock_provider.agents.get_default_agent.call_count == 2
