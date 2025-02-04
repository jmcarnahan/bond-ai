from bond_ai.bond.agent import Agent
from bond_ai.bond.broker import BondBroker, AgentResponseMessage
from bond_ai.bond.threads import Threads
from bond_ai.bond.config import Config
from tests.common import MySession
import pytest
import os
import time
import logging

LOGGER = logging.getLogger(__name__)

user_id = 'test_user'



class TestAgent:

  def setup_method(self):
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    self.broker = BondBroker()
    self.broker.start()
    self.session = MySession()
    self.config = Config(session=self.session)

  def teardown_method(self):
    self.config.get_threads().close()
    self.broker.stop()


  def test_list_agents(self):
    self.session['user_id'] = user_id
    agents = Agent.list_agents(self.config, user_id=user_id)
    assert len(agents) > 0


  def test_simple_agent(self):
    self.session['user_id'] = user_id
    openai_client = self.config.get_openai_client()
    simple_assistant = openai_client.beta.assistants.create(
        name="Simple Agent",
        instructions="You are a helpful assistant",
        model=self.config.get_openai_deployment(),
    )
    assert simple_assistant is not None
    threads = self.config.get_threads()
    thread_id = threads.create_thread()
    queue = threads.subscribe(thread_id=thread_id)
    assert thread_id is not None
    try:
      agent = Agent.get_agent_by_name("Simple Agent", config=self.config, user_id=user_id)
      assert agent is not None
      agent.handle_response("Say Hello", thread_id)
      response = queue.get(timeout=30)
      assert response is not None
      assert response.content == "Say Hello"
      response = queue.get(timeout=30)
      assert response is not None
      assert "Hello" in response.content
      assert threads.unsubscribe(thread_id=thread_id)
      threads.close()
    finally:
      response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads.delete_thread(thread_id)
      

  
  def test_multiple_users(self):
    
    openai_client = self.config.get_openai_client()
    simple_assistant = openai_client.beta.assistants.create(
        name="Simple Agent",
        instructions="You are a helpful assistant",
        model=self.config.get_openai_deployment(),
    )
    assert simple_assistant is not None

    self.session['user_id'] = 'test_user_1'
    threads_1 = self.config.get_threads()
    thread_id = threads_1.create_thread()
    queue_1 = threads_1.subscribe(thread_id=thread_id)

    self.session['user_id'] = 'test_user_2'
    threads_2 = self.config.get_threads()
    threads_2.grant_thread(thread_id=thread_id, user_id='test_user_2')
    queue_2 = threads_2.subscribe(thread_id=thread_id)

    try:
      agent = Agent.get_agent_by_name("Simple Agent", config=self.config, user_id='test_user_1')
      assert agent is not None

      agent.handle_response("Say Hello", thread_id)

      response = queue_1.get(timeout=30)
      assert response is not None
      assert response.content == "Say Hello"
      response = queue_1.get(timeout=30)
      assert response is not None
      assert "Hello" in response.content

      response = queue_2.get(timeout=30)
      assert response is not None
      assert response.content == "Say Hello"
      response = queue_2.get(timeout=30)
      assert response is not None
      assert "Hello" in response.content

      assert threads_1.unsubscribe(thread_id=thread_id)
      assert threads_2.unsubscribe(thread_id=thread_id)

    finally:
      response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads_1.delete_thread(thread_id)
      threads_1.close()
      threads_2.close()


  def test_functions_agent(self):
    self.session['user_id'] = user_id
    openai_client = self.config.get_openai_client()
    functions_assistant = openai_client.beta.assistants.create(
        name="Functions Agent",
        instructions="""
        You are a helpful assistant that answers questions about numbers. When the user
        gives you two numbers, you will use them to call the function 'use_numbers'. The use
        the result of that function to answer the question.
        """,
        tools=[{"type": "code_interpreter"},
          {
            "type": "function",
            "function": {
              "name": "use_numbers",
              "description": "use two numbers to generate a result",
              "parameters": {
                "type": "object",
                "properties": {
                  "a": {
                    "type": "integer",
                    "description": "first number"
                  },
                  "b": {
                    "type": "integer",
                    "description": "second number"
                  },
                },
                "required": ["a", "b"]
              }
            }
          }],
        model=self.config.get_openai_deployment(),
    )
    assert functions_assistant is not None
    threads = self.config.get_threads()
    thread_id = threads.create_thread()
    queue = threads.subscribe(thread_id=thread_id)
    assert thread_id is not None
    try:
      agent = Agent.get_agent_by_name("Functions Agent", config=self.config, user_id=user_id)
      assert agent is not None
      agent.handle_response("The numbers are 3 and 4", thread_id)
      response = queue.get(timeout=30)
      assert response is not None
      assert response.content == "The numbers are 3 and 4"
      response = queue.get(timeout=30)
      assert response is not None
      assert "-1" in response.content
      threads.close()
    finally:
      response = openai_client.beta.assistants.delete(assistant_id=functions_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads.delete_thread(thread_id)

