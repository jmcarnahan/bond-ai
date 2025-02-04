import os
import zmq
import threading
import logging
import json
import time
import queue
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)


PUB_ADDRESS = os.environ.get("BROKER_PUB_ADDRESS", "tcp://localhost:5555")
SUB_ADDRESS = os.environ.get("BROKER_SUB_ADDRESS", "tcp://localhost:5556")


class BondBrockerMessage(BaseModel):
    thread_id: str
    is_error: bool = False

class AgentResponseMessage(BondBrockerMessage):
    message_type: str = "AgentResponseMessage"
    id: str
    type: str
    role: str
    content: str

class MessageMapper:
    def __init__(self):
        self.message_types = {
            "AgentResponseMessage": AgentResponseMessage
        }

    def get_message(self, message_str: str) -> BondBrockerMessage:
        message_json = json.loads(message_str)
        message_type = message_json.get('message_type')
        if message_type is None:
            raise ValueError(f"Message does not contain message_type: {message_str}")
        
        message_class = self.message_types.get(message_type)
        if not message_class:
            raise ValueError(f"Unknown message_type '{message_type}': {message_str}")
        
        return message_class(**message_json)


class BondBrokerConnection:
    
    def __init__(self, pub_address, sub_address):
        self.pub_address = pub_address
        self.sub_address = sub_address
        self.context = zmq.Context()

        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.connect(self.pub_address)

        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect(self.sub_address)
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.message_mapper = MessageMapper()
        self.subscribers = {} # thread_id -> subscriber_id -> queue
        LOGGER.debug(f"Initialized: {str(self)}")

    def __str__(self):
        return f"Connection: pub[({self.pub_address})] sub[({self.sub_address})]"

    def publish(self, message: BondBrockerMessage):
        message_str = message.model_dump_json()
        self.pub_socket.send_string(message_str)
        LOGGER.debug(f"Sent message[{message.id}]: {message.content[0:20]}")

    def start(self):
        self.stop_event = threading.Event() 
        self.conn_thread = threading.Thread(target=self.listen, daemon=True)
        self.conn_thread.start()
        LOGGER.info(f"Started: {str(self)}")

    def listen(self):
      while not self.stop_event.is_set():
          try:
              message_str = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
              msg: BondBrockerMessage = self.message_mapper.get_message(message_str)
              LOGGER.debug(f"Received message[{msg.id}]: {msg.content[0:20]}")
              if msg.thread_id in self.subscribers:
                  for subscriber_id, subscriber_queue in self.subscribers[msg.thread_id].items():
                      LOGGER.debug(f"Relayed message[{msg.id}]: to queue {id(subscriber_queue)} for subscriber {subscriber_id}")
                      subscriber_queue.put(msg)
          except zmq.Again:
              # TODO: may want to add a sleep here
              time.sleep(0.1)
          except Exception as e:
            LOGGER.error(f"Error processing message: {e}")

    def stop(self):
        self.stop_event.set()
        if self.conn_thread.is_alive():
            self.conn_thread.join()

        self.pub_socket.close()
        self.sub_socket.close()
        self.context.term()

        self.subscribers = {}
        LOGGER.info(f"Stopped {str(self)}")

    def subscribe(self, thread_id, subscriber_id) -> queue.Queue:
        if thread_id not in self.subscribers:
            self.subscribers[thread_id] = {}
        if subscriber_id not in self.subscribers[thread_id]:
            self.subscribers[thread_id][subscriber_id] = queue.Queue()
            LOGGER.debug(f"Subscribed to thread {thread_id} with subscriber {subscriber_id} with NEW queue")
        else:
            LOGGER.debug(f"Subscribed to thread {thread_id} with subscriber {subscriber_id} with EXISTING queue")
        return self.subscribers[thread_id][subscriber_id]
    
    def unsubscribe(self, thread_id, subscriber_id):
        if thread_id in self.subscribers and subscriber_id in self.subscribers[thread_id]:
            del self.subscribers[thread_id][subscriber_id]
            if len(self.subscribers[thread_id]) == 0:
                del self.subscribers[thread_id]
        return True

class BondBroker:

  def __init__(self):
    pass


  def start(self):
    self.context = zmq.Context()

    self.pub_socket = self.context.socket(zmq.PUB)
    self.pub_socket.bind(PUB_ADDRESS)

    self.sub_socket = self.context.socket(zmq.SUB)
    self.sub_socket.bind(SUB_ADDRESS)
    self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    self.stop_event = threading.Event() 
    self.broker_thread = threading.Thread(target=self.proxy, daemon=True)
    self.broker_thread.start()
    LOGGER.info(f"Started: {str(self)}")

  def __str__(self):
    return f"Broker: pub[({PUB_ADDRESS})] sub[({SUB_ADDRESS})]"

  def __del__(self):
      self.stop()

  def stop(self):
    try:
        if self.context:
            self.sub_socket.close(linger=0)
            self.pub_socket.close()
            self.context.term()
            self.stop_event.set()
            if self.broker_thread.is_alive():
                self.broker_thread.join()
            self.context = None
            LOGGER.info(f"Stopped {str(self)}")
    except Exception as e:
          LOGGER.error(f"Error closing {str(self)}: {e}")

  def proxy(self):

    try:
        zmq.proxy(self.sub_socket, self.pub_socket)
    except Exception as e:
        LOGGER.warning(f"Stopped proxying messages: {e}")
        #continue

  @classmethod
  def connect(cls):
      return BondBrokerConnection(pub_address=SUB_ADDRESS, sub_address=PUB_ADDRESS)


    



