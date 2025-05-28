import logging 
LOGGER = logging.getLogger(__name__)

from typing import List
from bondable.bond.functions import Functions



class MySession(dict):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

class MyFunctions(Functions):

  def consume_code_file_ids(self) -> List[str]:
      return []

  def use_numbers (self, a, b):
      try:
        import json
        return json.dumps({"value": a - b})
      except Exception as e:
        LOGGER.error(f"Error in use_numbers: {e}")
        return '{"error": "Error in use_numbers"}'
  

