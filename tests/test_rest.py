import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import timedelta
import logging
# from bondable.rest.main import app, create_access_token, JWT_SECRET_KEY as MAIN_JWT_SECRET, JWT_ALGORITHM, ThreadRef
from bondable.rest.main import app, create_access_token
from bondable.rest.models.threads import ThreadRef, MessageRef
from bondable.rest.models.agents import AgentResponse, AgentCreateRequest, AgentUpdateRequest, ToolResourcesRequest, ToolResourceFilesList
from bondable.bond.config import Config
from bondable.bond.providers.agent import Agent # Needed for mocking
from bondable.bond.providers.threads import ThreadsProvider # Needed for mocking

from dotenv import load_dotenv
load_dotenv()

jwt_config = Config.config().get_jwt_config()

# --- Configuration ---
TEST_USER_EMAIL = "jmcarny@gmail.com"
TEST_USER_ID = "test-user-id-456"
# Mock paths for dependencies called by endpoints
MOCK_AGENT_LIST_PATH = "bondable.rest.main.Agent.list_agents"
MOCK_THREADS_LIST_PATH = "bondable.rest.main.ThreadsProvider.threads" # Added for /threads endpoint
MOCK_AGENT_GET_PATH = "bondable.rest.main.Agent.get_agent" # Added for /chat endpoint
MOCK_AGENT_BUILDER_GET_AGENT_PATH = "bondable.rest.main.AgentBuilder.builder" # For new agent endpoints

# Verify the imported JWT Secret matches our intended test key
# assert MAIN_JWT_SECRET == TEST_SECRET_KEY, f"App loaded JWT Secret '{MAIN_JWT_SECRET}' which differs from test key '{TEST_SECRET_KEY}'"

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_client() -> TestClient:
    """Provides a TestClient instance for the FastAPI app (module-scoped)."""
    client = TestClient(app)
    return client

@pytest.fixture(scope="function")
def authenticated_client(test_client: TestClient) -> tuple[TestClient, dict]:
    """
    Provides a TestClient instance along with valid JWT Authorization headers.
    Function-scoped for test isolation (fresh token per test).
    Returns a tuple: (client, auth_headers)
    """
    token_data = {"sub": TEST_USER_EMAIL, "name": "Test User", "provider": "google", "user_id": TEST_USER_ID}
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    yield (test_client, auth_headers)

# --- Test Cases ---

@patch(MOCK_AGENT_LIST_PATH)
def test_get_agents_success(mock_list_agents, authenticated_client):
    """
    Tests the GET /agents endpoint with valid authentication (happy path).
    Mocks the underlying Agent.list_agents call.
    """
    client, auth_headers = authenticated_client

    # --- Mock Setup ---
    mock_agent_1 = MagicMock(spec=Agent)
    mock_agent_1.get_id.return_value = "agent_123"
    mock_agent_1.get_name.return_value = "Test Agent One"
    mock_agent_1.get_description.return_value = "Description for agent one"

    mock_agent_2 = MagicMock(spec=Agent)
    mock_agent_2.get_id.return_value = "agent_456"
    mock_agent_2.get_name.return_value = "Test Agent Two"
    mock_agent_2.get_description.return_value = None

    mock_list_agents.return_value = [mock_agent_1, mock_agent_2]

    # --- Test Execution ---
    response = client.get("/agents", headers=auth_headers)

    # --- Assertions ---
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"

    expected_json = [
        {"id": "agent_123", "name": "Test Agent One", "description": "Description for agent one"},
        {"id": "agent_456", "name": "Test Agent Two", "description": None},
    ]
    assert response.json() == expected_json

    mock_list_agents.assert_called_once_with(user_id=TEST_USER_ID)


@patch(MOCK_THREADS_LIST_PATH)
def test_get_threads_success(mock_threads_cls, authenticated_client):
    """
    Tests the GET /threads endpoint with valid authentication (happy path).
    Mocks the underlying Threads.threads().get_current_threads() call chain.
    """
    client, auth_headers = authenticated_client

    # --- Mock Setup ---
    # The endpoint calls Threads.threads(user_id=...).get_current_threads()
    # So, the mock for the class needs to return an object that has get_current_threads
    mock_threads_instance = MagicMock()
    mock_threads_instance.get_current_threads.return_value = [
        {"thread_id": "thread_abc", "name": "Thread Alpha"},
        {"thread_id": "thread_def", "name": "Thread Beta"}, # Assuming 'name' exists, adjust if needed
    ]
    # Configure the class mock to return this instance when called
    mock_threads_cls.return_value = mock_threads_instance

    # --- Test Execution ---
    response = client.get("/threads", headers=auth_headers)

    # --- Assertions ---
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"

    # Check the JSON response matches the mocked data structure defined by ThreadRef Pydantic model
    # Note: ThreadRef in main.py currently expects 'id' and 'name', and optionally 'description'
    # Adjusting expected output based on ThreadRef definition
    expected_json = [
        # The mock returns dicts with 'thread_id', 'name'. ThreadRef expects 'id', 'name'.
        # The list comprehension in main.py handles this mapping.
        {"id": "thread_abc", "name": "Thread Alpha", "description": None}, # Assuming description defaults to None if not present
        {"id": "thread_def", "name": "Thread Beta", "description": None},
    ]
    # Need to check the ThreadRef model in main.py again - it uses id, name, description (optional)
    # The list comprehension in the endpoint correctly maps thread_id to id.
    assert response.json() == expected_json

    # Verify that the mocked class method was called correctly
    mock_threads_cls.assert_called_once_with(user_id=TEST_USER_ID)
    # Verify the chained method call on the returned instance
    mock_threads_instance.get_current_threads.assert_called_once()


@patch(MOCK_THREADS_LIST_PATH) # This constant points to "bondable.rest.main.Threads.threads"
def test_get_messages_success(mock_threads_cls, authenticated_client):
    """
    Tests the GET /threads/{thread_id}/messages endpoint (happy path).
    Mocks Threads.threads().get_messages() call chain.
    """
    client, auth_headers = authenticated_client
    test_thread_id = "test_thread_for_messages_123"

    # --- Mock Setup ---
    # Mock the instance returned by Threads.threads(user_id=...)
    mock_threads_instance = MagicMock()
    
    # Mock the get_messages method on this instance
    mock_messages_data = [
        {"message_id": "msg_alpha", "type": "user_message", "role": "user", "content": "First message"},
        {"message_id": "msg_beta", "type": "assistant_message", "role": "assistant", "content": "Reply to first"},
    ]
    mock_threads_instance.get_messages.return_value = mock_messages_data
    
    # Configure the class mock Threads.threads to return our specific instance
    mock_threads_cls.return_value = mock_threads_instance

    # --- Test Execution ---
    response = client.get(f"/threads/{test_thread_id}/messages", headers=auth_headers)

    # --- Assertions ---
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"

    # Expected JSON based on MessageRef model and mocked data
    expected_json = [
        {"id": "msg_alpha", "type": "user_message", "role": "user", "content": "First message"},
        {"id": "msg_beta", "type": "assistant_message", "role": "assistant", "content": "Reply to first"},
    ]
    assert response.json() == expected_json

    # Verify that Threads.threads(user_id=...) was called
    mock_threads_cls.assert_called_once_with(user_id=TEST_USER_ID)
    
    # Verify that get_messages(thread_id=...) was called on the instance with correct parameters
    # The endpoint defaults limit to 100
    mock_threads_instance.get_messages.assert_called_once_with(thread_id=test_thread_id, limit=100)


@patch(MOCK_AGENT_GET_PATH)
def test_chat_success(mock_get_agent, authenticated_client):
    """
    Tests the GET /chat endpoint with valid authentication (happy path).
    Mocks Agent.get_agent and its chained calls validate_user_access & stream_response.
    """
    client, auth_headers = authenticated_client
    test_thread_id = "chat_thread_789"
    test_agent_id = "chat_agent_abc"
    test_prompt = "Hello agent, this is a test prompt." # Added test prompt

    # --- Mock Setup ---
    # Mock the agent instance that Agent.get_agent(assistant_id) would return
    mock_agent_instance = MagicMock(spec=Agent)
    
    # Configure validate_user_access on this agent instance to return True
    mock_agent_instance.validate_user_access.return_value = True
    
    # Configure stream_response on this agent instance to yield sample stream data
    # Simulating Server-Sent Events (SSE) format: "data: your_json_or_text\n\n"
    # Or just raw text chunks if that's what your stream_response yields.
    # Let's assume it yields simple text chunks for this example.
    mock_stream_data = ["Hello, ", "world! ", "This is a stream."]
    mock_agent_instance.stream_response.return_value = (chunk for chunk in mock_stream_data) # Use a generator

    # Configure the patched Agent.get_agent to return our mock_agent_instance
    mock_get_agent.return_value = mock_agent_instance

    # --- Test Execution ---
    request_data = {"thread_id": test_thread_id, "agent_id": test_agent_id, "prompt": test_prompt}
    response = client.post("/chat", headers=auth_headers, json=request_data) # Changed to POST and send data in json

    # --- Assertions ---
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"
    # Make the content-type check more robust by checking the start of the string
    assert response.headers["content-type"].startswith("text/event-stream"), \
        f"Expected content-type to start with text/event-stream, got {response.headers.get('content-type')}"

    # Collect streamed content
    # response.text will usually block and read the whole stream if it's short.
    # For true streaming test, you might iterate response.iter_bytes() or response.iter_lines()
    # but response.text is often sufficient for TestClient if the stream is not infinite.
    streamed_content = response.text
    expected_content = "".join(mock_stream_data)
    assert streamed_content == expected_content, \
        f"Streamed content mismatch. Expected: '{expected_content}', Got: '{streamed_content}'"

    # Verify that Agent.get_agent was called with the correct agent_id
    mock_get_agent.assert_called_once_with(test_agent_id) # Changed to test_agent_id
    
    # Verify that validate_user_access was called on the agent instance
    mock_agent_instance.validate_user_access.assert_called_once_with(
        user_id=TEST_USER_ID, agent_id=test_agent_id # Changed to test_agent_id
    )
    
    # Verify that stream_response was called on the agent instance
    mock_agent_instance.stream_response.assert_called_once_with(thread_id=test_thread_id, prompt=test_prompt) # Verify prompt was passed


@patch(MOCK_THREADS_LIST_PATH) # Reusing because it points to Threads.threads
def test_create_new_thread_success(mock_threads_cls, authenticated_client):
    """
    Tests the POST /threads endpoint for creating a new thread with a specified name.
    Mocks Threads.threads().create_thread().
    """
    client, auth_headers = authenticated_client
    
    test_thread_name = "My Custom Thread Name"
    mock_new_thread_id = "new_thread_with_name_xyz789"

    # --- Mock Setup ---
    # Mock the instance returned by Threads.threads(user_id=...)
    mock_threads_instance = MagicMock()
    
    # Mock the create_thread method on this instance to return an object with thread_id and name attributes
    mock_created_orm_thread = MagicMock()
    mock_created_orm_thread.thread_id = mock_new_thread_id
    mock_created_orm_thread.name = test_thread_name # The name provided in the request
    mock_threads_instance.create_thread.return_value = mock_created_orm_thread
    
    # Configure the class mock Threads.threads to return our specific instance
    mock_threads_cls.return_value = mock_threads_instance

    # --- Test Execution ---
    # Send the name in the request body
    response = client.post("/threads", headers=auth_headers, json={"name": test_thread_name})

    # --- Assertions ---
    assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}. Response: {response.text}"

    # Expected JSON based on ThreadRef model and mocked data
    expected_json = {
        "id": mock_new_thread_id,
        "name": test_thread_name, # Expect the name we sent
        "description": None, 
    }
    assert response.json() == expected_json

    # Verify that Threads.threads(user_id=...) was called
    mock_threads_cls.assert_called_once_with(user_id=TEST_USER_ID)
    
    # Verify that create_thread() was called on the instance with the specified name
    mock_threads_instance.create_thread.assert_called_once_with(name=test_thread_name)
    
    # update_thread_name should NOT have been called by the endpoint
    mock_threads_instance.update_thread_name.assert_not_called()


@patch(MOCK_THREADS_LIST_PATH) # Reusing because it points to Threads.threads
def test_create_new_thread_success_no_name(mock_threads_cls, authenticated_client):
    """
    Tests the POST /threads endpoint for creating a new thread without a specified name.
    The endpoint should default the name (e.g., to "New Thread").
    Mocks Threads.threads().create_thread().
    """
    client, auth_headers = authenticated_client
    
    mock_new_thread_id = "new_thread_no_name_abc456"
    # As per current main.py logic, if name is not provided in request, it defaults to "New Thread" in the response.
    expected_default_name = "New Thread" # This is the default from the Thread ORM model if name is None

    # --- Mock Setup ---
    mock_threads_instance = MagicMock()
    
    # Mock create_thread to return an ORM-like object
    # If name=None is passed to service, the DB default "New Thread" should apply.
    mock_created_orm_thread_no_name = MagicMock()
    mock_created_orm_thread_no_name.thread_id = mock_new_thread_id
    mock_created_orm_thread_no_name.name = expected_default_name # Simulate DB default being set
    mock_threads_instance.create_thread.return_value = mock_created_orm_thread_no_name
    
    mock_threads_cls.return_value = mock_threads_instance

    # --- Test Execution ---
    # Send an empty JSON body or a body with name: null
    response = client.post("/threads", headers=auth_headers, json={"name": None})

    # --- Assertions ---
    assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}. Response: {response.text}"
    expected_json = {
        "id": mock_new_thread_id,
        "name": expected_default_name, # Expecting the default name set by the endpoint
        "description": None,
    }
    assert response.json() == expected_json
    mock_threads_cls.assert_called_once_with(user_id=TEST_USER_ID)
    # create_thread in the service layer should be called with name=None
    mock_threads_instance.create_thread.assert_called_once_with(name=None) 
    mock_threads_instance.update_thread_name.assert_not_called()


@patch(MOCK_AGENT_BUILDER_GET_AGENT_PATH)
def test_create_agent_endpoint(mock_builder_factory, authenticated_client):
    """Tests creating a new agent via POST /agents."""
    client, auth_headers = authenticated_client
    
    request_payload = AgentCreateRequest(
        name="MyNewAgentAPI",
        description="A brand new test agent via API.",
        instructions="Be helpful and new.",
        tools=[{"type": "code_interpreter"}],
        tool_resources=ToolResourcesRequest(
            code_interpreter=ToolResourceFilesList(file_ids=["file-newapi123"])
        ),
        metadata={"version": "1.0"}
    ).model_dump(exclude_none=True) # Use .model_dump() for Pydantic v2+

    mock_agent_id = "asst_apicreated_123"

    mock_builder_instance = MagicMock()
    mock_agent_object = MagicMock(spec=Agent)
    mock_agent_object.get_id.return_value = mock_agent_id
    mock_agent_object.get_name.return_value = request_payload["name"] 
    mock_builder_instance.get_agent.return_value = mock_agent_object
    mock_builder_factory.return_value = mock_builder_instance

    response = client.post("/agents", headers=auth_headers, json=request_payload)

    assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}. Response: {response.text}"
    response_data = response.json()
    assert response_data["agent_id"] == mock_agent_id
    assert response_data["name"] == request_payload["name"]

    mock_builder_factory.assert_called_once()
    mock_builder_instance.get_agent.assert_called_once()
    called_agent_def = mock_builder_instance.get_agent.call_args[0][0]
    assert called_agent_def.name == request_payload["name"]
    assert called_agent_def.id is None # ID should be None for creation


@patch(MOCK_AGENT_BUILDER_GET_AGENT_PATH)
def test_update_agent_endpoint(mock_builder_factory, authenticated_client):
    """Tests updating an existing agent via PUT /agents/{assistant_id}."""
    client, auth_headers = authenticated_client
    assistant_id_to_update = "asst_existing_for_update_789"
    
    request_payload = AgentUpdateRequest(
        name="UpdatedAgentNameAPI",
        description="An updated description via API.",
        instructions="Be helpful and very updated.",
        tools=[{"type": "file_search"}],
        tool_resources=ToolResourcesRequest(
            file_search=ToolResourceFilesList(file_ids=["vs-apiupdate456"])
        ),
        metadata={"version": "2.0"}
    ).model_dump(exclude_none=True) # Use .model_dump()

    mock_builder_instance = MagicMock()
    mock_agent_object = MagicMock(spec=Agent)
    mock_agent_object.get_id.return_value = assistant_id_to_update # Should return the ID it was called with
    mock_agent_object.get_name.return_value = request_payload["name"] # Should return the new name
    mock_builder_instance.get_agent.return_value = mock_agent_object
    mock_builder_factory.return_value = mock_builder_instance

    response = client.put(f"/agents/{assistant_id_to_update}", headers=auth_headers, json=request_payload)

    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"
    response_data = response.json()
    assert response_data["agent_id"] == assistant_id_to_update
    assert response_data["name"] == request_payload["name"]
    
    mock_builder_factory.assert_called_once()
    mock_builder_instance.get_agent.assert_called_once()
    called_agent_def = mock_builder_instance.get_agent.call_args[0][0]
    assert called_agent_def.id == assistant_id_to_update # ID should be passed for update
    assert called_agent_def.name == request_payload["name"]
