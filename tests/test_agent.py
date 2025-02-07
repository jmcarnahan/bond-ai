from bond_ai.bond.agent import Agent
from bond_ai.bond.broker import BondBroker, AgentResponseMessage
from bond_ai.bond.threads import Threads, ThreadMessageHandler, ThreadMessageParser
from bond_ai.bond.config import Config
from tests.common import MySession
import pytest
import os
import time
import logging

LOGGER = logging.getLogger(__name__)

user_id = 'test_user'


import xml.sax


class MyThreadMessageHandler(ThreadMessageHandler):

    def __init__(self):
        self.messages = []

    def set_parser(self, parser:ThreadMessageParser):
        self.parser = parser

    def onMessage(self, thread_id, message_id, type, role, is_error=False, is_done=False, clob=None):

        if role == 'system':
            LOGGER.debug(f"Received system message, ignoring {message_id}")
            self.parser.stop()
        if type == "text":
            self.messages.append(clob.get_content())
        elif type == "image_file":
            pass
        else:
            raise Exception(f"Unknown message type {type}")


class TestAgent:

  def find_open_port(self):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port

  def setup_method(self):
    os.environ['METADATA_CLASS'] = 'bond_ai.bond.metadata.metadata_db.MetadataSqlAlchemy'
    os.environ['FUNCTIONS_CLASS'] = 'tests.common.MyFunctions'
    os.environ['BROKER_PUB_ADDRESS'] = f"tcp://localhost:{self.find_open_port()}"
    os.environ['BROKER_SUB_ADDRESS'] = f"tcp://localhost:{self.find_open_port()}"
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
      
  def test_simple_agent_broadcast(self):
      self.session['user_id'] = user_id
      openai_client = self.config.get_openai_client()
      simple_assistant = openai_client.beta.assistants.create(
          name="Simple Agent",
          instructions="You are a helpful assistant that answers questions in a single sentence",
          model=self.config.get_openai_deployment(),
      )
      assert simple_assistant is not None
      threads = self.config.get_threads()
      thread_id = threads.create_thread()
      xml_queue = threads.subscribe(thread_id=thread_id)
      assert thread_id is not None
      try:
        agent = Agent.get_agent_by_name("Simple Agent", config=self.config, user_id=user_id)
        assert agent is not None
        agent.broadcast_response("Say Hello", thread_id)

        handler = MyThreadMessageHandler()
        parser = ThreadMessageParser(handler)
        handler.set_parser(parser)
        
        parser.parse(xml_queue)
        assert len(handler.messages) > 1
        assert handler.messages[0] == "Say Hello"
        assert "Hello" in handler.messages[1]

        assert threads.unsubscribe(thread_id=thread_id)
        threads.close()
      finally:
        response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
        assert response is not None
        assert response.deleted == True
        threads.delete_thread(thread_id)
  
  def test_multiple_users_broadcast(self):
    
    openai_client = self.config.get_openai_client()
    simple_assistant = openai_client.beta.assistants.create(
        name="Simple Agent",
        instructions="You are a helpful assistant",
        model=self.config.get_openai_deployment(),
    )
    assert simple_assistant is not None



    handler_1 = MyThreadMessageHandler()
    parser_1 = ThreadMessageParser(handler_1)
    handler_1.set_parser(parser_1)

    self.session['user_id'] = 'test_user_1'
    threads_1 = self.config.get_threads()
    thread_id = threads_1.create_thread()
    queue_1 = threads_1.subscribe(thread_id=thread_id)

    handler_2 = MyThreadMessageHandler()
    parser_2 = ThreadMessageParser(handler_2)
    handler_2.set_parser(parser_2)

    self.session['user_id'] = 'test_user_2'
    threads_2 = self.config.get_threads()
    threads_1.grant_thread(thread_id=thread_id, user_id='test_user_2')
    queue_2 = threads_2.subscribe(thread_id=thread_id)

    try:
      agent = Agent.get_agent_by_name("Simple Agent", config=self.config, user_id='test_user_1')
      assert agent is not None

      agent.broadcast_response("Say Hello", thread_id)
      
      parser_1.parse(queue_1)
      assert len(handler_1.messages) > 1
      assert handler_1.messages[0] == "Say Hello"
      assert "Hello" in handler_1.messages[1]


      parser_2.parse(queue_2)
      assert len(handler_2.messages) > 1
      assert handler_2.messages[0] == "Say Hello"
      assert "Hello" in handler_2.messages[1]

      assert threads_1.unsubscribe(thread_id=thread_id)
      assert threads_2.unsubscribe(thread_id=thread_id)

    finally:
      response = openai_client.beta.assistants.delete(assistant_id=simple_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads_1.delete_thread(thread_id)
      threads_1.close()
      threads_2.close()


  def test_functions_agent_broadcast(self):
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
    xml_queue = threads.subscribe(thread_id=thread_id)
    assert thread_id is not None
    try:
      agent = Agent.get_agent_by_name("Functions Agent", config=self.config, user_id=user_id)
      assert agent is not None

      agent.broadcast_response("The numbers are 3 and 4", thread_id)

      handler = MyThreadMessageHandler()
      parser = ThreadMessageParser(handler)
      handler.set_parser(parser)
      
      parser.parse(xml_queue)
      assert len(handler.messages) > 1
      assert handler.messages[0] == "The numbers are 3 and 4"
      assert "-1" in handler.messages[1]

      
    finally:
      response = openai_client.beta.assistants.delete(assistant_id=functions_assistant.id)
      assert response is not None
      assert response.deleted == True
      threads.delete_thread(thread_id)
      threads.close()

