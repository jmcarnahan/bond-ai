from abc import ABC, abstractmethod
from bondable.bond.definition import AgentDefinition
from bondable.bond.broker import Broker
from bondable.bond.providers.metadata import Metadata, AgentRecord, AgentGroup, GroupUser
from typing import List, Dict, Optional, Generator
import logging
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
    def stream_response(self, prompt=None, thread_id=None, attachments=None) -> Generator[str, None, None]:
        """
        Streams the response from the agent based on the provided prompt and thread ID.
        This method should be implemented by subclasses.
        Args:
            prompt (Optional[str]): The prompt to send to the agent.
            thread_id (Optional[str]): The ID of the thread to which the message belongs.
            attachments (Optional[List[str]]): List of file IDs to attach to the message.
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
    def create_or_update_agent_resource(self, agent_def: AgentDefinition) -> Agent:
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

        
    def delete_agent(self, agent_id: str) -> bool:
        """
        Deletes a file from the configured backend file storage.
        """
        deleted_resource = self.delete_agent_resource(agent_id)
        with self.metadata.get_db_session() as session:
            try:
                deleted_rows_count = session.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).delete()
                session.commit()
                if deleted_rows_count > 0:
                    LOGGER.info(f"Deleted {deleted_rows_count} local DB records for agent_id: {agent_id}")
                else:
                    LOGGER.info(f"No local DB records found for agent_id: {agent_id}")
                return True 
            except Exception as e:
                LOGGER.error(f"Error deleting file records from DB for agent_id {agent_id}: {e}", exc_info=True)
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
        agent: Agent = self.create_or_update_agent_resource(agent_def=agent_def)
        with self.metadata.get_db_session() as session:
            # check to see if the agent already exists in the metadata
            agent_record: AgentRecord = session.query(AgentRecord).filter(AgentRecord.agent_id == agent.get_agent_id()).first()
            if agent_record:
                # if it exists, update the name and owner_user_id if necessary
                LOGGER.info(f"Agent record already exists for agent_id: {agent.get_agent_id()}")
                if agent_record.name != agent.get_name() or agent_record.owner_user_id != user_id:
                    agent_record.name = agent.get_name()
                    agent_record.owner_user_id = user_id
                    session.commit()
                    LOGGER.info(f"Updated existing agent record for agent_id: {agent.get_agent_id()}")
            else:
                # if it does not exist, create a new record
                LOGGER.info(f"Creating new agent record for agent_id: {agent.get_agent_id()}")
                agent_record = AgentRecord(name=agent.get_name(), agent_id=agent.get_agent_id(), owner_user_id=user_id)
                session.add(agent_record)
                session.commit()  
        return agent     


    def get_agent_records(self, user_id: str) -> List[Dict[str, str]]:
        with self.metadata.get_db_session() as session:
            # first get the agent records that are owwned by the user
            results: List[AgentRecord] = session.query(AgentRecord).filter(AgentRecord.owner_user_id == user_id).all()
            agent_records = [
                {"name": record.name, "agent_id": record.agent_id, "owned": True} for record in results
            ]

            # then get the agent records that are shared with the user via groups
            shared_results: List[AgentRecord] = (
                session.query(AgentRecord)
                .join(AgentGroup, AgentRecord.agent_id == AgentGroup.agent_id)
                .join(GroupUser, AgentGroup.group_id == GroupUser.group_id)
                .filter(GroupUser.user_id == user_id)
                .all()
            )
            shared_agent_records = [
                {"name": agent.name, "agent_id": agent.agent_id, "owned": False} for agent in shared_results
            ]

            # combine owned and shared agent records
            agent_records.extend(shared_agent_records)
            return agent_records
        
    def list_agents(self, user_id) -> List[Agent]:
        agent_records = self.get_agent_records(user_id=user_id)
        agents = []
        for record in agent_records:
            agent = self.get_agent(agent_id=record['agent_id'])
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

    def create_group(self, group_id: str, group_name: str, agent_id: str, user_ids: Optional[List[str]] = None) -> None:
        """
        Creates a group for sharing an agent and optionally associates users with the group.
        TODO: do something with the group name
        """
        with self.metadata.get_db_session() as session:
            # Create the group and associate it with the assistant
            agent_group = AgentGroup(agent_id=agent_id, group_id=group_id)
            session.add(agent_group)

            # Add users to the group if provided
            if user_ids:
                for user_id in user_ids:
                    group_user = GroupUser(group_id=group_id, user_id=user_id)
                    session.add(group_user)

            session.commit()
            LOGGER.info(f"Created group with group_id: {group_id} for agent_id: {agent_id}")

