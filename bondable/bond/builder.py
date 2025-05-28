import logging
LOGGER = logging.getLogger(__name__)

import json
from bondable.bond.config import Config
from bondable.bond.agent import Agent
from bondable.bond.broker import Broker, BrokerConnectionEmpty
from bondable.bond.metadata import Metadata, AgentRecord
from bondable.bond.definition import AgentDefinition
from bondable.bond.cache import bond_cache
from IPython.display import Image, display
import threading
import base64



class AgentBuilder:

    # Using this class so that I dont need to set up and tear down assistants each time
    def __init__(self):
        self.metadata = Metadata.metadata()
        self.openai_client = Config.config().get_openai_client()
        self.context = {"agents": {}}
        # atexit.register(self.cleanup)
        LOGGER.info(f"Created AgentBuilder instance")

    @classmethod
    @bond_cache
    def builder(cls):
        return AgentBuilder()


    def cleanup(self):
        """This will delete all records and remove them from openai"""
        self.metadata.cleanup()

    def get_agent_id_by_name(self, name: str) -> str:
        """
        Retrieves the agent ID by name from the local metadata.
        If it does not exist it will return None. This is used primarily by notebooks
        to handle rerunning the same cell multiple times.
        """
        with self.metadata.get_db_session() as session:
            agent_record = session.query(AgentRecord).filter_by(name=name).first()
            if agent_record:
                return agent_record.assistant_id
            else:
                # not a warning if it does not exist
                LOGGER.debug(f"Agent with name '{name}' not found in local metadata.")
                return None

    def refresh_agent(self, agent_def: AgentDefinition, user_id: str) -> Agent:
        """
        Creates a new agent or updates an existing one.
        OpenAI is the source of truth for agent existence if an ID is provided.
        Handles local metadata synchronization.
        """
        openai_assistant_obj = None # Holds the final OpenAI assistant object

        with self.metadata.get_db_session() as session:
            if agent_def.id:  # ID is provided: implies update/refresh an existing agent
                LOGGER.info(f"Agent ID '{agent_def.id}' provided. Attempting to retrieve/update.")
                try:
                    # Retrieve from OpenAI first - this is the source of truth for existence by ID
                    openai_assistant_obj = self.openai_client.beta.assistants.retrieve(assistant_id=agent_def.id)
                    LOGGER.info(f"Retrieved OpenAI assistant with ID: {agent_def.id}")

                    # Check/Update local AgentRecord
                    agent_record_db = session.query(AgentRecord).filter_by(assistant_id=agent_def.id).first()
                    
                    # Determine the name to use for DB record and potential OpenAI update
                    # If agent_def.name is None, use the name from the retrieved OpenAI assistant
                    name_to_use = agent_def.name if agent_def.name is not None else openai_assistant_obj.name

                    if not agent_record_db:
                        LOGGER.warning(f"OpenAI Assistant ID {agent_def.id} exists but no local AgentRecord found. Creating one for user {user_id} with name '{name_to_use}'.")
                        self.metadata.create_agent_record(
                            name=name_to_use,
                            assistant_id=agent_def.id,
                            user_id=user_id  # Corrected parameter name
                        )
                    elif agent_record_db.name != name_to_use:
                        LOGGER.info(f"Updating local AgentRecord name for {agent_def.id} from '{agent_record_db.name}' to '{name_to_use}'.")
                        agent_record_db.name = name_to_use
                        session.commit()

                    # Compare definitions to see if OpenAI assistant needs an update
                    current_definition_from_openai = AgentDefinition.from_assistant(assistant_id=agent_def.id)
                    
                    # Construct the target definition for hash comparison
                    # Use the resolved 'name_to_use' and other fields from the input 'agent_def'
                    target_def_for_comparison = AgentDefinition(
                        id=agent_def.id, # Preserve ID for correct hash exclusion
                        name=name_to_use,
                        description=agent_def.description,
                        instructions=agent_def.instructions,
                        tools=agent_def.tools,
                        tool_resources=agent_def.tool_resources,
                        metadata=agent_def.metadata
                    )
                    # If model is specified in input, use it, otherwise use the existing one from OpenAI
                    target_def_for_comparison.model = agent_def.model if agent_def.model else current_definition_from_openai.model
                    
                    if current_definition_from_openai.get_hash() != target_def_for_comparison.get_hash():
                        LOGGER.info(f"Definition changed for agent ID {agent_def.id}. Updating OpenAI assistant.")
                        openai_assistant_obj = self.openai_client.beta.assistants.update(
                            assistant_id=agent_def.id,
                            name=name_to_use, # Use the resolved name
                            description=agent_def.description,
                            instructions=agent_def.instructions,
                            model=target_def_for_comparison.model,
                            tools=agent_def.tools,
                            tool_resources=agent_def.tool_resources,
                            metadata=agent_def.metadata
                        )
                        LOGGER.info(f"Successfully updated OpenAI assistant for ID: {agent_def.id}")
                    else:
                        LOGGER.info(f"No definition changes detected for agent ID {agent_def.id}. OpenAI assistant not updated.")

                except Exception as e: # Catches openai.NotFoundError and other issues
                    LOGGER.error(f"Error processing agent with ID {agent_def.id}: {e}", exc_info=True)
                    raise Exception(f"Failed to retrieve or update agent with ID {agent_def.id}. Original error: {str(e)}")

            else:  # No agent_def.id provided: this is a create new agent scenario
                if not agent_def.name:
                    raise ValueError("Agent name must be provided for creation.")
                LOGGER.info(f"No ID provided. Attempting to create new agent named '{agent_def.name}' for user '{user_id}'.")

                # Check for name uniqueness for this user in AgentRecord
                existing_agent_record_by_name = session.query(AgentRecord).filter_by(name=agent_def.name, owner_user_id=user_id).first()
                if existing_agent_record_by_name:
                    LOGGER.error(f"Agent with name '{agent_def.name}' already exists for user '{user_id}' (ID: {existing_agent_record_by_name.assistant_id}).")
                    raise Exception(f"Agent name '{agent_def.name}' already in use by you. Please choose a unique name.")

                LOGGER.info(f"Creating new OpenAI assistant: {agent_def.name}")
                openai_assistant_obj = self.openai_client.beta.assistants.create(
                    name=agent_def.name,
                    description=agent_def.description,
                    instructions=agent_def.instructions,
                    model=agent_def.model, # Uses default from AgentDefinition if not overridden
                    tools=agent_def.tools,
                    tool_resources=agent_def.tool_resources,
                    metadata=agent_def.metadata
                )
                agent_def.id = openai_assistant_obj.id # Update the input agent_def with the new ID
                
                self.metadata.create_agent_record(
                    name=agent_def.name,
                    assistant_id=agent_def.id,
                    user_id=user_id # Corrected parameter name
                )
                LOGGER.info(f"Successfully created new agent '{agent_def.name}' with ID '{agent_def.id}' for user '{user_id}'.")

        if not openai_assistant_obj:
            # This path should ideally not be hit if logic is correct.
            raise Exception("Critical error: OpenAI assistant object was not set after create/update logic.")

        final_agent_instance = Agent(assistant=openai_assistant_obj)
        self.context["agents"][final_agent_instance.get_name()] = final_agent_instance # Ensure context is updated
        return final_agent_instance

    def get_context(self):
        return self.context

    def display_message (self, message):
        if message.role == 'system':
            LOGGER.debug(f"Received system message, ignoring {message.message_id}")
            return
        if message.type == "text":
            print(f"[{message.message_id}/{message.role}] => {message.clob.get_content()}")
        elif message.type == "image_file":
            print(f"[{message.message_id}/{message.role}] => ")
            content = message.clob.get_content()
            if content.startswith('data:image/png;base64,'):
                base64_image = content[len('data:image/png;base64,'):]
                image_data = base64.b64decode(base64_image)
                display(Image(data=image_data))
            else:
                print(content)
        else:
            LOGGER.error(f"Unknown message type {type}")

    def print_responses (self, user_id, prompts, agent_def: AgentDefinition):
        # Create_thread now returns an ORM object, we need its ID.
        created_thread_orm = self.metadata.create_thread(user_id=user_id, name=f"PrintResponses for {agent_def.name}")
        thread_id = created_thread_orm.thread_id
        try:
            broker = Broker.broker()
            conn = broker.connect(thread_id=thread_id, subscriber_id=user_id)
            agent = self.refresh_agent(agent_def, user_id=user_id) # Call renamed method
            for prompt in prompts:
            
                message = agent.create_user_message(prompt, thread_id)
                thread = threading.Thread(target=agent.broadcast_response, args=(None, thread_id), daemon=True)
                thread.start()
                while True:
                    try:
                        bond_msg = conn.wait_for_message(timeout=5)
                        if bond_msg is None:
                            break
                        self.display_message(bond_msg)
                        if bond_msg.is_done:
                            break
                    except BrokerConnectionEmpty:
                        continue
                    except Exception as e:
                        LOGGER.error(f"Error: {e}")
                        break
                thread.join()

            conn.close()
        finally:
            self.metadata.delete_thread(thread_id)
