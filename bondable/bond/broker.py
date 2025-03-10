import logging
import queue
import re
from bondable.bond.cache import bond_cache

LOGGER = logging.getLogger(__name__)


class BondMessageClob:
    
    def __init__(self, content=None):
        if content is not None:
            self.queue = None
            self.content = content
        else:
            self.queue = queue.Queue()
            self.content = ""

    def generate(self):        
        while True:
            try:
                if self.queue is None:
                    break
                text = self.queue.get(timeout=5)
                if text is None:
                    break
                self.content += text
                yield text
            except queue.Empty:
                continue

    def put(self, text):
        if self.is_closed():
            raise ValueError("Cannot put to closed clob")
        self.queue.put(text)

    def close(self):
        if self.is_closed():
            return
        
        self.queue.put(None)
        while not self.queue.empty():
            chunk = self.queue.get()
            if chunk is not None:
                self.content += chunk
            else:
                break
        self.queue = None

    def is_closed(self):
        return self.queue is None

    def get_content(self) -> str:
        if not self.is_closed():
            for chunk in self.generate():
                pass
            self.close()
        return self.content


class BondMessage:

    thread_id: str
    message_id: str
    type: str
    role: str
    is_error: bool = False
    is_done: bool = False
    clob: BondMessageClob = None

    def __init__(self, thread_id, message_id, type, role, is_error=False, is_done=False, content=None):
        self.message_id = message_id
        self.thread_id = thread_id
        self.type = type
        self.role = role
        self.is_error = is_error
        self.is_done = is_done
        self.clob = BondMessageClob(content=content)

    def __str__(self):
        return f"Message thread[{self.thread_id}] message[{self.message_id}]"

    def to_start_xml(self):
        return f'<_bondmessage id="{self.message_id}" thread_id="{self.thread_id}" type="{self.type}" role="{self.role}" is_error="{self.is_error}" is_done="{self.is_done}">'
    
    def to_end_xml(self):
        return '</_bondmessage>'

class BrokerConnectionEmpty(Exception):
    pass

class BrokerConnection:

    def __init__(self, broker, thread_id, subscriber_id):
        self.thread_id = thread_id
        self.subscriber_id = subscriber_id
        self.msg_queue = queue.Queue()
        self.current_msg: BondMessage = None
        self.broker = broker
        LOGGER.debug(f"Created connection with queue")

    def is_bondmessage_start_tag(self, message:str):
        pattern = r'^<\s*_bondmessage(?:\s+[\w:-]+="[^"]*")*\s*/?>$'
        return bool(re.match(pattern, message.strip()))

    def parse_bondmessage_start_tag(self, message:str):
        pattern = r'^<\s*_bondmessage(?:\s+([\w:-]+)="([^"]*)")*\s*/?>$'
        if not re.match(pattern, message.strip()):
            return None  
        attributes = dict(re.findall(r'([\w:-]+)="([^"]*)"', message))
        return attributes
    
    def is_bondmessage_end_tag(self, message:str):
        pattern = r'^</\s*_bondmessage\s*>$'
        return bool(re.match(pattern, message.strip()))
    
    def publish(self, message:str):
        if self.is_bondmessage_start_tag(message):
            LOGGER.debug(f"Received start message: {message[0:200]}")
            if self.current_msg is not None:
                raise ValueError(f"Received new message before closing previous message: {message}")
            attributes = self.parse_bondmessage_start_tag(message)
            self.current_msg = BondMessage(
                thread_id=attributes.get('thread_id'),
                message_id=attributes.get('id'),
                type=attributes.get('type'),
                role=attributes.get('role'),
                is_error=str(attributes.get('is_error')).lower() == 'true',
                is_done=str(attributes.get('is_done')).lower() == 'true'
            )
            self.msg_queue.put(self.current_msg)
        elif self.is_bondmessage_end_tag(message):
            LOGGER.debug(f"Received end message")
            if self.current_msg is None:
                raise ValueError(f"Received end message before start message: {message}")
            self.current_msg.clob.close()
            self.current_msg = None
        else:
            LOGGER.debug(f"Received body message")
            self.current_msg.clob.put(message)
            
    def stop(self):
        self.msg_queue.put(None)

    def close(self):
        self.stop()
        self.broker.disconnect(thread_id=self.thread_id, subscriber_id=self.subscriber_id)

    def wait_for_message(self, timeout=5) -> BondMessage:
        try:
            message = self.msg_queue.get(timeout=timeout)
            if message is None:
                LOGGER.debug(f"Received STOP message")
                return None
            else:
                LOGGER.debug(f"Received message: {message}")
                return message
        except queue.Empty:
            raise BrokerConnectionEmpty("No message received")

class Broker:
    # This needs to be a singleton
    # TODO: can route this through ZMQ later

    def __init__(self):
        self.topics = {} # thread_id -> subscriber_id -> connection]
        LOGGER.info("Created Broker instance")

    @classmethod
    @bond_cache
    def broker(cls):
        return Broker()

    def stop(self):
        for thread_id, conns in self.topics.items():
            for subscriber_id, connection in conns.items():
                connection.stop()
        LOGGER.info("Closed all connections")
        self.topics = {}

    def publish(self, thread_id, message):
        if thread_id in self.topics:
            for subscriber_id, connection in self.topics[thread_id].items():
                connection.publish(message)
        else:
            LOGGER.warning(f"Thread {thread_id} not found - no subscribers")

    def connect(self, thread_id, subscriber_id) -> BrokerConnection:
        if thread_id not in self.topics:
            self.topics[thread_id] = {}
        if subscriber_id not in self.topics[thread_id]:
            self.topics[thread_id][subscriber_id] = BrokerConnection(broker=self, thread_id=thread_id, subscriber_id=subscriber_id)
        return self.topics[thread_id][subscriber_id]
    
    def disconnect(self, thread_id, subscriber_id):
        if thread_id in self.topics and subscriber_id in self.topics[thread_id]:
            del self.topics[thread_id][subscriber_id]
        else:
            LOGGER.warning(f"Thread {thread_id} not found - no subscribers")

        

    



