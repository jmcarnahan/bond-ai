import os
import zmq
import threading
import logging
import json
import time
import queue
import re
from pydantic import BaseModel
import xml.etree.ElementTree as ET

LOGGER = logging.getLogger(__name__)


PUB_ADDRESS = os.environ.get("BROKER_PUB_ADDRESS", "tcp://localhost:5555")
SUB_ADDRESS = os.environ.get("BROKER_SUB_ADDRESS", "tcp://localhost:5556")


class BondBrockerMessage(BaseModel):
    thread_id: str
    is_error: bool = False
    is_done: bool = False

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

        self.current_thread_ids = []
        self.current_message_ids = []

        LOGGER.debug(f"Initialized: {str(self)}")

    def __str__(self):
        return f"Connection: pub[({self.pub_address})] sub[({self.sub_address})]"

    def publish(self, message: BondBrockerMessage):
        message_str = message.model_dump_json()
        self.pub_socket.send_string(message_str)
        LOGGER.debug(f"Sent message[{message.id}]: {message.content[0:20]}")

    def put (self, content:str):
        self.pub_socket.send_string(content)
        LOGGER.debug(f"Put content: {content[0:20]}")

    def start(self):
        self.stop_event = threading.Event() 
        self.conn_thread = threading.Thread(target=self.listen, daemon=True)
        self.conn_thread.start()
        LOGGER.info(f"Started: {str(self)}")

    def is_json(self, message_str:str):
        try:
            json.loads(message_str)
            return True
        except (ValueError, TypeError):
            return False
        
    def is_bondmessage_start_tag(self, message_str:str):
        pattern = r'^<\s*_bondmessage(?:\s+[\w:-]+="[^"]*")*\s*/?>$'
        return bool(re.match(pattern, message_str.strip()))

    def parse_bondmessage_start_tag(self, message_str:str):
        pattern = r'^<\s*_bondmessage(?:\s+([\w:-]+)="([^"]*)")*\s*/?>$'
        if not re.match(pattern, message_str.strip()):
            return None  
        attributes = dict(re.findall(r'([\w:-]+)="([^"]*)"', message_str))
        return attributes
    
    def is_bondmessage_end_tag(self, message_str:str):
        pattern = r'^</\s*_bondmessage\s*>$'
        return bool(re.match(pattern, message_str.strip()))

    def send_string(self, message_str):
        message_id = self.current_message_ids[-1] if len(self.current_message_ids) > 0 else None
        thread_id = self.current_thread_ids[-1] if len(self.current_thread_ids) > 0 else None
        if message_id is None or thread_id is None:
            raise ValueError(f"Invalid message: {message_str}: unknown thread_id or message_id")
        if thread_id in self.subscribers:
            for subscriber_id, subscriber_queue in self.subscribers[thread_id].items():
                LOGGER.debug(f"Relayed message[{message_id}]: to queue {id(subscriber_queue)} for subscriber {subscriber_id}")
                subscriber_queue.put(message_str)     

    def listen(self):
        while not self.stop_event.is_set():
            message_str = None
            try:
                message_str = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
                LOGGER.debug(f"Received message: {message_str[0:100]}")
                # if self.is_json(message_str):
                #     msg: BondBrockerMessage = self.message_mapper.get_message(message_str)
                #     LOGGER.debug(f"Received JSON message[{msg.id}]: {msg.content[0:20]}")
                #     if msg.thread_id in self.subscribers:
                #         for subscriber_id, subscriber_queue in self.subscribers[msg.thread_id].items():
                #             LOGGER.debug(f"Relayed message[{msg.id}]: to queue {id(subscriber_queue)} for subscriber {subscriber_id}")
                #             subscriber_queue.put(msg)
                if self.is_bondmessage_start_tag(message_str):
                    attributes = self.parse_bondmessage_start_tag(message_str)
                    if 'id' in attributes and 'thread_id' in attributes:
                        self.current_thread_ids.append(attributes['thread_id'])
                        self.current_message_ids.append(attributes['id'])                
                        LOGGER.debug(f"Received XML start message[{attributes['id']}]")
                        self.send_string(message_str)
                    else:
                        raise ValueError(f"Invalid bondmessage tag: {message_str}")
                elif self.is_bondmessage_end_tag(message_str):
                    LOGGER.debug(f"End of XML message")
                    self.send_string(message_str)
                    self.current_thread_ids.pop()
                    self.current_message_ids.pop()
                else:
                    # this is just a bare string
                    self.send_string(message_str)

            except zmq.Again:
                # TODO: may want to add a sleep here
                time.sleep(0.1)
            except Exception as e:
                failed_msg = ""
                if message_str is not None:
                    failed_msg = f"Failed message: {message_str[0:100]}"
                LOGGER.error(f"Error processing message -> {failed_msg}", exc_info=e)

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
        self.pub_socket.bind(self.get_pub_address())

        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.bind(self.get_sub_address())
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
    def get_pub_address(cls):
        return os.environ.get("BROKER_PUB_ADDRESS", "tcp://localhost:5555")
    
    @classmethod
    def get_sub_address(cls):
        return os.environ.get("BROKER_SUB_ADDRESS", "tcp://localhost:5556")

    @classmethod
    def connect(cls):
        return BondBrokerConnection(pub_address=cls.get_sub_address(), sub_address=cls.get_pub_address())


    



