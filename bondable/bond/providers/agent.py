from abc import ABC, abstractmethod
from bondable.bond.definition import AgentDefinition
from bondable.bond.broker import Broker
from bondable.bond.providers.metadata import Metadata, AgentRecord, AgentGroup, GroupUser, VectorStore
from typing import List, Dict, Optional, Generator
import logging
import uuid
LOGGER = logging.getLogger(__name__)




class Agent(ABC):

    def __init__(self):
        """
        Initializes the Agent with a broker instance.

        Args:
            broker: The broker instance used for message publishing.
        """
        self.broker = Broker.broker()

    @abstractmethod
    def get_agent_id(self) -> str:
        """
        Returns the unique identifier of the agent.
        """
        pass

    @abstractmethod
    def get_agent_definition(self) -> AgentDefinition:
        """
        Returns the agent definition associated with this agent.
        This method should be implemented by subclasses.
        Returns:
            AgentDefinition: The agent definition object.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the name of the agent.
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Returns the description of the agent.
        """
        pass

    @abstractmethod
    def get_metadata_value(self, key, default_value=None):
        """
        Retrieves a metadata value by its key.

        Args:
            key (str): The key of the metadata value to retrieve.
            default_value: The default value to return if the key does not exist.

        Returns:
            The value associated with the given key, or the default value if the key does not exist.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, str]:
        """
        Returns the metadata associated with the agent.

        Returns:
            Dict[str, str]: A dictionary containing metadata key-value pairs.
        """
        pass

    @abstractmethod
    def create_user_message(self, prompt, thread_id, attachments=None, override_role="user") -> str:
        """
        Creates a user message for the agent based on the provided prompt and thread ID.
        This method should be implemented by subclasses.

        Args:
            prompt (str): The prompt to send to the agent.
            thread_id (str): The ID of the thread to which the message belongs.
            attachments (Optional[List[str]]): List of file IDs to attach to the message.
            override_role (str): Role to override the default role for the message.

        Returns:
            str: The ID of the created message.
        """
        pass

    @abstractmethod
    def stream_response(self, prompt=None, thread_id=None, attachments=None, override_role="user") -> Generator[str, None, None]:
        """
        Streams the response from the agent based on the provided prompt and thread ID.
        This method should be implemented by subclasses.
        Args:
            prompt (Optional[str]): The prompt to send to the agent.
            thread_id (Optional[str]): The ID of the thread to which the message belongs.
            attachments (Optional[List[str]]): List of file IDs to attach to the message.
            override_role (str): The role to use for the message (default: "user").
        Yields:
            str: The streamed response from the agent.
        """
        pass

    def broadcast_message(self, prompt, thread_id, attachments=None, override_role="user") -> str:
        msg_id = self.create_user_message(prompt=prompt, thread_id=thread_id, attachments=attachments, override_role=override_role)
        LOGGER.debug(f"Broadcasting new message: {prompt}")
        self.broker.publish(thread_id=thread_id, message=f"<_bondmessage id=\"{msg_id}\" role=\"{override_role}\" type=\"text\" thread_id=\"{thread_id}\" is_done=\"false\">")
        self.broker.publish(thread_id=thread_id, message=prompt)
        self.broker.publish(thread_id=thread_id, message="</_bondmessage>")
        return msg_id

    def broadcast_response(self, prompt=None, thread_id=None, attachments=None) -> bool:
        try:
            for content in self.stream_response(prompt=prompt, thread_id=thread_id, attachments=attachments):
                LOGGER.debug(f"Broadcasting content: {content}")
                self.broker.publish(thread_id=thread_id, message=content)
            return True
        except Exception as e:
            LOGGER.exception(f"Error handling response: {str(e)}")
            return False


class AgentProvider(ABC):
    """
    Abstract base class for agent providers.
    This class should be extended by any specific agent provider implementation.
    """

    metadata: Metadata = None

    def __init__(self, metadata: Metadata):
        """
        Initializes with a Metadata instance.
        Subclasses should call this constructor with their specific Metadata instance.
        """
        self.metadata = metadata

    @abstractmethod
    def delete_agent_resource(self, agent_id: str) -> bool:
        """
        Deletes an agent by its ID. This method should be implemented by subclasses.
        Don't throw an exception if it does not exist, just return False.
        """
        pass

    @abstractmethod
    def create_or_update_agent_resource(self, agent_def: AgentDefinition, owner_user_id: str) -> Agent:
        """
        Creates or updates an agent resource based on the provided agent definition.

        Args:
            user_id (str): The ID of the user creating or updating the agent.
            agent_def (AgentDefinition): The definition of the agent to be created or updated.

        Returns:
            Agent: The created or updated agent object.
        """
        pass

    @abstractmethod
    def get_agent(self, agent_id) -> Agent:
        """
        Retrieve a specific agent by its ID.

        Args:
            agent_id (str): The ID of the agent to retrieve.

        Returns:
            Agent: The agent object associated with the given ID.
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[Dict[str, any]]:
        """
        Get a list of available models that can be used by agents.

        Returns:
            List[Dict[str, any]]: A list of dictionaries containing model information.
                Each dictionary should have the following keys:
                - 'name' (str): The model identifier/name
                - 'description' (str): A human-readable description of the model
                - 'is_default' (bool): Whether this is the default model
        """
        pass

    def get_default_model(self) -> str:
        """
        Get the default model from available models.

        Returns:
            str: The name/identifier of the default model
        """
        models = self.get_available_models()
        for model in models:
            if model.get('is_default', False):
                return model['name']
        # If no default is set, return the first model
        if models:
            return models[0]['name']

        raise RuntimeError("No models were found. Cannot get default model.")


    def delete_agent(self, agent_id: str) -> bool:
        """
        Deletes an agent and its associated resources (like default vector store).
        """
        # First, try to find and delete the default vector store for this agent
        # Collect vector store IDs first, then delete outside the session to avoid
        # DetachedInstanceError when delete_vector_store opens its own session
        vector_store_ids_to_delete = []
        try:
            with self.metadata.get_db_session() as session:
                # Find vector stores that are default for this agent
                default_vector_stores = session.query(VectorStore).filter(
                    VectorStore.default_for_agent_id == agent_id
                ).all()
                # Extract IDs while session is still open
                vector_store_ids_to_delete = [vs.vector_store_id for vs in default_vector_stores]
        except Exception as e:
            LOGGER.error(f"Error finding default vector stores for agent {agent_id}: {e}")

        # Now delete the vector stores outside the session
        for vector_store_id in vector_store_ids_to_delete:
            try:
                from bondable.bond.config import Config
                provider = Config.config().get_provider()
                if hasattr(provider, 'vectorstores'):
                    provider.vectorstores.delete_vector_store(vector_store_id)
                    LOGGER.info(f"Deleted default vector store {vector_store_id} for agent {agent_id}")
            except Exception as e:
                LOGGER.error(f"Error deleting vector store {vector_store_id}: {e}")

        # Delete the agent resource
        deleted_resource = self.delete_agent_resource(agent_id)

        # Delete the agent record from the database
        with self.metadata.get_db_session() as session:
            try:
                # First, clean up agent-group relationships
                agent_group_deleted = session.query(AgentGroup).filter(
                    AgentGroup.agent_id == agent_id
                ).delete()
                LOGGER.debug(f"Deleted {agent_group_deleted} agent-group relationships for agent {agent_id}")

                # Clean up Bedrock-specific agent options if they exist
                try:
                    # Import here to avoid circular imports and handle cases where Bedrock isn't available
                    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockAgentOptions
                    bedrock_options_deleted = session.query(BedrockAgentOptions).filter(
                        BedrockAgentOptions.agent_id == agent_id
                    ).delete()
                    LOGGER.debug(f"Deleted {bedrock_options_deleted} Bedrock agent options for agent {agent_id}")
                except ImportError:
                    LOGGER.debug(f"Bedrock metadata not available, skipping Bedrock agent options cleanup for {agent_id}")
                except Exception as e:
                    LOGGER.warning(f"Error cleaning up Bedrock agent options for {agent_id}: {e}")

                # Now delete the agent record (safe from FK constraints)
                deleted_rows_count = session.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).delete()
                session.commit()
                if deleted_rows_count > 0:
                    LOGGER.info(f"Deleted {deleted_rows_count} local DB records for agent_id: {agent_id}")
                else:
                    LOGGER.info(f"No local DB records found for agent_id: {agent_id}")
                return True
            except Exception as e:
                LOGGER.error(f"Error deleting agent records from DB for agent_id {agent_id}: {e}", exc_info=True)
                raise

    def delete_agents_for_user(self, user_id: str) -> None:
        # query all agents owned by the user
        with self.metadata.get_db_session() as session:
            LOGGER.info(f"Cleaning up resources for user_id: {user_id}")
            for agent_id_tuple in session.query(AgentRecord.agent_id).filter(AgentRecord.owner_user_id == user_id).all():
                agent_id = agent_id_tuple[0]
                try:
                    deleted = self.delete_agent(agent_id)
                    LOGGER.info(f"Deleted agent with agent_id: {agent_id} - Success: {deleted}")
                except Exception as e:
                    LOGGER.error(f"Error deleting agent with agent_id: {agent_id}. Error: {e}")


    def create_or_update_agent(self, agent_def: AgentDefinition, user_id: str) -> Agent:
        agent: Agent = self.create_or_update_agent_resource(agent_def=agent_def, owner_user_id=user_id)
        with self.metadata.get_db_session() as session:
            # check to see if the agent already exists in the metadata
            agent_record: AgentRecord = session.query(AgentRecord).filter(AgentRecord.agent_id == agent.get_agent_id()).first()
            if agent_record:
                # if it exists, update the name, introduction, reminder and owner_user_id if necessary
                LOGGER.info(f"Agent record already exists for agent_id: {agent.get_agent_id()}")

                # Define fields to check and update
                fields_to_check = ['name', 'introduction', 'reminder', 'tool_resources', 'model']
                needs_update = False

                # Check each field for changes
                for field in fields_to_check:
                    old_value = getattr(agent_record, field, None)
                    new_value = getattr(agent_def, field, None)

                    if old_value != new_value:
                        needs_update = True
                        break

                if needs_update:
                    LOGGER.info(f"Updating agent record for agent_id: {agent.get_agent_id()}")
                    # Update all tracked fields
                    for field in fields_to_check:
                        setattr(agent_record, field, getattr(agent_def, field, None))
                    # Always update owner_user_id
                    agent_record.owner_user_id = user_id
                    session.commit()
                    LOGGER.info(f"Updated existing agent record for agent_id: {agent.get_agent_id()}")
            else:
                # if it does not exist, create a new record
                LOGGER.info(f"Creating new agent record for agent_id: {agent.get_agent_id()}")
                agent_record = AgentRecord(
                    name=agent.get_name(),
                    agent_id=agent.get_agent_id(),
                    owner_user_id=user_id,
                    introduction=agent_def.introduction,
                    reminder=agent_def.reminder,
                )
                session.add(agent_record)
                session.commit()

            # at this point we should have a valid agent record in the database with an agent_id
            # Update the default vector store for the agent (for both new and existing agents)
            # This ensures Bedrock agents get their vector stores linked properly
            LOGGER.info(f"Ensuring default vector store for agent {agent.get_name()} (ID: {agent.get_agent_id()})")
            LOGGER.info(f"Agent Definition Tool Resources: {agent_def.tool_resources}")

            if "file_search" in agent_def.tool_resources and agent_def.tool_resources["file_search"] is not None:
                file_search_vs_ids = agent_def.tool_resources["file_search"].get("vector_store_ids", [])
                if file_search_vs_ids:
                    vector_store_records = session.query(VectorStore).filter(VectorStore.vector_store_id.in_(file_search_vs_ids)).all()
                    for vector_store_record in vector_store_records:
                        if vector_store_record.name.startswith("default_vs_"):
                            # Check if this vector store is already linked to an agent
                            if vector_store_record.default_for_agent_id:
                                if vector_store_record.default_for_agent_id == agent.get_agent_id():
                                    # Already linked to this agent, nothing to do
                                    LOGGER.info(f"Vector store {vector_store_record.name} is already linked to agent {agent.get_name()}")
                                    continue
                                else:
                                    # Linked to a different agent - this is an error
                                    LOGGER.error(f"Vector store {vector_store_record.name} is already linked to a different agent: {vector_store_record.default_for_agent_id}")
                                    continue

                            # Link the vector store to this agent
                            vector_store_record.default_for_agent_id = agent.get_agent_id()
                            session.commit()
                            LOGGER.info(f"Updated vector store {vector_store_record.name} to be default for agent {agent.get_name()}")

        return agent


    def get_agent_record(self, agent_id: str) -> Optional[AgentRecord]:
        """Retrieve a specific agent record by its agent_id."""
        with self.metadata.get_db_session() as session:
            return session.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).first()

    def get_agent_records(self, user_id: str) -> List[Dict[str, str]]:
        with self.metadata.get_db_session() as session:
            agent_records = []

            # First, check for the default agent (Home)
            default_agent = session.query(AgentRecord).filter(AgentRecord.is_default == True).first()
            default_agent_id = None

            if default_agent:
                default_agent_id = default_agent.agent_id
                # Check if user owns the default agent
                is_owned = default_agent.owner_user_id == user_id
                agent_records.append({
                    "name": default_agent.name,
                    "agent_id": default_agent.agent_id,
                    "owned": is_owned
                })

            # Get the agent records that are owned by the user (excluding default if already added)
            query = session.query(AgentRecord).filter(AgentRecord.owner_user_id == user_id)
            if default_agent_id:
                query = query.filter(AgentRecord.agent_id != default_agent_id)
            results: List[AgentRecord] = query.all()

            owned_records = [
                {"name": record.name, "agent_id": record.agent_id, "owned": True} for record in results
            ]
            agent_records.extend(owned_records)

            # Get owned agent IDs to avoid duplicates (including default if owned)
            owned_agent_ids = {record.agent_id for record in results}
            if default_agent and default_agent.owner_user_id == user_id:
                owned_agent_ids.add(default_agent_id)

            # Get the agent records that are shared with the user via groups
            # exclude agents that the user already owns and the default agent
            shared_results: List[AgentRecord] = (
                session.query(AgentRecord)
                .join(AgentGroup, AgentRecord.agent_id == AgentGroup.agent_id)
                .join(GroupUser, AgentGroup.group_id == GroupUser.group_id)
                .filter(
                    GroupUser.user_id == user_id,
                    ~AgentRecord.agent_id.in_(owned_agent_ids)  # Exclude owned agents
                )
                .all()
            )

            # Filter out default agent from shared results if it exists
            if default_agent_id:
                shared_results = [agent for agent in shared_results if agent.agent_id != default_agent_id]

            shared_agent_records = [
                {"name": agent.name, "agent_id": agent.agent_id, "owned": False} for agent in shared_results
            ]
            agent_records.extend(shared_agent_records)

            return agent_records

    def list_agents(self, user_id) -> List[Agent]:
        agent_records = self.get_agent_records(user_id=user_id)
        agents = []
        for record in agent_records:
            agent: Agent = self.get_agent(agent_id=record['agent_id'])
            if agent:
                agents.append(agent)
        return agents


    def get_agents_by_name(self, agent_name: str) -> List[Agent]:
        with self.metadata.get_db_session() as session:
            try:
                agent_records = session.query(AgentRecord).filter(AgentRecord.name == agent_name).all()
                return [agent for record in agent_records if (agent := self.get_agent(agent_id=record.agent_id))]
            except Exception as e:
                LOGGER.error(f"Error retrieving agents by name '{agent_name}': {e}", exc_info=True)
                raise e


    def can_user_access_agent(self, user_id: str, agent_id: str) -> bool:
        """
        Validates if a user can access a given agent. The user can either be the owner of the agent
        or the agent could have been shared with the user via a group.
        """
        with self.metadata.get_db_session() as session:
            access_query = (
                session.query(AgentRecord)
                .outerjoin(AgentGroup, AgentRecord.agent_id == AgentGroup.agent_id)
                .outerjoin(GroupUser, AgentGroup.group_id == GroupUser.group_id)
                .filter(
                    (AgentRecord.owner_user_id == user_id) |
                    (GroupUser.user_id == user_id),
                    AgentRecord.agent_id == agent_id
                )
                .exists()
            )
            return session.query(access_query).scalar()

    def get_default_agent(self) -> Optional[Agent]:
        """
        Retrieves the default agent from the database.
        If no default agent exists, creates one automatically.

        Returns:
            Agent: The default agent object, or None if creation fails.
        """
        with self.metadata.get_db_session() as session:
            # First, try to find an existing default agent
            default_agent_record = session.query(AgentRecord).filter(
                AgentRecord.is_default == True
            ).first()

            if default_agent_record:
                try:
                    return self.get_agent(default_agent_record.agent_id)
                except Exception as e:
                    LOGGER.error(f"Error retrieving default agent with id {default_agent_record.agent_id}: {e}")
                    # Continue to create a new default if retrieval fails

            # No default agent exists, create one
            LOGGER.info("No default agent found, creating one...")

            # Get or create the system user
            system_user = self.metadata.get_or_create_system_user()

            # Create default agent definition with unique ID
            # default_agent_id = f"default_agent_{uuid.uuid4()}"
            default_agent_def = AgentDefinition(
                user_id=system_user.id,
                # id=default_agent_id,
                name="Home",
                description="Your AI assistant for various tasks",
                instructions="You are a helpful AI assistant. Help users with their questions and tasks.",
                introduction="Greet the user with a brief, friendly welcome. Keep it to 2-3 sentences. Do not mention your model name or creator. Simply let them know you're here to help and ask what they'd like to work on.",
                reminder="",
                model=self.get_default_model(),
                tools=[{"type": "code_interpreter"}, {"type": "file_search"}],  # Enable code interpreter and file search
                metadata={"is_default": "true"},
                temperature=0.7,
                top_p=0.9
            )

            try:
                # Use the existing create_or_update_agent method
                agent = self.create_or_update_agent(
                    agent_def=default_agent_def,
                    user_id=system_user.id
                )

                # Mark it as default in the database
                agent_record = session.query(AgentRecord).filter(
                    AgentRecord.agent_id == agent.get_agent_id()
                ).first()

                if agent_record:
                    agent_record.is_default = True
                    session.commit()
                    LOGGER.info(f"Created default agent with id: {agent.get_agent_id()}")
                    return agent
                else:
                    LOGGER.error("Failed to find default agent record in database after creation")
                    return None

            except Exception as e:
                LOGGER.error(f"Error creating default agent: {e}", exc_info=True)
                return None
