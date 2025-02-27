from bond_ai.bond.config import Config
from bond_ai.bond.threads import Threads
from bond_ai.bond.metadata import Metadata
import os
import sys
import time
import importlib
import logging 
import pytest
import streamlit as st
from tests.common import MySession
from abc import ABC, abstractmethod
LOGGER = logging.getLogger(__name__)


user_id = 'test_user'


class TestThreads(ABC):

  @abstractmethod
  def setup_method(self):
    pass

  def teardown_method(self):
    pass

  def test_create_thread(self):
    thread_id = self.threads.create_thread()
    assert thread_id is not None

  def test_get_current_threads(self):
    thread_id = self.threads.create_thread()
    assert thread_id is not None
    threads = self.threads.get_current_threads(count=10)
    assert len(threads) > 0
    assert threads[0]['thread_id'] == thread_id
    assert threads[0]['name'] == 'New Thread'

  def test_get_current_thread(self):
    thread_id = self.threads.create_thread()
    assert thread_id is not None
    session = MySession()
    current_thread_id = self.threads.get_current_thread_id(session=session)
    assert current_thread_id is not None
    assert current_thread_id == thread_id
    repeat_thread_id = self.threads.get_current_thread_id(session=session)
    assert current_thread_id is not None
    assert current_thread_id == repeat_thread_id    

  def test_update_thread_name(self):
    thread_id = self.threads.create_thread()
    assert thread_id is not None
    self.config.get_openai_client().beta.threads.messages.create(thread_id=thread_id, role="user", content="My New Thread")
    threads = self.threads.get_current_threads(count=10)
    assert len(threads) > 0
    assert threads[0]['thread_id'] == thread_id
    assert threads[0]['name'] == 'My New Thread'

  def test_grant_thread(self):

    thread_id = self.threads.create_thread()
    assert thread_id is not None
    threads = self.metadata.get_current_threads(user_id, count=10)
    assert len(threads) == 1
    assert threads[0]['thread_id'] == thread_id

    threads = self.metadata.get_current_threads('test_user_2', count=10)
    assert len(threads) == 0  

    self.threads.grant_thread(thread_id, 'test_user_2')
    threads = self.metadata.get_current_threads('test_user_2', count=10)
    assert len(threads) == 1
    assert threads[0]['thread_id'] == thread_id

  def test_get_thread(self):
    thread_id = self.threads.create_thread()
    assert thread_id is not None
    thread = self.threads.get_thread(thread_id)
    assert thread is not None
    assert thread['thread_id'] == thread_id



class TestThreadsDB(TestThreads):

  def setup_method(self):
    tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    if tests_path not in sys.path:
        sys.path.append(tests_path)
    st.cache_resource.clear()
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'
    os.environ['METADATA_DB_URL'] = 'sqlite:///.metadata-test.db'
    self.config = Config.config()
    self.threads = Threads.threads(user_id=user_id)
    self.metadata = Metadata.metadata()

  def teardown_method(self):
    threads = self.threads.get_current_threads(count=100)
    for thread in threads:
      self.threads.delete_thread(thread['thread_id'])
      LOGGER.debug(f"Deleted thread {thread['thread_id']}")
    self.metadata.close()
    if os.path.exists('.metadata-test.db'):
      os.remove('.metadata-test.db')
    self.config = None
    self.threads.close()
    self.threads = None




    

