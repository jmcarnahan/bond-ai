import httpx
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional # Added import for Optional
from jose import jwt
from dotenv import load_dotenv

# For cleanup - direct import from your project structure
from bondable.bond.builder import AgentBuilder
from bondable.bond.config import Config # To ensure config is loaded for builder

# --- Configuration ---
load_dotenv() # Load environment variables from .env file

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000") # Ensure your API runs here
TEST_USER_EMAIL = "script_test_user@example.com" # Or any other email

# JWT Configuration - ensure these match your .env or bondable.bond.config
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY not set in environment. Please ensure it's in your .env file.")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s')
LOGGER = logging.getLogger(__name__)

# --- Helper Functions ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_agent(client: httpx.Client, headers: dict, agent_name: str, agent_def_payload: dict):
    """Creates or updates an agent using the POST /agents endpoint."""
    LOGGER.info(f"Attempting to create agent: {agent_name}")
    # The endpoint is POST /agents, name is in payload
    response = client.post(f"{API_BASE_URL}/agents", headers=headers, json=agent_def_payload)
    response.raise_for_status() # Raise an exception for bad status codes
    agent_data = response.json()
    LOGGER.info(f"Agent created/retrieved: ID={agent_data['agent_id']}, Name={agent_data['name']}")
    return agent_data

def create_thread(client: httpx.Client, headers: dict, thread_name: Optional[str] = None):
    """Creates a new thread using the POST /threads endpoint."""
    LOGGER.info(f"Attempting to create thread with name: {thread_name if thread_name else 'Default Name'}")
    payload = {}
    if thread_name:
        payload["name"] = thread_name
    
    response = client.post(f"{API_BASE_URL}/threads", headers=headers, json=payload)
    response.raise_for_status()
    thread_data = response.json()
    LOGGER.info(f"Thread created: ID={thread_data['id']}, Name={thread_data['name']}")
    return thread_data

def chat_with_agent(client: httpx.Client, headers: dict, thread_id: str, agent_id: str, prompt: str):
    """Sends a prompt to the chat endpoint and streams the response."""
    LOGGER.info(f"Sending prompt to agent {agent_id} in thread {thread_id}: '{prompt}'")
    payload = {
        "thread_id": thread_id,
        "agent_id": agent_id,
        "prompt": prompt
    }
    with client.stream("POST", f"{API_BASE_URL}/chat", headers=headers, json=payload, timeout=60) as response:
        response.raise_for_status()
        LOGGER.info("Chat stream started. Receiving response:")
        full_response_content = ""
        for chunk in response.iter_text():
            print(chunk, end="", flush=True) # Print chunks as they arrive
            full_response_content += chunk
        print() # Newline after stream finishes
    LOGGER.info("Chat stream finished.")
    return full_response_content

def perform_cleanup():
    """Performs cleanup using AgentBuilder."""
    LOGGER.warning("Performing FULL CLEANUP using AgentBuilder.cleanup(). This will delete ALL agents, threads, etc.")
    LOGGER.warning("Ensure this is the intended action, especially in a non-test environment.")
    try:
        # Ensure config is loaded if AgentBuilder relies on it implicitly
        _ = Config.config() 
        builder = AgentBuilder.builder()
        builder.cleanup()
        LOGGER.info("Cleanup successful.")
    except Exception as e:
        LOGGER.error(f"Error during cleanup: {e}", exc_info=True)

# --- Main Execution ---
def main_flow():
    LOGGER.info("Starting REST API Flow Demo Script...")

    # 1. Authenticate (Generate JWT Token)
    LOGGER.info(f"Generating JWT for user: {TEST_USER_EMAIL}")
    token_data = {"sub": TEST_USER_EMAIL}
    access_token = create_access_token(data=token_data)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    LOGGER.info("JWT generated successfully.")

    agent_id = None
    thread_id = None

    try:
        with httpx.Client() as client:
            # 2. Create an Agent
            agent_definition_payload = {
                "name": "DemoFlowAgent",
                "description": "An agent created by the REST API flow demo script.",
                "instructions": "You are a helpful demo assistant. Respond concisely.",
                "tools": [{"type": "code_interpreter"}], # Example tool
                # "tool_resources": {}, # Optional
                # "metadata": {} # Optional
            }
            created_agent = create_agent(client, auth_headers, agent_definition_payload["name"], agent_definition_payload)
            agent_id = created_agent["agent_id"]

            # 3. Create a Thread
            created_thread = create_thread(client, auth_headers, thread_name="Demo Flow Thread")
            thread_id = created_thread["id"]

            # 4. Chat with the Agent
            sample_prompt = "Hello, Agent! What can you do?"
            chat_with_agent(client, auth_headers, thread_id, agent_id, sample_prompt)
            
            another_prompt = "Can you write a haiku about Python programming?"
            chat_with_agent(client, auth_headers, thread_id, agent_id, another_prompt)


    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP error occurred: {e.request.method} {e.request.url} - Status {e.response.status_code}")
        try:
            # Attempt to read the response text, useful for non-streaming error responses
            error_body = e.response.read().decode()
            LOGGER.error(f"Error response body: {error_body}")
        except httpx.ResponseNotRead:
            LOGGER.error("Could not read error response body because it was a streaming response or already read.")
        except Exception as read_err:
            LOGGER.error(f"Could not read error response body: {read_err}")
    except Exception as e:
        LOGGER.error(f"An unexpected error occurred during API interaction: {e}", exc_info=True)
    finally:
        # 5. Cleanup
        # WARNING: This deletes ALL agents and threads known to the system via metadata.
        # Consider if this is appropriate for your use case.
        # If you only want to delete the specific agent/thread created in *this* script,
        # you would need to implement targeted deletion API calls or methods.
        LOGGER.info("Proceeding to cleanup phase...")
        perform_cleanup()

    LOGGER.info("REST API Flow Demo Script finished.")

if __name__ == "__main__":
    main_flow()
