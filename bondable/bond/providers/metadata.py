from abc import ABC, abstractmethod


from sqlalchemy import ForeignKey, create_engine, Column, String, DateTime, func, PrimaryKeyConstraint, UniqueConstraint, Boolean, JSON, Integer
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.sql import text
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple


LOGGER = logging.getLogger(__name__)


# These are the default ORM classes 
# All instances of Metadata should use these classes and augment them as needed
Base = declarative_base()
class Thread(Base):
    __tablename__ = 'threads'
    thread_id = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    name = Column(String, default="New Thread")
    session_id = Column(String, nullable=True)  # remote session ID if any
    session_state = Column(JSON, default=dict)  # remote session state if any
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (PrimaryKeyConstraint('thread_id', 'user_id'),)
class AgentRecord(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    introduction = Column(String, nullable=True, default="")
    reminder = Column(String, nullable=True, default="")
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

class FileRecord(Base):
    __tablename__ = "files"
    file_id = Column(String, primary_key=True)  # Unique file ID from provider
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    mime_type = Column(String, default="application/octet-stream")  # Default MIME type
    file_size = Column(Integer, nullable=True)  # Size in bytes
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # Unique constraint on file_path + file_hash + owner_user_id
    # This allows same user to upload different versions of same file
    # and different users to upload same file
    __table_args__ = (UniqueConstraint('file_path', 'file_hash', 'owner_user_id', name='_file_path_hash_user_uc'),)
class VectorStore(Base):
    __tablename__ = "vector_stores"
    vector_store_id = Column(String, primary_key=True)  # Use vector_store_id as primary key
    name = Column(String, nullable=False)
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    default_for_agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # Unique constraint on name + owner_user_id
    # This allows different users to have vector stores with the same name
    __table_args__ = (UniqueConstraint('name', 'owner_user_id', name='_vector_store_name_user_uc'),)
class AgentGroup(Base):
    __tablename__ = "agent_groups"
    agent_id = Column(String, ForeignKey('agents.agent_id'), primary_key=True)
    group_id = Column(String, ForeignKey('groups.id'), primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class Group(Base):
    __tablename__ = "groups"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
class GroupUser(Base):
    __tablename__ = "group_users"
    group_id = Column(String, ForeignKey('groups.id'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    sign_in_method = Column(String, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)



class Metadata(ABC):

    def __init__(self, metadata_db_url):
        self.metadata_db_url = metadata_db_url
        self.engine = create_engine(self.metadata_db_url, echo=False)
        self.create_all()
        self.session = scoped_session(sessionmaker(bind=self.engine))
        LOGGER.info(f"Created Metadata instance using database engine: {self.metadata_db_url}")

    def get_engine(self):
        return self.engine

    def create_all(self):
        # This method should be overriden by subclasses to create all necessary tables
        return Base.metadata.create_all(self.engine)
    
    def drop_and_recreate_all(self):
        """Drop all tables and recreate them. Use with caution - this deletes all data!"""
        LOGGER.warning("Dropping all tables and recreating schema. All data will be lost!")
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        LOGGER.info("Schema recreated successfully")
        
    def get_db_session(self) -> scoped_session:
        if not self.engine:
            self.engine = create_engine(self.metadata_db_url, echo=False)
            self.create_all()
            self.session = scoped_session(sessionmaker(bind=self.engine))
            LOGGER.info(f"Re-created Metadata instance using database engine: {self.metadata_db_url}")
        return self.session()

    def close_db_engine(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None
            LOGGER.info(f"Closed database engine")

    def close(self) -> None:
        self.close_db_engine()
    
    def get_or_create_system_user(self) -> User:
        """
        Get or create the system user for internal operations.
        
        Returns:
            User: The system user object
        """
        with self.get_db_session() as session:
            system_user = session.query(User).filter(User.email == "system@bondableai.com").first()
            
            if not system_user:
                # Create system user
                import uuid
                system_user = User(
                    id=str(uuid.uuid4()),
                    email="system@bondableai.com",
                    name="System",
                    sign_in_method="system"
                )
                session.add(system_user)
                session.commit()
                LOGGER.info(f"Created system user with id: {system_user.id}")
            
            return system_user




