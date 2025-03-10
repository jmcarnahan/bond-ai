import logging 
LOGGER = logging.getLogger(__name__)


from bondable.bond.config import Config
from bondable.bond.functions import Functions
from bondable.bond.pages import Pages
from bondable.bond.metadata import Metadata
import os
from bondable.bond.cache import bond_cache_clear
import pytest


user_id = 'test_user'

class TestConfig:

  @pytest.fixture
  def setup(self):
    yield
    bond_cache_clear()

  def test_get_config(self, setup):
    config = Config.config()
    config_id = id(config)
    assert config is not None
    config2 = Config.config()
    assert config2 is not None
    config2_id = id(config2)
    assert config_id == config2_id

  def test_openai(self, setup):
    config = Config.config()
    openai_client = config.get_openai_client()
    assert openai_client is not None

  def test_get_functions_default(self, setup):
    if 'FUNCTIONS_CLASS' in os.environ:
      del os.environ['FUNCTIONS_CLASS']
    functions = Functions.functions()
    assert functions is not None
    assert functions.get_config() is not None
    # assert functions.get_config().get_session() is not None
    assert not hasattr(functions, 'use_numbers')
    cached_functions = Functions.functions()
    assert id(functions) == id(cached_functions)

  def test_get_functions_common(self, setup):
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    bond_cache_clear()
    functions = Functions.functions()
    assert functions is not None
    assert functions.get_config() is not None
    assert hasattr(functions, 'use_numbers')
    cached_functions = Functions.functions()
    assert id(functions) == id(cached_functions)
    del os.environ['FUNCTIONS_CLASS']

  def test_get_pages_default(self, setup):
    if 'PAGES_CLASS' in os.environ:
      del os.environ['PAGES_CLASS']
    pages_cls = Pages.pages()
    assert pages_cls is not None
    pages = pages_cls.get_pages()
    assert isinstance(pages, list)
    assert len(pages) >= 0
    cached_pages_cls = Pages.pages()
    assert id(pages_cls) == id(cached_pages_cls)

  def test_get_pages_common(self, setup):
    os.environ['PAGES_CLASS'] = 'tests.common.MyPages'
    bond_cache_clear()
    pages_cls = Pages.pages()
    assert pages_cls is not None
    pages = pages_cls.get_pages()
    assert isinstance(pages, list)
    assert len(pages) == 2
    del os.environ['PAGES_CLASS']

  def test_metadata_db(self, setup):
    metadata = Metadata.metadata()
    assert metadata is not None
    current_threads = metadata.get_current_threads(user_id)
    assert isinstance(current_threads, list)
    assert len(current_threads) >= 0
    metadata2 = Metadata.metadata()
    assert metadata2 is not None
    assert id(metadata) == id(metadata2)
    

