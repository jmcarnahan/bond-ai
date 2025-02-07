import io
import socket
import json
import zmq
from PIL import Image
from bond_ai.bond.config import Config
from bond_ai.bond.broker import AgentResponseMessage, BondBroker, BondBrokerConnection
import logging
import os
import threading
import time
import uuid
import queue
import re
from xml.sax import ContentHandler, make_parser
from xml.sax.xmlreader import XMLReader
from abc import ABC, abstractmethod

LOGGER = logging.getLogger(__name__)

START_MSG_PATTERN = r'^<\s*_bondmessage(?:\s+[\w:-]+="[^"]*")*\s*/?>$'
PARSE_MSG_PATTERN = r'^<\s*_bondmessage(?:\s+([\w:-]+)="([^"]*)")*\s*/?>$'
END_MSG_PATTERN   = r'^</\s*_bondmessage\s*>$'
ATTR_MSG_PATTERN  = r'([\w:-]+)="([^"]*)"'

class ThreadMessageHandler(ABC):

    @abstractmethod
    def onMessage(self, thread_id, message_id, type, role, is_error=False, is_done=False, clob=None):
        pass

class ThreadMessageTextGenerator:
    
    def __init__(self, content=None):
        self.queue = queue.Queue()
        self.content = content
        self.running = content is None

    def generate(self):
        self.running = True
        self.content = ""
        while True:
            try:
                text = self.queue.get(timeout=5)
                if text is None:
                    break
                self.content += text
                yield text
            except queue.Empty:
                continue

    def put(self, text):
        self.queue.put(text)

    def close(self):
        if self.content is None:
            self.content = ""
        while not self.queue.empty():
            chunk = self.queue.get()
            if chunk is not None:
                self.content += chunk
            else:
                break
        self.running = False

    def is_closed(self):
        return not self.running

    def get_content(self):
        if self.running:
            self.close()
        return self.content


class ThreadMessageParser:
        
    def __init__(self, handler:ThreadMessageHandler):
        self.running = True
        self.handler = handler
        LOGGER.info(f"Starting parser {id(self)} with handler {id(handler)}")
        
    def stop(self):
        self.running = False

    def is_bondmessage_start_tag(self, message_str:str):
        return bool(re.match(START_MSG_PATTERN, message_str.strip()))

    def parse_bondmessage_start_tag(self, message_str:str):
        if not re.match(PARSE_MSG_PATTERN, message_str.strip()):
            return None  
        attributes = dict(re.findall(ATTR_MSG_PATTERN, message_str))
        return attributes
    
    def is_bondmessage_end_tag(self, message_str:str):
        return bool(re.match(END_MSG_PATTERN, message_str.strip()))
    
    def generate_text(self, xml_queue:queue.Queue, sink:ThreadMessageTextGenerator):
       while self.running:
            xml_chunk = None
            try:
                xml_chunk = xml_queue.get(timeout=5)
                if xml_chunk is None:  # Stop signal
                    break
                if self.is_bondmessage_end_tag(xml_chunk):
                    sink.put(None)
                    return
                else:
                    sink.put(xml_chunk)
            except queue.Empty:
                continue
            except Exception as e:
                LOGGER.error(f"Error parsing chunk: {xml_chunk}", exc_info=e)


    def parse(self, xml_queue:queue.Queue):
        LOGGER.info(f"Continuing parser {id(self)} with queue {id(xml_queue)} and handler {id(self.handler)}")
        while self.running:
            xml_chunk = None
            try:
                xml_chunk = xml_queue.get(timeout=5)
                LOGGER.debug(f"Got chunk: {xml_chunk}")
                if xml_chunk is None:  # Stop signal
                    break
                if self.is_bondmessage_start_tag(xml_chunk):
                    attributes = self.parse_bondmessage_start_tag(xml_chunk)
                    if 'id' in attributes and 'thread_id' in attributes:
                        gen = ThreadMessageTextGenerator()
                        # start generating the text
                        thread = threading.Thread(target=self.generate_text, args=(xml_queue, gen))
                        thread.start()
                        # on message will block until complete
                        self.handler.onMessage(thread_id=attributes['thread_id'], 
                                                    message_id=attributes['id'], 
                                                    type=attributes.get('type', 'text'), 
                                                    role=attributes.get('role', 'user'),
                                                    is_error=attributes.get('is_error', 'false').lower() == 'true',
                                                    is_done=attributes.get('is_done', 'false').lower() == 'true',
                                                    clob=gen)

                    else:
                        LOGGER.error(f"Invalid bondmessage tag: {xml_chunk}")
                else:
                    LOGGER.error(f"Unexpected XML chunk: {xml_chunk}")
            except queue.Empty:
                continue
            except Exception as e:
                LOGGER.error(f"Error parsing chunk: {xml_chunk}", exc_info=e)

class Threads:
     
    user_id: str = None

    def __init__(self, user_id, config: Config):
        self.user_id = user_id
        self.config = config
        self.metadata = self.config.get_metadata()

        self.conn: BondBrokerConnection = BondBroker.connect()
        self.conn.start()

    def close(self):
        self.conn.stop()

    def get_user_id(self):
        return self.user_id

    def update_thread_name(self, thread_id) -> str:
        thread_name = "New Thread"
        messages = self.config.get_openai_client().beta.threads.messages.list(thread_id=thread_id, limit=1, order="asc")
        if len(messages.data) > 0:
            thread_name = messages.data[0].content[0].text.value.replace("\'", " ")
            self.metadata.update_thread_name(thread_id=thread_id, thread_name=thread_name)
        return thread_name
    
    def get_current_threads(self, count=10) -> list:
        thread_list = self.metadata.get_current_threads(user_id=self.user_id, count=count)
        for thread in thread_list:
            if thread['name'] == None or thread['name'] == "":
                thread['name'] = self.update_thread_name(thread_id=thread['thread_id'])
        return thread_list

    def create_thread(self) -> str:
        thread = self.config.get_openai_client().beta.threads.create()
        return self.metadata.grant_thread(thread_id=thread.id, user_id=self.user_id, fail_if_missing=False)

    
    def get_current_thread_id(self) -> str:
        session = self.config.get_session()
        if 'thread' not in session:
            threads = self.get_current_threads(count=1)
            if len(threads) > 0:
                session['thread'] = threads[0]['thread_id']
            else:
                session['thread'] = self.create_thread()
        return session['thread']
    
    def grant_thread(self, thread_id, user_id=None) -> str:
        if user_id is None:
            user_id = self.user_id
        thread_id = self.metadata.grant_thread(thread_id=thread_id, user_id=user_id, fail_if_missing=True)
        LOGGER.info(f"Granted thread {thread_id} to user {user_id}")
        return thread_id
    
    def get_messages(self, thread_id, limit=100) -> dict:
        response_msgs = []
        messages = self.config.get_openai_client().beta.threads.messages.list(thread_id=thread_id, limit=limit, order="asc")
        for message in messages.data:
            part_idx = 0
            for part in message.content:
                part_idx += 1
                part_id = f"{message.id}_{part_idx}"
                if part.type == "text":
                    response_msgs.append({"id": part_id, "type": part.type, "role": message.role, "content": part.text.value})
                elif part.type == "image_file":
                    response_content = self.config.get_openai_client().files.content(part.image_file.file_id)
                    data_in_bytes = response_content.read()
                    readable_buffer = io.BytesIO(data_in_bytes)
                    image = Image.open(readable_buffer)
                    response_msgs.append({"id": part_id, "type": part.type, "role": message.role, "content": image})
        return {message['id']: message for message in response_msgs}

    def delete_thread(self, thread_id) -> None:
        self.config.get_openai_client().beta.threads.delete(thread_id=thread_id)
        self.metadata.delete_thread(thread_id=thread_id)

    def get_thread(self, thread_id):
        return self.metadata.get_thread(thread_id=thread_id)

    def notify(self, message:AgentResponseMessage) -> str:
        self.conn.publish(message)

    def put(self, content) -> str:
        self.conn.put(content)

    def subscribe(self, thread_id) -> queue.Queue:
        subscriber_id = f"{self.user_id}.{thread_id}"
        return self.conn.subscribe(thread_id, subscriber_id)
    
    def unsubscribe(self, thread_id) -> bool:
        subscriber_id = f"{self.user_id}.{thread_id}"
        return self.conn.unsubscribe(thread_id, subscriber_id)






