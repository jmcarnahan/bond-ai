import logging
LOGGER = logging.getLogger(__name__)

from abc import ABC, abstractmethod
from bondable.bond.agent import Agent
from bondable.app.chat_page import ChatPage
from bondable.bond.page import Page
from bondable.bond.config import Config
from bondable.bond.cache import bond_cache
import os
import importlib


class Pages(ABC):

  def __init__(self, *args, **kwargs):
    pass

  def get_config(self):
      return Config.config()
  
  @abstractmethod
  def get_pages(self) -> list[Page]:
    pass

  @classmethod
  @bond_cache
  def pages(cls):
      fully_qualified_name = os.getenv('PAGES_CLASS', f"{DefaultPages.__module__}.{DefaultPages.__qualname__}")
      try:
          module_name, class_name = fully_qualified_name.rsplit(".", 1)
          module = importlib.import_module(module_name)
          instance_class = getattr(module, class_name)
          if not issubclass(instance_class, Pages):
              raise ValueError(f"Class {class_name} must extend {Pages}")
          instance = instance_class()
          LOGGER.info(f"Created Pages instance using class: ({fully_qualified_name})")      
          return instance
      except ImportError:
          raise ImportError(f"Could not import module: {fully_qualified_name}")


class DefaultPages(Pages):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    
  def get_pages(self) -> list[Page]: 
    agent_pages = []
    for agent in Agent.list_agents():
        is_visible:bool = str(agent.get_metadata_value('visible', 'true')).lower() == 'true'
        if is_visible:
          agent_pages.append(ChatPage(agent=agent, title=agent.name))
        else:
            LOGGER.debug(f"Not showing agent: {agent.name}")
    return agent_pages


