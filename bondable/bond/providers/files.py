from abc import ABC, abstractmethod
import io
from bondable.bond.providers.metadata import Metadata, FileRecord
from typing import List, Dict, Any, Optional, Tuple
import logging
import hashlib
from magika import Magika
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

@dataclass
class FileDetails:
    file_id: str
    file_path: str
    file_hash: str
    mime_type: str
    owner_user_id: str
    file_size: Optional[int] = None  # Size in bytes, optional
    
    @classmethod
    def from_file_record(cls, file_record: FileRecord) -> 'FileDetails':
        """Create FileDetails from a FileRecord object while in session context."""
        return cls(
            file_id=file_record.file_id,
            file_path=file_record.file_path,
            file_hash=file_record.file_hash,
            mime_type=file_record.mime_type,
            file_size=file_record.file_size,
            owner_user_id=file_record.owner_user_id
        )

class FilesProvider(ABC):

    metadata: Metadata = None

    def __init__(self, metadata: Metadata):
        """
        Initializes with a Metadata instance.
        Subclasses should call this constructor with their specific Metadata instance.
        """
        self.metadata = metadata

    @abstractmethod
    def delete_file_resource(self, file_id: str) -> bool:
        """
        Deletes a file by its path. Subclasses should implement this method.
        Don't throw an exception if it does not exist, just return False.
        """
        pass

    @abstractmethod
    def create_file_resource(self, file_path: str, file_bytes: io.BytesIO) -> str:
        """
        Creates a new file. Subclasses should implement this method.
        Returns the file_id of the created file.
        """
        pass

    def get_file_bytes(self, file_tuple: Tuple[str, Optional[bytes]]) -> io.BytesIO:
        """
        Returns the SHA-256 hash of the file content.
        If file_bytes is provided, it uses that; otherwise, it reads from the file_path.
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
        return io.BytesIO(file_bytes)

    def get_or_create_file_id(self, user_id, file_tuple: Tuple[str, Optional[bytes]]) -> FileDetails:
        """
        Ensures a file record exists in the database and the resource exists in the provider.
        Returns a FileDetails object with the file details.
        """
        file_path  = file_tuple[0]
        file_bytes = self.get_file_bytes(file_tuple)
        file_bytes.seek(0)  
        content = file_bytes.read()
        file_hash  = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        
        # Detect mime type using Magika
        magika = Magika()
        result = magika.identify_bytes(content)
        mime_type = result.output.mime_type

        with self.metadata.get_db_session() as session:
            # First check if exact same file (path + hash + user) already exists
            exact_match = session.query(FileRecord).filter_by(
                file_path=file_path, 
                file_hash=file_hash, 
                owner_user_id=user_id
            ).first()
            
            if exact_match:
                LOGGER.info(f"Exact file match found for {file_path}. Reusing existing record with file_id: {exact_match.file_id}")
                # Update mime_type if it was not set before
                if not exact_match.mime_type:
                    exact_match.mime_type = mime_type
                    session.commit()
                return FileDetails.from_file_record(exact_match)
            
            # Check if same content (hash) exists for this user with different path
            content_match = session.query(FileRecord).filter_by(
                file_hash=file_hash, 
                owner_user_id=user_id
            ).first()
            
            if content_match:
                # Same content exists with different path - reuse file_id but create new record
                LOGGER.info(f"Content hash for '{file_path}' matches existing record '{content_match.file_path}' (file_id: {content_match.file_id}). Creating new path record with existing file_id.")
                new_record = FileRecord(
                    file_path=file_path, 
                    file_hash=file_hash, 
                    file_id=content_match.file_id,  # Reuse existing file_id
                    mime_type=mime_type, 
                    file_size=file_size,
                    owner_user_id=user_id
                )
                session.add(new_record)
                session.commit()
                return FileDetails.from_file_record(new_record)
            
            # No existing content found - create new file
            file_bytes.seek(0) 
            file_id = self.create_file_resource(file_path, file_bytes)
            file_record = FileRecord(
                file_path=file_path, 
                file_hash=file_hash, 
                file_id=file_id, 
                mime_type=mime_type, 
                file_size=file_size,
                owner_user_id=user_id
            )
            session.add(file_record)
            session.commit()
            LOGGER.info(f"Created new file record for {file_path} with mime_type: {mime_type}")
            return FileDetails.from_file_record(file_record)

    def delete_file(self, file_id: str) -> bool:
        """
        Deletes a file from the configured backend file storage.
        """
        deleted_resource = self.delete_file_resource(file_id)
        with self.metadata.get_db_session() as session:
            try:
                # FileRecord.file_id stores the provider_file_id
                # Delete all local records associated with this provider_file_id
                deleted_rows_count = session.query(FileRecord).filter(FileRecord.file_id == file_id).delete()
                session.commit()
                if deleted_rows_count > 0:
                    LOGGER.info(f"Deleted {deleted_rows_count} local DB records for file_id: {file_id}")
                else:
                    LOGGER.info(f"No local DB records found for file_id: {file_id}")
                return True 
            except Exception as e:
                LOGGER.error(f"Error deleting file records from DB for file_id {file_id}: {e}", exc_info=True)
                raise 

    def delete_files_for_user(self, user_id: str) -> None:
        with self.metadata.get_db_session() as session:    
            for file_record in session.query(FileRecord).filter(FileRecord.owner_user_id == user_id).all():
                if file_record.file_id is None:
                    continue
                try:
                    deleted = self.delete_file(file_record.file_id)
                    LOGGER.info(f"Deleted file with file_id: {file_record.file_id} - Success: {deleted}")
                except Exception as e:
                    LOGGER.error(f"Error deleting file with file_id: {file_record.file_id}. Error: {e}")    


    def get_file_details(self, file_ids: List[str]) -> List[FileDetails]:
        """ Get the file details from the file IDs. """
        with self.metadata.get_db_session() as session:
            file_records = session.query(FileRecord).filter(FileRecord.file_id.in_(file_ids)).all()
            file_details = []
            for file_record in file_records:
                file_details.append(FileDetails.from_file_record(file_record))
            return file_details
        
    # def get_file_paths(self, file_ids: List[str]) -> List[Dict[str, str]]:
    #     """ Get the file path from the file ID. """
    #     with self.metadata.get_db_session() as session:
    #         file_records = session.query(FileRecord).filter(FileRecord.file_id.in_(file_ids)).all()
    #         file_paths = []
    #         for file_record in file_records:
    #             file_paths.append({'file_id': file_record.file_id, 'file_path': file_record.file_path, 'vector_store_id': None})
    #         return file_paths