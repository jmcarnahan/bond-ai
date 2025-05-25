from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, event, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.sql import text
import os
import io
import logging
from bondable.bond.cache import bond_cache
from bondable.bond.config import Config
import datetime
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
import openai # For exception handling like openai.NotFoundError


LOGGER = logging.getLogger(__name__)

Base = declarative_base()
class Thread(Base):
    __tablename__ = 'threads'
    thread_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    name = Column(String, default="New Thread")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (PrimaryKeyConstraint('thread_id', 'user_id'),)
class AgentRecord(Base):
    __tablename__ = "agents"
    assistant_id = Column(String, primary_key=True) # Changed to primary key
    name = Column(String, nullable=False) # No longer primary key, but still required
    owner_user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    # Consider adding a UniqueConstraint('name', 'owner_user_id', name='uq_agent_name_owner') if names should be unique per user
class FileRecord(Base):
    __tablename__ = "files"
    file_path = Column(String, primary_key=True)
    file_hash = Column(String, nullable=False)
    file_id = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)
class VectorStore(Base):
    __tablename__ = "vector_stores"
    name = Column(String, primary_key=True)
    vector_store_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
class AgentGroup(Base):
    __tablename__ = "agent_groups"
    assistant_id = Column(String, primary_key=True)
    group_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class GroupUser(Base):
    __tablename__ = "group_users"
    group_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)


MAX_FILE_LIMIT = 100
class Metadata:

    def __init__(self):
        self.config = Config.config()
        # TODO: get this from config
        self.metadata_db_url = os.getenv('METADATA_DB_URL', 'sqlite:////tmp/.metadata.db')
        self.engine = create_engine(self.metadata_db_url, echo=False)
        Base.metadata.create_all(self.engine) 
        self.session = scoped_session(sessionmaker(bind=self.engine))
        self.openai_client = Config.config().get_openai_client()
        LOGGER.info(f"Created Metadata instance using database engine: {self.metadata_db_url}")

    @classmethod
    @bond_cache
    def metadata(cls):
        return Metadata()

    def get_db_session(self) -> scoped_session:
        if not self.engine:
            self.engine = create_engine(self.metadata_db_url, echo=False)
            Base.metadata.create_all(self.engine)
            self.session = scoped_session(sessionmaker(bind=self.engine))
            LOGGER.info(f"Re-created Metadata instance using database engine: {self.metadata_db_url}")
        return self.session()

    def close_db_engine(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None
            LOGGER.info(f"Closed database engine")

    def cleanup(self):
        session = self.get_db_session()

        try:
            for assistant_id_tuple in session.query(AgentRecord.assistant_id).all():
                assistant_id = assistant_id_tuple[0]
                try:
                    self.openai_client.beta.assistants.delete(assistant_id)
                    LOGGER.info(f"Deleting assistant with assistant_id: {assistant_id}")
                except Exception as e:
                    LOGGER.error(f"Error deleting assistant with assistant_id: {assistant_id}. Error: {e}")
            session.query(AgentRecord).delete()
            session.commit()

            for thread_id_tuple in session.query(Thread.thread_id).all():
                thread_id = thread_id_tuple[0]
                try:
                    self.openai_client.beta.threads.delete(thread_id)
                    LOGGER.info(f"Deleting thread with thread_id: {thread_id}")
                except Exception as e:
                    LOGGER.error(f"Error deleting thread with thread_id: {thread_id}. Error: {e}")
            session.query(Thread).delete()
            session.commit()

            for file_record in session.query(FileRecord).all():
                if file_record.file_id is None:
                    continue
                try:
                    self.openai_client.files.delete(file_record.file_id)
                    LOGGER.info(f"Deleting file with file_id: {file_record.file_id}")
                except Exception as e:
                    LOGGER.error(f"Error deleting file with file_id: {file_record.file_id}. Error: {e}")
            session.query(FileRecord).delete()
            session.commit()

            for vector_store_record in session.query(VectorStore).all():
                try:
                    self.openai_client.vector_stores.delete(vector_store_record.vector_store_id)
                    LOGGER.info(f"Deleting vector store with vector_store_id: {vector_store_record.vector_store_id}")
                except Exception as e:
                    LOGGER.error(f"Error deleting vector store with vector_store_id: {vector_store_record.vector_store_id}. Error: {e}")
            session.query(VectorStore).delete()
            session.commit()

        # session.query(VectorStoreFileRecord).delete()
        # session.commit()

        finally:
            session.close()



    def close(self) -> None:
        self.close_db_engine()

    def create_thread(self, user_id: str, name: Optional[str] = None) -> Thread: # Return Thread object
        openai_thread = self.config.get_openai_client().beta.threads.create()
        # Pass the name to grant_thread, which will now return the Thread object
        return self.grant_thread(thread_id=openai_thread.id, user_id=user_id, name=name, fail_if_missing=False)

    def update_thread_name(self, thread_id: str, thread_name: str) -> None:
        with self.get_db_session() as session:  
            thread = session.query(Thread).filter_by(thread_id=thread_id).first()
            if thread:
                thread.name = thread_name  
                session.commit()  

    def get_current_threads(self, user_id: str, count: int = 10) -> list:
        with self.get_db_session() as session:  
            results = (session.query(Thread.thread_id, Thread.name, Thread.created_at, Thread.updated_at)
                        .filter_by(user_id=user_id).order_by(Thread.created_at.desc()).limit(count).all())
            threads = [
                {"thread_id": thread_id, "name": name, "created_at": created_at, "updated_at": updated_at}
                for thread_id, name, created_at, updated_at in results
            ]
            LOGGER.debug(f"Retrieved available threads: {len(threads)}")
            return threads


    def grant_thread(self, thread_id: str, user_id: str, name: Optional[str] = None, fail_if_missing: bool = False) -> Thread:
        with self.get_db_session() as session:
            if fail_if_missing:
                # Check if the thread_id exists for *any* user.
                # This confirms the thread is known to the system if we are trying to grant access to an existing thread.
                thread_exists_for_any_user = session.query(Thread).filter_by(thread_id=thread_id).first()
                if not thread_exists_for_any_user:
                    raise Exception(f"Thread {thread_id} not found in metadata. Cannot grant access when fail_if_missing is True.")

            # Attempt to get the specific user's access record for this thread.
            user_access_record = session.query(Thread).filter_by(thread_id=thread_id, user_id=user_id).first()

            if user_access_record:
                # User already has access.
                # If a new name is provided and it's different, update it.
                if name is not None and user_access_record.name != name:
                    user_access_record.name = name
                    session.commit()
                    session.refresh(user_access_record) # Ensure the returned object reflects the update.
                return user_access_record
            else:
                # User does not have access yet. Create a new access record.
                # The `name` will be used if provided; otherwise, the DB default ("New Thread") will apply.
                new_access_record = Thread(thread_id=thread_id, user_id=user_id, name=name)
                session.add(new_access_record)
                session.commit()
                session.refresh(new_access_record) # Load any DB-generated defaults.
                return new_access_record

    def delete_thread(self, thread_id: str) -> None:
        with self.get_db_session() as session:
            try:
                self.openai_client.beta.threads.delete(thread_id)
                LOGGER.info(f"Successfully deleted OpenAI thread: {thread_id}")
            except Exception as e:
                # Log the error but continue to delete local records
                LOGGER.warning(f"Failed to delete OpenAI thread {thread_id}: {e}. Proceeding with local DB record deletion.")
            
            # Delete all user associations for this thread_id from our DB
            deleted_rows = session.query(Thread).filter(Thread.thread_id == thread_id).delete()
            
            if deleted_rows > 0:
                try:
                    session.commit()
                    LOGGER.info(f"Successfully committed deletion of {deleted_rows} DB records for thread_id: {thread_id}")
                except Exception as e:
                    LOGGER.critical(f"CRITICAL: Failed to commit DB deletion for thread_id {thread_id} after {deleted_rows} rows were marked for deletion. Error: {e}", exc_info=True)
                    session.rollback() # Rollback the transaction
                    raise # Re-raise the exception to signal failure
            else:
                # This might happen if called multiple times for the same thread_id or if thread never existed in DB.
                # No commit needed if no rows were deleted.
                LOGGER.info(f"No DB records found to delete for thread_id: {thread_id} (possibly already deleted or never existed in DB).")

    def get_thread(self, thread_id: str) -> dict | None:
        with self.get_db_session() as session:
            results = session.query(Thread).filter(Thread.thread_id == thread_id).all()
            if results:
                first_row = results[0]  
                thread = {
                    "thread_id": first_row.thread_id,
                    "name": first_row.name,
                    "created_at": first_row.created_at, 
                    "updated_at": first_row.updated_at,
                    "users": [row.user_id for row in results]  
                }
                return thread
            return None
        
    def get_thread_owner(self, thread_id: str) -> Optional[str]:
        with self.get_db_session() as session:
            thread = session.query(Thread).filter(Thread.thread_id == thread_id).first()
            if thread:
                return thread.user_id
            return None

    def get_file_id(self, file_tuple: Tuple[str, Optional[bytes]]) -> str:
        """
        Ensures a file record exists in the database and uploads the file to OpenAI if not already present.
        Returns the FileRecord object.
        """

        file_path = file_tuple[0]
        file_bytes = file_tuple[1]
        if file_bytes is None:
            try:
                with open(file_path, "rb") as file:
                    file_bytes = file.read()
            except Exception as e:
                LOGGER.error(f"Error reading file {file_path}: {e}")
                raise e
            
        LOGGER.debug(f"Getting hash for file {file_path}:\n{file_bytes}\n\n")
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        with self.get_db_session() as session:
            file_record: FileRecord = session.query(FileRecord).filter(FileRecord.file_hash == file_hash).first()
            if file_record:
                if file_record.file_path == file_path:
                    LOGGER.info(f"File {file_path} (and hash) is same in the database. Reusing existing record.")
                    return file_record.file_id
                else:
                    # Hash matches, but path is different. This implies same content from a new source path.
                    # Create a new FileRecord for the new path, but reuse the OpenAI file_id from the record found by hash.
                    LOGGER.info(f"Content hash for '{file_path}' matches existing record '{file_record.file_path}' (file_id: {file_record.file_id}). Creating new path record with existing file_id.")
                    new_path_record = FileRecord(file_path=file_path, file_hash=file_hash, file_id=file_record.file_id)
                    session.add(new_path_record)
                    session.commit()
                    return new_path_record.file_id
            
            # If no record found by hash, or if specific logic above decided to proceed to upload:
            if not file_record: # This condition might be redundant now due to returns above, but keep for clarity of flow for new files
                # tuple of hash and path do not exist - need to create
                LOGGER.debug(f"Creating new file '{file_path}' to OpenAI.")
                file_id = None
                try:
                    openai_file = self.openai_client.files.create(
                        file=(file_path, io.BytesIO(file_bytes)),
                        purpose='assistants'
                    )
                    file_id = openai_file.id
                    LOGGER.info(f"Successfully uploaded '{file_path}' to OpenAI. File ID: {file_id}")
                except Exception as e:
                    LOGGER.error(f"Error uploading file '{file_path}' to OpenAI: {e}")
                    raise e

                file_record = FileRecord(file_path=file_path, file_hash=file_hash, file_id=file_id)
                session.add(file_record)
                session.commit()
                LOGGER.info(f"Created new file record for {file_path}")
                return file_record.file_id

    def delete_file(self, provider_file_id: str) -> bool:
        """
        Deletes a file from the configured backend file storage (e.g., OpenAI)
        and its corresponding record(s) from the local FileRecord database table.
        Returns True if the operation is successful (file deleted from provider or confirmed not found,
        and DB records deleted or confirmed not found). Raises an exception on critical failures.
        """
        try:
            self.openai_client.files.delete(provider_file_id)
            LOGGER.info(f"Successfully deleted file {provider_file_id} from provider.")
        except openai.NotFoundError: 
            LOGGER.warning(f"File {provider_file_id} not found on provider. Considered 'deleted' for provider part.")
        except Exception as e:
            LOGGER.error(f"Error deleting file {provider_file_id} from provider: {e}", exc_info=True)
            raise  # Re-raise if provider deletion fails critically

        # Proceed to delete from local DB
        with self.get_db_session() as session:
            try:
                # FileRecord.file_id stores the provider_file_id
                # Delete all local records associated with this provider_file_id
                deleted_rows_count = session.query(FileRecord).filter(FileRecord.file_id == provider_file_id).delete()
                session.commit()
                if deleted_rows_count > 0:
                    LOGGER.info(f"Deleted {deleted_rows_count} local DB records for provider_file_id: {provider_file_id}")
                else:
                    LOGGER.info(f"No local DB records found for provider_file_id: {provider_file_id}")
                return True # Operation considered successful
            except Exception as e:
                LOGGER.error(f"Error deleting file records from DB for provider_file_id {provider_file_id}: {e}", exc_info=True)
                raise # DB operation failure is critical

    def _get_vector_store_file_ids(self, vector_store_id: str) -> List[str]:
        """ Get the files associated with a vector store. """
        # TODO: Need to page through the files to get all file IDs
        vector_store_files = self.openai_client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=MAX_FILE_LIMIT
        )
        vector_store_file_ids = [record['id'] for record in vector_store_files.to_dict()['data']]
        return vector_store_file_ids

    def get_vector_store_id(self, name: str, file_tuples: Tuple[str, Optional[bytes]]) -> str:
        """
        Ensures an OpenAI Vector Store with the given name exists and contains exactly the specified file_ids.
        Adds missing files and removes extra files from the vector store.
        """
        with self.get_db_session() as session:
            vector_store_record = session.query(VectorStore).filter(VectorStore.name == name).first()
            if vector_store_record:
                LOGGER.debug(f"Reusing vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")
            else: 
                vector_store = self.openai_client.vector_stores.create(name=name)
                vector_store_record = VectorStore(name=name, vector_store_id=vector_store.id)
                session.add(vector_store_record)
                session.commit()
                LOGGER.info(f"Created new vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")

            vector_store_id = vector_store_record.vector_store_id
            vector_store_file_ids = self._get_vector_store_file_ids(vector_store_id=vector_store_id)

            for file_tuple in file_tuples:
                file_id = self.get_file_id(file_tuple=file_tuple)
                if file_id not in vector_store_file_ids:
                    if self.add_vector_store_file(vector_store_id, file_id):
                        LOGGER.info(f"Created new vector store [{vector_store_id}] file record for file: {file_tuple[0]}")
                    else:
                        LOGGER.error(f"Error uploading file {file_id} to vector store {vector_store_id}")
                else:
                    vector_store_file_ids.remove(file_id)
                    LOGGER.debug(f"Reusing vector store [{vector_store_id}] file record for file: {file_tuple[0]}")
                    
            for file_id in vector_store_file_ids:
                self.openai_client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
                LOGGER.info(f"Deleted vector store [{vector_store_id}] file record for file: {file_id}")

            return vector_store_id

    def add_vector_store_file(self, vector_store_id, file_id):
        """ Associate a file with a vector store and poll for completion. """
        vector_store_file = self.openai_client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        while vector_store_file.status == "in_progress":
            time.sleep(1)
        return vector_store_file.status == "completed"
  
    def get_file_paths(self, file_ids: List[str]) -> List[Dict[str, str]]:
        """ Get the file path from the file ID. """
        with self.get_db_session() as session:
            file_records = session.query(FileRecord).filter(FileRecord.file_id.in_(file_ids)).all()
            file_paths = []
            for file_record in file_records:
                file_paths.append({'file_id': file_record.file_id, 'file_path': file_record.file_path, 'vector_store_id': None})
            return file_paths
        
    def get_vector_store_file_paths(self, vector_store_ids: List[str]) -> List[Dict[str, str]]:
        """ Get the files associated with a vector store. """
        with self.get_db_session() as session:
            file_paths = []
            for vector_store_id in vector_store_ids:
                vector_store_file_ids = self._get_vector_store_file_ids(vector_store_id=vector_store_id)
                vs_file_paths = self.get_file_paths(file_ids=vector_store_file_ids)
                for vs_file_path in vs_file_paths:
                    vs_file_path['vector_store_id'] = vector_store_id
                    file_paths.append(vs_file_path)
            return file_paths

    def create_agent_record(self, name: str, assistant_id: str, user_id: str) -> None:
        with self.get_db_session() as session:
            agent_record = AgentRecord(name=name, assistant_id=assistant_id, owner_user_id=user_id)
            session.add(agent_record)
            session.commit()

    def get_agent_records(self, user_id: str) -> List[Dict[str, str]]:
        with self.get_db_session() as session:
            # first get the agent records that are owwned by the user
            results = session.query(AgentRecord).filter(AgentRecord.owner_user_id == user_id).all()
            agent_records = [
                {"name": record.name, "assistant_id": record.assistant_id, "owned": True} for record in results
            ]

            # then get the agent records that are shared with the user via groups
            shared_results = (
                session.query(AgentRecord.name, AgentRecord.assistant_id)
                .join(AgentGroup, AgentRecord.assistant_id == AgentGroup.assistant_id)
                .join(GroupUser, AgentGroup.group_id == GroupUser.group_id)
                .filter(GroupUser.user_id == user_id)
                .all()
            )
            shared_agent_records = [
                {"name": name, "assistant_id": assistant_id, "owned": False} for name, assistant_id in shared_results
            ]

            # combine owned and shared agent records
            agent_records.extend(shared_agent_records)
            return agent_records
        
    def can_user_access_agent(self, user_id: str, assistant_id: str) -> bool:
        """
        Validates if a user can access a given agent. The user can either be the owner of the agent
        or the agent could have been shared with the user via a group.
        """
        with self.get_db_session() as session:
            access_query = (
                session.query(AgentRecord)
                .outerjoin(AgentGroup, AgentRecord.assistant_id == AgentGroup.assistant_id)
                .outerjoin(GroupUser, AgentGroup.group_id == GroupUser.group_id)
                .filter(
                    (AgentRecord.owner_user_id == user_id) | 
                    (GroupUser.user_id == user_id),
                    AgentRecord.assistant_id == assistant_id
                )
                .exists()
            )
            return session.query(access_query).scalar()


    def create_group(self, group_id: str, group_name: str, assistant_id: str, user_ids: Optional[List[str]] = None) -> None:
        """
        Creates a group for sharing an agent and optionally associates users with the group.
        """
        with self.get_db_session() as session:
            # Create the group and associate it with the assistant
            agent_group = AgentGroup(assistant_id=assistant_id, group_id=group_id)
            session.add(agent_group)

            # Add users to the group if provided
            if user_ids:
                for user_id in user_ids:
                    group_user = GroupUser(group_id=group_id, user_id=user_id)
                    session.add(group_user)

            session.commit()
            LOGGER.info(f"Created group '{group_name}' with group_id: {group_id} for assistant_id: {assistant_id}")
