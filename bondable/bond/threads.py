import io
import socket
import json
from PIL import Image
import base64
from bondable.bond.config import Config
from bondable.bond.metadata import Metadata
from bondable.bond.broker import BondMessage
from bondable.bond.broker import Broker
from bondable.bond.cache import bond_cache
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

class Threads:
     
    user_id: str = None

    def __init__(self, user_id):
        self.user_id = user_id
        self.config = Config.config()
        self.metadata = Metadata.metadata()
        self.broker = Broker.broker()
        LOGGER.info(f"Created new threads instance for user: ({self.user_id})")

    @classmethod
    @bond_cache
    def threads(cls, user_id):
        return Threads(user_id=user_id)

    def close(self):
        pass

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

    def get_current_thread_id(self, session) -> str:
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
    
    def has_messages(self, thread_id, last_message_id) -> bool:
        response = self.config.get_openai_client().beta.threads.messages.list(thread_id, limit=1, after=last_message_id)
        return not response.data

    def get_messages(self, thread_id, limit=100) -> dict:
        response_msgs = []
        messages = self.config.get_openai_client().beta.threads.messages.list(thread_id=thread_id, limit=limit, order="asc")
        for message in messages.data:
            part_idx = 0

            metadata = message.metadata
            if metadata is not None and "override_role" in metadata:
                message.role = metadata["override_role"]

            for part in message.content:
                LOGGER.debug(f"Processing message part: {str(part)}")
                part_id = f"{message.id}_{part_idx}"
                if part.type == "text":
                    response_msgs.append(BondMessage(thread_id=thread_id, message_id=part_id, type=part.type, role=message.role, content=part.text.value))
                elif part.type == "image_file":
                    image_content = self.config.get_openai_client().files.content(part.image_file.file_id)
                    data_in_bytes = image_content.read()
                    readable_buffer = io.BytesIO(data_in_bytes)
                    img_src = 'data:image/png;base64,' + base64.b64encode(readable_buffer.getvalue()).decode('utf-8')
                    # data_in_bytes = response_content.read()
                    # readable_buffer = io.BytesIO(data_in_bytes)
                    # image = Image.open(readable_buffer)
                    response_msgs.append(BondMessage(thread_id=thread_id, message_id=part_id, type=part.type, role=message.role, content=img_src))
                part_idx += 1
        return {message.message_id: message for message in response_msgs}

    # def get_messages(self, thread_id):
    #     response_msgs = []
    #     messages = self.openai_client.beta.threads.messages.list(
    #         thread_id=thread_id
    #     )
    #     for message in reversed(messages.data):
    #         part_idx = 0

    #         metadata = message.metadata
    #         if metadata is not None and "override_role" in metadata:
    #             message.role = metadata["override_role"]

    #         for part in message.content:
    #             part_idx += 1
    #             part_id = f"{message.id}_{part_idx}"
    #             if part.type == "text":
    #                 response_msgs.append({"id": part_id, "role": message.role, "content": part.text.value})
    #             elif part.type == "image_file":
    #                 response_content = self.openai_client.files.content(part.image_file.file_id)
    #                 data_in_bytes = response_content.read()
    #                 readable_buffer = io.BytesIO(data_in_bytes)
    #                 image = Image.open(readable_buffer)
    #                 response_msgs.append({"id": part_id, "role": message.role, "content": image})
    #     return response_msgs


    def delete_thread(self, thread_id) -> None:
        self.config.get_openai_client().beta.threads.delete(thread_id=thread_id)
        self.metadata.delete_thread(thread_id=thread_id)

    def get_thread(self, thread_id):
        return self.metadata.get_thread(thread_id=thread_id)







