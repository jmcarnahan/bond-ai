import json
import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod
import os
import importlib
from bondable.bond.config import Config
from bondable.bond.decorator import bondtool
from bondable.bond.cache import bond_cache

LOGGER = logging.getLogger(__name__)

class Functions(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def get_config(self):
        return Config.config()

    @abstractmethod
    def consume_code_file_ids(self) -> List[str]:
        pass

    @classmethod
    @bond_cache
    def functions(cls):
        fully_qualified_name = os.getenv('FUNCTIONS_CLASS', f"{DefaultFunctions.__module__}.{DefaultFunctions.__qualname__}")
        try:
            module_name, class_name = fully_qualified_name.rsplit(".", 1)
            module = importlib.import_module(module_name)
            instance_class = getattr(module, class_name)
            if not issubclass(instance_class, Functions):
                raise ValueError(f"Class {class_name} must extend {Functions}")
            instance = instance_class()
            LOGGER.info(f"Created Functions instance using class: ({fully_qualified_name})")      
            return instance
        except ImportError:
            raise ImportError(f"Could not import module: {fully_qualified_name}")

class DefaultFunctions(Functions):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def consume_code_file_ids(self):
        return []
    
    @bondtool(description="Will say hello to the name provided.", arg_descriptions={"name": "The name to say hello to."})
    def hello(self, name:str) -> str:
        LOGGER.info(f"Saying hello to: {name}")
        return f"Hello, {name}!"




  


