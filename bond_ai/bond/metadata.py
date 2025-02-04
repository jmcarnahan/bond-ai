from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, event, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.sql import text
import os
import logging
import uuid


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

  def __init__(self, config):
    self.session = config.get_session()
    self.engine_key = __name__ + "_metadata_db_engine"
    self.db_session_key = __name__ + "_metadata_db_session"

    if self.engine_key in self.session:
      self.engine = self.session[self.engine_key]
    else:
      metadata_db_url = os.getenv('METADATA_DB_URL', 'sqlite:///.metadata.db')
      self.engine = create_engine(metadata_db_url, echo=False)
      Base.metadata.create_all(self.engine) 
      self.session[self.engine_key] = self.engine
      LOGGER.debug(f"Created database engine for metadata at {metadata_db_url}")


  def get_db_session(self):
    if self.db_session_key not in self.session:
      Session = scoped_session(sessionmaker(bind=self.engine))
      self.session[self.db_session_key] = Session()
      LOGGER.debug(f"Created new database session")
      # # need to re-listen for every new session
      # event.listen(Thread, 'after_update', self.create_after_insert_listener())
    return self.session[self.db_session_key]
      

  def close_db_engine(self):
    self.engine.dispose()
    self.engine = None
    if self.engine_key in self.session:
        del self.session[self.engine_key]
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
