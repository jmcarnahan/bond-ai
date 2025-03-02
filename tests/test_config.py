from bondable.bond.config import Config
from bondable.bond.functions import Functions
from bondable.bond.pages import Pages
from bondable.bond.metadata import Metadata

import os
import sys
import importlib
import logging 
import pytest
from tests.common import MySession
LOGGER = logging.getLogger(__name__)

user_id = 'test_user'

class TestConfig:

  @pytest.fixture(scope="class", autouse=True)
  def setup_class(self, request):
    tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    if tests_path not in sys.path:
        sys.path.append(tests_path)

  def setup_method(self):
    import streamlit as st
    st.cache_resource.clear()
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'

  def test_get_config(self):
    config = Config.config()
    config_id = id(config)
    assert config is not None
    config2 = Config.config()
    assert config2 is not None
    config2_id = id(config2)
    assert config_id == config2_id

  def test_openai(self):
    config = Config.config()
    openai_client = config.get_openai_client()
    assert openai_client is not None

  def test_get_functions_default(self):
    if 'FUNCTIONS_CLASS' in os.environ:
      del os.environ['FUNCTIONS_CLASS']
    functions = Functions.functions()
    assert functions is not None
    assert functions.get_config() is not None
    # assert functions.get_config().get_session() is not None
    assert not hasattr(functions, 'use_numbers')
    cached_functions = Functions.functions()
    assert id(functions) == id(cached_functions)

  def test_get_functions_common(self):
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    functions = Functions.functions()
    assert functions is not None
    assert functions.get_config() is not None
    # assert functions.get_config().get_session() is not None
    assert hasattr(functions, 'use_numbers')
    cached_functions = Functions.functions()
    assert id(functions) == id(cached_functions)

  def test_get_pages_default(self):
    if 'PAGES_CLASS' in os.environ:
      del os.environ['PAGES_CLASS']
    pages_cls = Pages.pages()
    assert pages_cls is not None
    pages = pages_cls.get_pages()
    assert isinstance(pages, list)
    assert len(pages) >= 0
    cached_pages_cls = Pages.pages()
    assert id(pages_cls) == id(cached_pages_cls)

  def test_get_pages_common(self):
    os.environ['PAGES_CLASS'] = 'tests.common.MyPages'
    pages_cls = Pages.pages()
    assert pages_cls is not None
    pages = pages_cls.get_pages()
    assert isinstance(pages, list)
    assert len(pages) == 2

  def test_metadata_db(self):
    metadata = Metadata.metadata()
    assert metadata is not None
    current_threads = metadata.get_current_threads(user_id)
    assert isinstance(current_threads, list)
    assert len(current_threads) >= 0
    metadata2 = Metadata.metadata()
    assert metadata2 is not None
    assert id(metadata) == id(metadata2)
    

