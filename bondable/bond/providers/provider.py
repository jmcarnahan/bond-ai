from abc import ABC, abstractmethod
from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.vectorstores import VectorStoresProvider
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.agent import AgentProvider
from bondable.bond.groups import Groups
from bondable.bond.users import Users
import logging
LOGGER = logging.getLogger(__name__)

class Provider(ABC):

    files: FilesProvider = None
    vectorstores: VectorStoresProvider = None
    threads: ThreadsProvider = None
    agents: AgentProvider = None
    groups: Groups = None
    users: Users = None

    def get_default_model(self) -> str:
        """
        Returns the default model for the provider.
        Delegates to the agents provider for backward compatibility.
        """
        if not self.agents:
            raise RuntimeError("AgentProvider not initialized. Cannot get default model.")
        return self.agents.get_default_model()


    def cleanup(self, user_id) -> None:
        # query all agents owned by the user
        LOGGER.info(f"Cleaning up resources for user_id: {user_id}")
        self.agents.delete_agents_for_user(user_id)
        self.threads.delete_threads_for_user(user_id)
        self.files.delete_files_for_user(user_id)
        self.vectorstores.delete_vector_stores_for_user(user_id)



