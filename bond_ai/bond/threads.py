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

LOGGER = logging.getLogger(__name__)




class Threads:
     
    user_id: str = None

    def __init__(self, user_id, config: Config):
        self.user_id = user_id
        self.config = config
        self.metadata = self.config.get_metadata()

        # port = self.find_unused_port()
        # self.address = f"tcp://localhost:{port}"
        # broker_address = os.environ.get("BROKER_ADDRESS", "tcp://localhost:5555")

        # self.pub_context = zmq.Context()
        # self.pub_socket = self.pub_context.socket(zmq.PUB)
        # self.pub_socket.connect(broker_address)

        # self.sub_context = zmq.Context()
        # self.sub_socket = self.sub_context.socket(zmq.SUB)
        # self.sub_socket.bind(self.address)
        # self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.conn: BondBrokerConnection = BondBroker.connect()
        self.conn.start()
        # self.stop_event = threading.Event() 
        # self.callback_thread = threading.Thread(target=self.listen, daemon=True)
        # self.callback_thread.start()
        # LOGGER.debug(f"Threads initialized for user {self.user_id} - listening on {self.address} and sending to {broker_address}")

    # def find_unused_port(self):
    #     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    #         s.bind(("", 0)) 
    #         return s.getsockname()[1] 

    # def __del__(self):
    #     self.close()
        # if not self.stop_event.is_set():
        #     self.close()

    def close(self):
        self.conn.stop()
        # self.stop_event.set()
        # if self.callback_thread.is_alive():
        #     self.callback_thread.join()
        # LOGGER.debug(f"Threads closed for user {self.user_id}")
        # self.pub_socket.close(linger=0)
        # self.pub_context.term()
        # self.sub_socket.close(linger=0)
        # self.sub_context.term()

    # def listen(self):
    #     while not self.stop_event.is_set():
    #         try:
    #             message_str = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
    #             agent_msg = AgentResponseMessage.model_validate_json(message_str)
    #             if agent_msg.thread_id in self.callbacks:
    #                 for callback_id, callback in self.callbacks[agent_msg.thread_id].items():
    #                     callback(agent_msg)
    #                 LOGGER.debug(f"Callbacks: ({agent_msg.role}) message for thread {agent_msg.thread_id} to {len(self.callbacks[agent_msg.thread_id])} callbacks")
    #             else:
    #                 LOGGER.warning(f"No callback for thread {agent_msg.thread_id}")
    #         except zmq.Again:
    #             # TODO: may want to add a sleep here
    #             time.sleep(0.1)
    #         except Exception as e:
    #             LOGGER.error(f"Error processing message: {e}")



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
    
    def get_messages(self, thread_id, limit=20) -> dict:
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
        # message_str = message.model_dump_json()
        # self.pub_socket.send_string(message_str)

    def subscribe(self, thread_id) -> queue.Queue:
        subscriber_id = f"{self.user_id}.{thread_id}"
        return self.conn.subscribe(thread_id, subscriber_id)

    def unsubscribe(self, thread_id) -> bool:
        subscriber_id = f"{self.user_id}.{thread_id}"
        return self.conn.unsubscribe(thread_id, subscriber_id)



    # def create_listener(self, thread_id, callback):
    #     if thread_id not in self.callbacks:
    #         self.callbacks[thread_id] = {}
    #     callback_id = f"{self.user_id}.{thread_id}.{callback.__module__}.{callback.__qualname__}"
    #     if callback_id not in self.callbacks[thread_id]:
    #         self.callbacks[thread_id][callback_id] = callback
    #         msg = AgentSubscribeMessage(thread_id=thread_id, subscriber_id=callback_id, zmq_address=self.address)
    #         self.pub_socket.send_string(msg.model_dump_json())
    #         LOGGER.debug(f"Subscribing to thread {thread_id} at {self.address} with callback {callback_id}")
    #     else:
    #         LOGGER.debug(f"Callback {callback_id} already exists for thread {thread_id}")
    #     return callback_id
    
    # def delete_listener(self, thread_id, callback_id):
    #     if thread_id in self.callbacks:
    #         if callback_id in self.callbacks[thread_id]:
    #             del self.callbacks[thread_id][callback_id]
    #             msg = AgentUnsubscribeMessage(thread_id=thread_id, subscriber_id=callback_id)
    #             self.pub_socket.send_string(msg.model_dump_json())
    #             return True
    #     return False





