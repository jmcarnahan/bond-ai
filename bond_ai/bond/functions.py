import json
import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod

LOGGER = logging.getLogger(__name__)

class Functions(ABC):

    def __init__(self, *args, **kwargs):
        self.config = None
        if 'config' in kwargs:
            self.config = kwargs['config']
        if self.config is not None:
            self.session = self.config.get_session()
        else:
            LOGGER.warning("No config provided, session will be None")

    def get_config(self):
        return self.config

    @abstractmethod
    def consume_code_file_ids(self) -> List[str]:
        pass


class DefaultFunctions(Functions):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def consume_code_file_ids(self):
        return []




  


