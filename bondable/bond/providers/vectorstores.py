from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Tuple
from bondable.bond.providers.metadata import Metadata, VectorStore
from bondable.bond.providers.files import FilesProvider
import logging
LOGGER = logging.getLogger(__name__)

class VectorStoresProvider(ABC):

    metadata: Metadata = None

    def __init__(self, metadata: Metadata):
        """
        Initializes with a Metadata instance.
        Subclasses should call this constructor with their specific Metadata instance.
        """
        self.metadata = metadata

    @abstractmethod
    def get_files_provider(self) -> FilesProvider:
        """
        Returns the files provider instance used by this provider.
        Subclasses should implement this method.
        """
        pass

    @abstractmethod
    def delete_vector_store_resource(self, vector_store_id: str) -> bool:
        """
        Deletes a vector store by its ID. This method should be implemented by subclasses.
        Don't throw an exception if it does not exist, just return False.
        """
        pass


    @abstractmethod
    def create_vector_store_resource(self, name: str) -> str:
        """
        Creates a new vector store with the given name. This method should be implemented by subclasses.
        Returns the vector_store_id of the created vector store.
        """
        pass

    @abstractmethod
    def get_vector_store_file_ids(self, vector_store_id: str) -> List[str]:
        """
        Retrieves the file IDs associated with a vector store. This method should be implemented by subclasses.
        Returns a list of file IDs.
        """
        pass

    @abstractmethod
    def add_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """
        Adds a file to a vector store. This method should be implemented by subclasses.
        Returns True if the file was successfully added, False otherwise.
        """
        pass

    @abstractmethod
    def remove_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """
        Removes a file from a vector store. This method should be implemented by subclasses.
        Returns True if the file was successfully removed, False otherwise.
        """
        pass

    def get_or_create_vector_store_id(self, name: str, user_id, file_tuples: List[Tuple[str, Optional[bytes]]]) -> str:
        """
        Gets or creates a vector store ID based on the provided name and file tuples.
        Adds missing files and removes extra files from the vector store.
        """
        with self.metadata.get_db_session() as session:
            vector_store_record = session.query(VectorStore).filter_by(name=name, owner_user_id=user_id).first()
            if vector_store_record:
                LOGGER.debug(f"Reusing vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")
            else: 
                vector_store_id = self.create_vector_store_resource(name=name)
                vector_store_record = VectorStore(name=name, vector_store_id=vector_store_id, owner_user_id=user_id)
                session.add(vector_store_record)
                session.commit()
                LOGGER.info(f"Created new vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")

            vector_store_id = vector_store_record.vector_store_id
            vector_store_file_ids = self.get_vector_store_file_ids(vector_store_id=vector_store_id)

            for file_tuple in file_tuples:
                file_id = self.get_files_provider().get_or_create_file_id(user_id=user_id, file_tuple=file_tuple)
                if file_id not in vector_store_file_ids:
                    if self.add_vector_store_file(vector_store_id, file_id):
                        LOGGER.info(f"Created new vector store [{vector_store_id}] file record for file: {file_tuple[0]}")
                    else:
                        LOGGER.error(f"Error uploading file {file_id} to vector store {vector_store_id}")
                else:
                    vector_store_file_ids.remove(file_id)
                    LOGGER.debug(f"Reusing vector store [{vector_store_id}] file record for file: {file_tuple[0]}")
                    
            for file_id in vector_store_file_ids:
                removed = self.remove_vector_store_file(vector_store_id=vector_store_id, file_id=file_id)
                LOGGER.info(f"Deleted vector store [{vector_store_id}] file record for file: {file_id} - Success: {removed}")

            return vector_store_id
        
    def delete_vector_store(self, vector_store_id: str) -> bool:
        """
        Deletes a file from the configured backend file storage.
        TODO: delete files associated with this vector store as well.
        """
        deleted_resource = self.delete_vector_store_resource(vector_store_id=vector_store_id)
        with self.metadata.get_db_session() as session:
            try:
                deleted_rows_count = session.query(VectorStore).filter(VectorStore.vector_store_id == vector_store_id).delete()
                session.commit()
                if deleted_rows_count > 0:
                    LOGGER.info(f"Deleted {deleted_rows_count} local DB records for vector_store_id: {vector_store_id}")
                else:
                    LOGGER.info(f"No local DB records found for vector_store_id: {vector_store_id}")
                return True 
            except Exception as e:
                LOGGER.error(f"Error deleting file records from DB for vector_store_id {vector_store_id}: {e}", exc_info=True)
                raise 

    def delete_vector_stores_for_user(self, user_id: str) -> None:
        with self.metadata.get_db_session() as session:
            for vector_store_record in session.query(VectorStore).filter(VectorStore.owner_user_id == user_id).all():
                try:
                    deleted = self.delete_vector_store(vector_store_record.vector_store_id)
                    LOGGER.info(f"Deleted vector store with vector_store_id: {vector_store_record.vector_store_id} - Success: {deleted}")
                except Exception as e:
                    LOGGER.error(f"Error deleting vector store with vector_store_id: {vector_store_record.vector_store_id}. Error: {e}")

    def get_vector_store_file_paths(self, vector_store_ids: List[str]) -> List[Dict[str, str]]:
        """ Get the files associated with a vector store. """
        with self.metadata.get_db_session() as session:
            file_paths = []
            for vector_store_id in vector_store_ids:
                vector_store_file_ids = self.get_vector_store_file_ids(vector_store_id=vector_store_id)
                vs_file_paths = self.get_files_provider().get_file_paths(file_ids=vector_store_file_ids)
                for vs_file_path in vs_file_paths:
                    vs_file_path['vector_store_id'] = vector_store_id
                    file_paths.append(vs_file_path)
            return file_paths
    