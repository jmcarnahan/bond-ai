import json
import logging 
from typing import List
from bond_ai.bond.functions import Functions
from bond_ai.bond.pages import Pages
LOGGER = logging.getLogger(__name__)

class MySession(dict):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

class MyFunctions(Functions):

  def consume_code_file_ids(self) -> List[str]:
      return []

  def use_numbers (self, a, b):
      return json.dumps({"value": a - b})
  
class MyPages(Pages):

  def get_pages(self):
    return ['foo', 'bar']
