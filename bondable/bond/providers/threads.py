from abc import ABC, abstractmethod
from bondable.bond.providers.metadata import Metadata, Thread
import logging
from typing import Optional, Dict
from bondable.bond.broker import BondMessage

LOGGER = logging.getLogger(__name__)

class ThreadsProvider(ABC):

    metadata: Metadata = None

    def __init__(self, metadata: Metadata):
        """
        Initializes with a Metadata instance.
        Subclasses should call this constructor with their specific Metadata instance.
        """
        self.metadata = metadata

    @abstractmethod
    def delete_thread_resource(self, thread_id: str) -> bool:
        """
        Deletes a thread by its id. Subclasses should implement this method.
        Don't throw an exception if it does not exist, just return False.
        """
        pass

    @abstractmethod
    def create_thread_resource(self) -> str:
        """
        Creates a new thread. Subclasses should implement this method.
        Returns the thread_id of the created thread.
        """
        pass

    @abstractmethod
    def has_messages(self, thread_id, last_message_id) -> bool:
        pass

    @abstractmethod
    def get_messages(self, thread_id, limit=100) -> Dict[str, BondMessage]:
        pass

    def create_thread(self, user_id: str, name: Optional[str] = None) -> Thread: # Return Thread object
        thread_id = self.create_thread_resource()  
        return self.grant_thread(thread_id=thread_id, user_id=user_id, name=name, fail_if_missing=False)
    
    def update_thread_name(self, thread_id: str, user_id: str, thread_name: str) -> None:
        with self.metadata.get_db_session() as session:  
            thread = session.query(Thread).filter_by(thread_id=thread_id, user_id=user_id).first()
            if thread:
                thread.name = thread_name  
                session.commit()  
            else:
                LOGGER.error(f"Thread {thread_id} not found for user {user_id}. Cannot update name.")

    def update_thread(self, thread_id: str, user_id: str, name: str) -> bool:
        """Update a thread's metadata for a specific user."""
        with self.metadata.get_db_session() as session:  
            thread = session.query(Thread).filter_by(thread_id=thread_id, user_id=user_id).first()
            if thread:
                thread.name = name
                session.commit()  
                return True
            else:
                LOGGER.error(f"Thread {thread_id} not found for user {user_id}. Cannot update.")
                return False


    def get_current_threads(self, user_id: str, count: int = 10) -> list:
        with self.metadata.get_db_session() as session:  
            results = (session.query(Thread.thread_id, Thread.name, Thread.created_at, Thread.updated_at)
                        .filter_by(user_id=user_id).order_by(Thread.created_at.desc()).limit(count).all())
            threads = [
                {"thread_id": thread_id, "name": name, "created_at": created_at, "updated_at": updated_at}
                for thread_id, name, created_at, updated_at in results
            ]
            LOGGER.debug(f"Retrieved available threads: {len(threads)}")
            return threads


    def grant_thread(self, thread_id: str, user_id: str, name: Optional[str] = None, fail_if_missing: bool = False) -> Thread:
        with self.metadata.get_db_session() as session:
            if fail_if_missing:
                # Check if the thread_id exists for *any* user.
                # This confirms the thread is known to the system if we are trying to grant access to an existing thread.
                thread_count = session.query(Thread).filter_by(thread_id=thread_id).count()
                if thread_count == 0:
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


    def delete_thread(self, thread_id: str, user_id: str) -> bool:
        """
        Deletes a thread by its id. Delete the resource if no users are left associated with it.
        """
        with self.metadata.get_db_session() as session:   
            deleted_resource: bool = False    
            deleted_count = session.query(Thread).filter_by(thread_id=thread_id, user_id=user_id).delete()
            current_count = session.query(Thread).filter_by(thread_id=thread_id).count()
            session.commit()  
            if current_count == 0:
                deleted_resource = self.delete_thread_resource(thread_id)  
            if deleted_count > 0:
                LOGGER.info(f"Deleted {deleted_count} DB records for thread_id: {thread_id} and user_id: {user_id} - remaining users: {current_count}")
                return True
            else:
                # This might happen if called multiple times for the same thread_id in teardown
                LOGGER.error(f"No DB records found to delete for thread_id: {thread_id} and user_id: {user_id} (possibly already deleted).")
                return False
        

    def delete_threads_for_user(self, user_id: str) -> None:
         with self.metadata.get_db_session() as session:   
            for thread_id_tuple in session.query(Thread.thread_id).filter(Thread.user_id == user_id).all():
                thread_id = thread_id_tuple[0]
                try:
                    deleted = self.delete_thread(thread_id=thread_id, user_id=user_id)
                    LOGGER.info(f"Deleted thread with thread_id: {thread_id} - Success: {deleted}")
                except Exception as e:
                    LOGGER.error(f"Error deleting thread with thread_id: {thread_id}. Error: {e}")


    def get_thread(self, thread_id: str, user_id: str) -> Optional[Thread]:
        """Get a thread record for a specific user."""
        with self.metadata.get_db_session() as session:
            thread = session.query(Thread).filter_by(thread_id=thread_id, user_id=user_id).first()
            if thread:
                # Detach from session so it can be used outside the session
                session.expunge(thread)
            return thread

    def get_thread_owner(self, thread_id: str) -> Optional[str]:
        with self.metadata.get_db_session() as session:
            thread = session.query(Thread).filter_by(thread_id=thread_id).order_by(Thread.created_at.desc()).first()
            if thread:
                return thread.user_id
            return None