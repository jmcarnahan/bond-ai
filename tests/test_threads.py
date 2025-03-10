import logging 
LOGGER = logging.getLogger(__name__)

from bondable.bond.config import Config
from bondable.bond.threads import Threads
from bondable.bond.metadata import Metadata
from bondable.bond.cache import bond_cache_clear
from tests.common import MySession
import os
import sys
from abc import ABC, abstractmethod



user_id = 'test_user'


class TestThreads(ABC):

  @abstractmethod
  def setup_method(self):
    pass

  @abstractmethod
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
    session = MySession()
    assert thread_id is not None
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
    bond_cache_clear()
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




    

