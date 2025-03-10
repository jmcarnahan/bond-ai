from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, event, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.sql import text
import os
import logging
import uuid
from bondable.bond.cache import bond_cache


LOGGER = logging.getLogger(__name__)

Base = declarative_base()
class Thread(Base):
  __tablename__ = 'threads'
  thread_id = Column(String, nullable=False)
  user_id = Column(String, nullable=False)
  name = Column(String)
  created_at = Column(DateTime, default=func.now())
  updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
  __table_args__ = (PrimaryKeyConstraint('thread_id', 'user_id'),)

class Metadata:

  def __init__(self):
    self.metadata_db_url = os.getenv('METADATA_DB_URL', 'sqlite:///.metadata.db')
    self.engine = create_engine(self.metadata_db_url, echo=False)
    Base.metadata.create_all(self.engine) 
    self.session = scoped_session(sessionmaker(bind=self.engine))
    LOGGER.info(f"Created Metadata instance using database engine: {self.metadata_db_url}")

  @classmethod
  @bond_cache
  def metadata(cls):
    return Metadata()

  def get_db_session(self):
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

  def close(self) -> None:
    self.close_db_engine()

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


  def grant_thread(self, thread_id: str, user_id: str, fail_if_missing: bool = False) -> str:
      with self.get_db_session() as session:
          existing_users = (session.query(Thread.user_id).filter(Thread.thread_id == thread_id).all())
          if fail_if_missing and not existing_users:
              raise Exception(f"Thread {thread_id} not found")
          user_ids = {user[0] for user in existing_users}
          if user_id not in user_ids:
              new_access = Thread(thread_id=thread_id, user_id=user_id)
              session.add(new_access)
              session.commit()
          return thread_id

  def delete_thread(self, thread_id: str) -> None:
      with self.get_db_session() as session:
          session.query(Thread).filter(Thread.thread_id == thread_id).delete()
          session.commit()

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
