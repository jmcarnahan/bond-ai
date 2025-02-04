from bond_ai.bond.config import Config
import os
import sys
import importlib
import logging 
import pytest
from tests.common import MySession
LOGGER = logging.getLogger(__name__)




class TestConfig:

  @pytest.fixture(scope="class", autouse=True)
  def setup_class(self, request):
    self.session = MySession()
    request.cls.session = self.session
    tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    if tests_path not in sys.path:
        sys.path.append(tests_path)

  def setup_method(self):
    if '_FUNCTIONS_INSTANCE' in self.session:
      del self.session['_FUNCTIONS_INSTANCE']
    if '_PAGES_INSTANCE' in self.session:
      del self.session['_PAGES_INSTANCE']
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'
    self.config = Config(session=self.session)

  def test_openai(self):
    openai_client = self.config.get_openai_client()
    assert openai_client is not None

  def test_get_functions_default(self):
    if 'FUNCTIONS_CLASS' in os.environ:
      del os.environ['FUNCTIONS_CLASS']
    functions = self.config.get_functions()
    assert functions is not None
    assert functions.get_config() is not None
    assert functions.get_config().get_session() is not None
    assert not hasattr(functions, 'use_numbers')
    cached_functions = self.config.get_functions()
    assert id(functions) == id(cached_functions)

  def test_get_functions_common(self):
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    functions = self.config.get_functions()
    assert functions is not None
    assert functions.get_config() is not None
    assert functions.get_config().get_session() is not None
    assert hasattr(functions, 'use_numbers')
    cached_functions = self.config.get_functions()
    assert id(functions) == id(cached_functions)

  def test_get_pages_default(self):
    if 'PAGES_CLASS' in os.environ:
      del os.environ['PAGES_CLASS']
    pages = self.config.get_pages()
    assert pages is not None
    assert isinstance(pages, list)
    assert len(pages) == 0

  def test_get_pages_common(self):
    os.environ['PAGES_CLASS'] = 'tests.common.MyPages'
    pages = self.config.get_pages()
    assert pages is not None
    assert isinstance(pages, list)
    assert len(pages) == 2

  def test_metadata_db(self):
    # the meta data class is set up in the setup_method
    metadata = self.config.get_metadata()
    assert metadata is not None
    

