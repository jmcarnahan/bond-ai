import logging
LOGGER = logging.getLogger(__name__)

from bondable.bond.agent import Agent
from bondable.bond.broker import Broker, BondMessage
from bondable.bond.threads import Threads
from bondable.bond.config import Config
from bondable.bond.functions import Functions
from bondable.bond.cache import bond_cache_clear
import pytest
import os
import time


user_id = 'test_user'

class TestAgent:

  def setup_method(self):
    bond_cache_clear()
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    self.broker = Broker.broker()
    self.config = Config.config()
    self.threads = Threads.threads(user_id=user_id)

  def teardown_method(self):
    self.threads.close()
    self.broker.stop()
    bond_cache_clear()
    del os.environ['METADATA_CLASS']
    del os.environ['FUNCTIONS_CLASS']

  def test_list_agents(self):
    agents = Agent.list_agents()
    assert len(agents) > 0

  def test_create_system_messsage(self):
      openai_client = self.config.get_openai_client()
      simple_assistant = openai_client.beta.assistants.create(
          name="Simple Agent",
          instructions="You are a helpful assistant that answers questions in a single sentence",
          model=self.config.get_openai_deployment(),
      )
      assert simple_assistant is not None
      thread_id = self.threads.create_thread()
      assert thread_id is not None
      conn = self.broker.connect(thread_id=thread_id, subscriber_id=user_id)
      assert conn is not None
      try:
        agent = Agent.get_agent_by_name("Simple Agent")
        assert agent is not None

        msg = agent.create_user_message("Say Hello", thread_id, override_role="system")
        response: BondMessage  = conn.wait_for_message()
        assert response is not None
        assert response.thread_id == thread_id
        assert response.role == "system"
        assert response.type == "text"
        assert response.clob.get_content() == "Say Hello"

        # get the messages from the thread
        msgs = self.threads.get_messages(thread_id)
        assert len(msgs) == 1
        response = list(msgs.values())[0]
        assert response.role == "system"
        assert response.type == "text"
        assert response.clob.get_content() == "Say Hello"

      finally:
        response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
        assert response is not None
        assert response.deleted == True
        self.threads.delete_thread(thread_id)


  def test_simple_agent_broadcast(self):
      openai_client = self.config.get_openai_client()
      simple_assistant = openai_client.beta.assistants.create(
          name="Simple Agent",
          instructions="You are a helpful assistant that answers questions in a single sentence",
          model=self.config.get_openai_deployment(),
      )
      assert simple_assistant is not None
      thread_id = self.threads.create_thread()
      assert thread_id is not None
      conn = self.broker.connect(thread_id=thread_id, subscriber_id=user_id)
      assert conn is not None
      try:
        agent = Agent.get_agent_by_name("Simple Agent")
        assert agent is not None

        agent.broadcast_response("Say Hello", thread_id)
        response: BondMessage  = conn.wait_for_message()
        assert response is not None
        assert response.thread_id == thread_id
        assert response.role == "user"
        assert response.type == "text"
        assert response.clob.get_content() == "Say Hello"

        response: BondMessage = conn.wait_for_message()
        assert response is not None
        assert response.thread_id == thread_id
        assert response.role == "assistant"
        assert response.type == "text"
        assert "hello" in response.clob.get_content().lower()

      finally:
        response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
        assert response is not None
        assert response.deleted == True
        self.threads.delete_thread(thread_id)


  def test_multiple_users_broadcast(self):

    openai_client = self.config.get_openai_client()
    simple_assistant = openai_client.beta.assistants.create(
        name="Simple Agent",
        instructions="You are a helpful assistant",
        model=self.config.get_openai_deployment(),
    )
    assert simple_assistant is not None

    threads = Threads.threads(user_id='test_user_1')
    thread_id = threads.create_thread()

    conn_1 = self.broker.connect(thread_id=thread_id, subscriber_id='test_user_1')
    assert conn_1 is not None
    conn_2 = self.broker.connect(thread_id=thread_id, subscriber_id='test_user_2')
    assert conn_2 is not None

    try:
      agent = Agent.get_agent_by_name("Simple Agent")
      assert agent is not None

      agent.broadcast_response("Say Hello", thread_id)

      response: BondMessage  = conn_1.wait_for_message()
      assert response is not None
      assert response.clob.get_content() == "Say Hello"

      response: BondMessage = conn_1.wait_for_message()
      assert response is not None
      assert "hello" in response.clob.get_content().lower()

      response: BondMessage  = conn_2.wait_for_message()
      assert response is not None
      assert response.clob.get_content() == "Say Hello"

      response: BondMessage = conn_2.wait_for_message()
      assert response is not None
      assert "hello" in response.clob.get_content().lower()

    finally:
      response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads.delete_thread(thread_id)



  def test_functions_agent_broadcast(self):

    # first confirm that the function is working
    fxns = Functions.functions()
    result = fxns.use_numbers(a=3, b=4)
    assert result == '{"value": -1}'

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

    thread_id = self.threads.create_thread()
    assert thread_id is not None

    conn = self.broker.connect(thread_id=thread_id, subscriber_id=user_id)
    assert conn is not None

    try:
      agent = Agent.get_agent_by_name("Functions Agent")
      assert agent is not None

      agent.broadcast_response("The numbers are 3 and 4", thread_id)

      response: BondMessage  = conn.wait_for_message()
      assert response is not None
      assert response.clob.get_content() == "The numbers are 3 and 4"

      response: BondMessage = conn.wait_for_message()
      assert response is not None
      assert "-1" in response.clob.get_content().lower()


    finally:
      response = openai_client.beta.assistants.delete(assistant_id=functions_assistant.id)
      assert response is not None
      assert response.deleted == True
      self.threads.delete_thread(thread_id)















  # def test_simple_agent_handler(self):
  #   self.session['user_id'] = user_id
  #   openai_client = self.config.get_openai_client()
  #   simple_assistant = openai_client.beta.assistants.create(
  #       name="Simple Agent",
  #       instructions="You are a helpful assistant that answers questions in a single sentence",
  #       model=self.config.get_openai_deployment(),
  #   )
  #   assert simple_assistant is not None
  #   threads = self.config.get_threads()
  #   thread_id = threads.create_thread()
  #   queue = threads.subscribe(thread_id=thread_id)
  #   assert thread_id is not None
  #   try:
  #     agent = Agent.get_agent_by_name("Simple Agent", config=self.config, user_id=user_id)
  #     assert agent is not None
  #     agent.handle_response("Say Hello", thread_id)
  #     response = queue.get(timeout=30)
  #     assert response is not None
  #     assert response.content == "Say Hello"
  #     response = queue.get(timeout=30)
  #     assert response is not None
  #     assert "Hello" in response.content
  #     response = queue.get(timeout=30)
  #     assert response is not None
  #     assert "Done" in response.content
  #     assert response.role == "system"
  #     assert response.is_done == True
  #     assert threads.unsubscribe(thread_id=thread_id)
  #     threads.close()
  #   finally:
  #     response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
  #     assert response is not None
  #     assert response.deleted == True
  #     threads.delete_thread(thread_id)
