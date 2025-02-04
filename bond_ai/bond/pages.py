from abc import ABC, abstractmethod
import streamlit as st
from bond_ai.bond.agent import Agent
from bond_ai.app.chat_page import ChatPage
from bond_ai.bond.threads import Threads
import logging

LOGGER = logging.getLogger(__name__)

class Pages(ABC):
  def __init__(self, *args, **kwargs):
    self.config = None
    if 'config' in kwargs:
      self.config = kwargs['config']
    if self.config is not None:
      self.session = self.config.get_session()      
    else:
      self.session = None
      LOGGER.warning("No config provided, session will be None")

  def get_config(self):
      return self.config
  
  def get_session(self):
      return self.session
  
  @abstractmethod
  def get_pages(self):
    pass


class DefaultPages(Pages):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def create_chat_page(self, agent, title, threads, thread_id):
      def dynamic_function():
          return ChatPage(agent=agent, title=title, threads=threads, thread_id=thread_id).display_chatbot()
      dynamic_function.__name__ = f"chat_{agent.assistant_id}"
      return dynamic_function

  def get_pages(self): 
    agent_pages = []
    if 'user_id' in self.session:
      user_threads = self.config.get_threads()
      thread_id = user_threads.get_current_thread_id()
      for agent in Agent.list_agents(config=self.config, user_id=self.session['user_id']):
          is_visible:bool = str(agent.get_metadata_value('visible', 'true')).lower() == 'true'
          if is_visible:
            agent_pages.append(st.Page(self.create_chat_page(agent=agent, title=agent.name, threads=user_threads, thread_id=thread_id), title=agent.name))
          else:
             LOGGER.debug(f"Not showing agent: {agent.name}")
      return agent_pages
    else:
      LOGGER.warning("No user id provided, pages will be empty")
      return agent_pages

