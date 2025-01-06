from bond_ai.bond.config import Config
import os
import sys
import importlib

def test_openai():
  openai_client = Config.get_openai_client()
  assert openai_client is not None

def test_get_functions():
  functions = Config.get_functions()
  assert functions is not None

class MyPages:
  @classmethod
  def get_pages(cls):
    return ['foo', 'bar']

def test_get_pages():
  #set the env var PAGES_FUNCTION to the string version of the get_pages function in MyPages
  tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
  if tests_path not in sys.path:
      sys.path.append(tests_path)
  os.environ['PAGES_FUNCTION'] = 'test_config.MyPages.get_pages'
  print(os.getenv('PAGES_FUNCTION'))
  pages = Config.get_pages()
  assert pages is not None
