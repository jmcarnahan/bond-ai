import json
import logging

LOGGER = logging.getLogger(__name__)

class Functions:

  def use_numbers (self, a, b):
      LOGGER.debug(f"Subtracting {b} from {a}")
      return json.dumps({"value": a - b})







  


