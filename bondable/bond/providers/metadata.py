from abc import ABC, abstractmethod


from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, event, PrimaryKeyConstraint, Index
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
    user_id = Column(String, nullable=False)
    name = Column(String, default="New Thread")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (PrimaryKeyConstraint('thread_id', 'user_id'),)
class AgentRecord(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True) # Changed to primary key
    name = Column(String, nullable=False) # No longer primary key, but still required
    owner_user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    # Consider adding a UniqueConstraint('name', 'owner_user_id', name='uq_agent_name_owner') if names should be unique per user
class FileRecord(Base):
    __tablename__ = "files"
    file_path = Column(String, primary_key=True)
    file_hash = Column(String, nullable=False)
    file_id = Column(String)
    mime_type = Column(String)
    owner_user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
class VectorStore(Base):
    __tablename__ = "vector_stores"
    name = Column(String, primary_key=True)
    vector_store_id = Column(String, nullable=False)
    owner_user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
class AgentGroup(Base):
    __tablename__ = "agent_groups"
    agent_id = Column(String, primary_key=True)
    group_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class GroupUser(Base):
    __tablename__ = "group_users"
    group_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
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




