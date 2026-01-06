from bondable.bond.providers.vectorstores import VectorStoresProvider
from bondable.bond.providers.metadata import Metadata
from bondable.bond.providers.files import FilesProvider
from bondable.bond.config import Config
from bondable.bond.cache import bond_cache
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from bondable.bond.providers.openai.OAIAFiles import OAIAFilesProvider
import openai
import time
import logging
from typing_extensions import override
from typing import Any, Dict, Optional, List

LOGGER = logging.getLogger(__name__)

MAX_LIMIT = 100
class OAIAVectorStoresProvider(VectorStoresProvider):

    def __init__(self, openai_client, metadata, files):
        super().__init__(metadata=metadata)
        self.openai_client = openai_client
        self.files = files

    # @classmethod
    # @bond_cache
    # def provider(cls) -> VectorStoresProvider:
    #     return OAIAVectorStoresProvider()

    def get_files_provider(self) -> FilesProvider:
        return self.files

    @override
    def delete_vector_store_resource(self, vector_store_id: str) -> bool:
        """
        Deletes a vector store by its ID.
        Don't throw an exception if it does not exist, just return False.
        """
        try:
            self.openai_client.vector_stores.delete(vector_store_id)
            LOGGER.info(f"Deleting vector store with vector_store_id: {vector_store_id}")
            return True
        except openai.NotFoundError:
            LOGGER.warning(f"Vector store with vector_store_id: {vector_store_id} not found. Considered 'deleted' for provider part.")
            return False
        except Exception as e:
            LOGGER.error(f"Error deleting vector store with vector_store_id: {vector_store_id}. Error: {e}")
            raise e

    @override
    def create_vector_store_resource(self, name: str) -> str:
        """
        Creates a new vector store with the given name.
        Returns the vector_store_id of the created vector store.
        """
        try:
            vector_store = self.openai_client.vector_stores.create(name=name)
            return vector_store.id
        except Exception as e:
            LOGGER.error(f"Error creating vector store with name {name}. Error: {e}")
            raise e

    @override
    def get_vector_store_file_ids(self, vector_store_id: str) -> List[str]:
        """
        Retrieves the file IDs associated with a vector store.
        Returns a list of file IDs.
        """
        vector_store_files = self.openai_client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=MAX_LIMIT
        )
        vector_store_file_ids = [record['id'] for record in vector_store_files.to_dict()['data']]
        return vector_store_file_ids

    @override
    def add_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """
        Adds a file to a vector store.
        Returns True if the file was successfully added, False otherwise.
        """
        # need to check if the file exists in the vector store first
        vector_store_files = self.get_vector_store_file_ids(vector_store_id)
        if file_id in vector_store_files:
            LOGGER.info(f"File {file_id} already exists in vector store {vector_store_id}. No action taken.")
            return True

        vector_store_file = self.openai_client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        while vector_store_file.status == "in_progress":
            time.sleep(1)
        if vector_store_file.status == "completed":
            LOGGER.info(f"Added vector store [{vector_store_id}] file record for file: {file_id}")
            return True
        else:
            LOGGER.error(f"Failed to add vector store [{vector_store_id}] file record for file: {file_id}. Status: {vector_store_file.status}")
            raise Exception(f"Failed to add file to vector store. Status: {vector_store_file.status}")


    @override
    def remove_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """
        Removes a file from a vector store.
        Returns True if the file was successfully removed, False otherwise.
        """
        try:
            self.openai_client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
            LOGGER.info(f"Deleted vector store [{vector_store_id}] file record for file: {file_id}")
            return True
        except Exception as e:
            LOGGER.error(f"Error deleting vector store [{vector_store_id}] file record for file: {file_id}. Error: {e}")
            raise e
