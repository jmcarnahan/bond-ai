import logging
import os
import base64
import threading
import time
from typing import List, Dict, Any, Tuple, Optional

import pytest
import pandas as pd
from dotenv import load_dotenv

from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import Agent
from bondable.bond.broker import Broker, BrokerConnectionEmpty, BondMessage
from bondable.bond.definition import AgentDefinition
from bondable.bond.functions import Functions
from bondable.bond.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

load_dotenv(override=True)

@pytest.fixture(scope="session")
def user_id_session():
    return "pytest_user@example.com"

@pytest.fixture(scope="session")
def config_session():
    return Config.config()

@pytest.fixture(scope="session")
def builtin_functions_session():
    return Functions.functions()

@pytest.fixture(scope="function")
def provider_fixture(config_session, user_id_session):
    provider: Provider = config_session.get_provider()
    # Perform cleanup before each test function to ensure a clean slate
    LOGGER.info(f"Performing pre-test cleanup for user_id: {user_id_session}")
    provider.cleanup(user_id=user_id_session)
    return provider

def get_first_agent_id(provider: Provider, agent_name: str) -> Optional[str]:
    agents: List[Agent] = provider.agents.get_agents_by_name(agent_name)
    if agents:
        return agents[0].get_agent_id()
    return None

def run_agent_interaction_test(
    provider: Provider,
    user_id: str,
    agent_def: AgentDefinition,
    prompts: List[str],
    expected_min_responses: int = 1
) -> List[BondMessage]:
    """
    Helper function to run a standard agent interaction test.
    Creates/updates an agent, creates a thread, sends prompts, and collects responses.
    """
    agent = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=user_id)
    assert agent is not None, f"Failed to create/update agent: {agent_def.name}"
    assert agent.get_agent_id() is not None

    created_thread_record = provider.threads.create_thread(user_id=user_id, name=f"Test Thread for {agent.get_name()}")
    assert created_thread_record is not None
    thread_id = created_thread_record.thread_id
    assert thread_id is not None

    collected_messages: List[BondMessage] = []

    try:
        broker = Broker.broker()
        conn = broker.connect(thread_id=thread_id, subscriber_id=user_id)
        assert conn is not None, "Broker connection failed"

        for prompt_text in prompts:
            if prompt_text is None:
                continue

            agent.broadcast_message(prompt_text, thread_id)
            response_thread = threading.Thread(target=agent.broadcast_response, args=(None, thread_id), daemon=True)
            response_thread.start()

            prompt_messages_received = 0
            while True:
                try:
                    bond_msg = conn.wait_for_message(timeout=5)
                    if bond_msg is None:
                        break

                    if bond_msg.role != "user":
                        collected_messages.append(bond_msg)
                        prompt_messages_received += 1

                    if bond_msg.is_done:
                        break
                except BrokerConnectionEmpty:
                    continue
                except Exception as e:
                    LOGGER.error(f"Error waiting for message: {e}")
                    break

            response_thread.join()

            assert prompt_messages_received >= expected_min_responses, \
                f"Expected at least {expected_min_responses} response(s) for prompt '{prompt_text}', got {prompt_messages_received}"

    finally:
        if 'conn' in locals() and conn:
            conn.close()
        if thread_id:
            provider.threads.delete_thread(thread_id=thread_id, user_id=user_id)
            LOGGER.info(f"Deleted thread: {thread_id}")

    return collected_messages


def test_simple_agent(provider_fixture, user_id_session):
    agent_def = AgentDefinition(
        name="Test Simple Agent",
        id=get_first_agent_id(provider_fixture, "Test Simple Agent"),
        description="Pirate Agent for testing.",
        instructions="Answer requests from user like a pirate. Be very brief.",
        model="gpt-4.1-nano",
        metadata={'visible': 'True'},
        tools=[{"type": "code_interpreter"}], # Added CI as per notebook, though not strictly used by pirate
        user_id=user_id_session
    )
    responses = run_agent_interaction_test(
        provider=provider_fixture,
        user_id=user_id_session,
        agent_def=agent_def,
        prompts=['tell me a joke'],
        expected_min_responses=1
    )
    assert len(responses) >= 1
    # Basic check, could be more specific if pirate responses are consistent
    assert any("arrr" in r.clob.get_content().lower() or "matey" in r.clob.get_content().lower() for r in responses if r.type == "text"), \
           "Pirate agent response did not seem pirate-y enough."


def test_function_agent(provider_fixture, user_id_session, builtin_functions_session, caplog):
    agent_def = AgentDefinition(
        name="Test Function Agent",
        id=get_first_agent_id(provider_fixture, "Test Function Agent"),
        description="Say hello to the user via function.",
        instructions="Call the simple method 'hello' with the name provided by the user. If no name is provided, ask the user to provide a name.",
        metadata={'visible': 'True'},
        tools=[builtin_functions_session.hello],
        model="gpt-4.1-nano",
        user_id=user_id_session
    )
    responses = run_agent_interaction_test(
        provider=provider_fixture,
        user_id=user_id_session,
        agent_def=agent_def,
        prompts=['my name is testuser'],
        expected_min_responses=1 # Expecting at least one response, possibly tool call + final answer
    )
    assert len(responses) >= 1
    # Check if the function execution was logged
    log_records = [record for record in caplog.get_records('call') if record.name == 'bondable.bond.functions' and "Saying hello to: testuser" in record.message]
    assert len(log_records) >= 1, "The 'hello' function call with 'testuser' was not logged."


def test_synth_agent_code_interpreter(provider_fixture, user_id_session, caplog):
    # TODO: Fix vector store configuration issue - getting "array too long" error for vector_store_ids
    # Error: Expected an array with maximum length 1, but got an array with length 2 instead
    agent_def = AgentDefinition(
        name="Test Synth Agent",
        id=get_first_agent_id(provider_fixture, "Test Synth Agent"),
        description="An agent that will load synthetic data about people and answer questions",
        instructions="When you begin you should create a synthetic data set that has the weight and height of 100 people. You should answer questions about the data set.",
        tools=[{"type": "code_interpreter"}],
        metadata={'visible': 'True', 'initial_prompt': 'Generate the data set of 100 people and confirm.'},
        model="gpt-4.1-nano",
        user_id=user_id_session
    )

    initial_prompt = agent_def.metadata.get('initial_prompt')
    prompts = [
        initial_prompt,
        "How many people are there in the dataset?",
        "What is the average height? (Provide just the number)"
    ]

    responses = run_agent_interaction_test(
        provider=provider_fixture,
        user_id=user_id_session,
        agent_def=agent_def,
        prompts=prompts,
        expected_min_responses=1 # Each prompt should get at least one response
    )
    assert len(responses) >= len(prompts)

    # For now, let's simplify and check the first response block for the initial prompt's expected output
    # This relies on the order of prompts and responses being maintained.
    # We'll check responses that are not from the 'user' role.

    # Get the message_id of the user's initial prompt message
    # This requires modifying run_agent_interaction_test or how agent.broadcast_message is called and its return captured.
    # For now, let's assume the first block of non-user responses is for the first prompt.

    # Find the responses related to the first prompt (initial_prompt)
    # This is tricky without direct prompt-response linking in collected_messages.
    # We'll assume the first batch of assistant messages are for the first prompt.
    # A better way would be to enhance run_agent_interaction_test to return (prompt, responses_for_prompt) tuples.

    # Simplified check: look for the confirmation in any text response.
    confirmed_generation = False
    for r in responses:
        if r.type == "text":
            content_lower = r.clob.get_content().lower()
            if "100 people" in content_lower or "dataset generated" in content_lower or "confirmed" in content_lower:
                confirmed_generation = True
                break
    assert confirmed_generation, "Synth agent did not confirm dataset generation from initial prompt."

    # Check for response to "How many people"
    answered_how_many = False
    for r in responses:
        if r.type == "text":
            if "100" in r.clob.get_content() and "people" in prompts[1].lower(): # Check if response is to the right question
                 # This is still a bit loose. A better check would involve inspecting messages associated with the second prompt.
                answered_how_many = True
                break
    assert answered_how_many, "Synth agent did not correctly answer how many people."


def test_file_agent_csv_code_interpreter(provider_fixture, user_id_session, tmp_path):
    data = {
        'Customer_ID': [1, 2, 3], 'First_Name': ['Jack', 'Jane', 'Doe'],
        'Last_Name': ['Doe', 'Smith', 'Johnson'], 'Email': ['jack.doe@example.com', 'jane.smith@example.com', 'doe.johnson@example.com']
    }
    df = pd.DataFrame(data)
    data_file_path = tmp_path / "test_customers.csv"
    df.to_csv(data_file_path, index=False)

    initial_prompt = "What are all of the customer first names from the CSV?"
    agent_def = AgentDefinition(
        name="Test CSV File Agent",
        id=get_first_agent_id(provider_fixture, "Test CSV File Agent"),
        description="Agent to test CSV reading with Code Interpreter.",
        instructions="Answer questions about user data in the attached CSV file. The first row contains column names.",
        tools=[{"type": "code_interpreter"}],
        tool_resources={"code_interpreter": {"files": [(str(data_file_path), None)]}},
        metadata={'visible': 'True', 'initial_prompt': initial_prompt},
        model="gpt-4.1-nano",
        user_id=user_id_session
    )
    responses = run_agent_interaction_test(
        provider=provider_fixture,
        user_id=user_id_session,
        agent_def=agent_def,
        prompts=[initial_prompt],
        expected_min_responses=1
    )
    assert len(responses) >= 1
    text_responses = [r.clob.get_content().lower() for r in responses if r.type == "text"]
    assert any("jack" in tr and "jane" in tr and "doe" in tr for tr in text_responses), \
           "CSV File agent did not seem to list customer names."


def test_file_agent_html_file_search(provider_fixture, user_id_session, tmp_path):
    data = {
        'Product_ID': [101, 102, 103], 'Product_Name': ['Laptop', 'Mouse', 'Keyboard'],
        'Category': ['Electronics', 'Accessories', 'Accessories']
    }
    df = pd.DataFrame(data)
    html_file_path = tmp_path / "test_products.html"
    df.to_html(html_file_path, index=False)

    initial_prompt = "List all product names from the HTML file."
    agent_def = AgentDefinition(
        name="Test HTML File Agent",
        id=get_first_agent_id(provider_fixture, "Test HTML File Agent"),
        description="Agent to test HTML reading with File Search.",
        instructions="Answer questions about user data in the attached HTML file.",
        tools=[{"type": "file_search"}], # Changed from code_interpreter to file_search as per notebook
        tool_resources={"file_search": {"files": [(str(html_file_path), None)]}},
        metadata={'visible': 'True', 'initial_prompt': initial_prompt},
        model="gpt-4.1-nano", # Ensure model supports file_search or is general purpose
        user_id=user_id_session
    )
    responses = run_agent_interaction_test(
        provider=provider_fixture,
        user_id=user_id_session,
        agent_def=agent_def,
        prompts=[initial_prompt],
        expected_min_responses=1
    )
    assert len(responses) >= 1
    text_responses = [r.clob.get_content().lower() for r in responses if r.type == "text"]
    assert any("laptop" in tr and "mouse" in tr and "keyboard" in tr for tr in text_responses), \
           "HTML File agent did not seem to list product names."
