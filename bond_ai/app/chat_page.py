import streamlit as st
import queue
from bond_ai.bond.threads import Threads, ThreadMessageParser, ThreadMessageHandler, ThreadMessageTextGenerator
from bond_ai.bond.agent import Agent
from bond_ai.bond.broker import AgentResponseMessage
from typing_extensions import override
import base64
import logging
import threading
from io import BytesIO
from PIL import Image
import time

LOGGER = logging.getLogger(__name__)



class MyThreadMessageHandler(ThreadMessageHandler):

    def __init__(self, messages_key):
        self.messages_key = messages_key

    def set_parser(self, parser:ThreadMessageParser):
        self.parser = parser

    def onMessage(self, thread_id, message_id, type, role, is_error=False, is_done=False, clob=None):
        LOGGER.debug(f"PARSER message: {thread_id} {message_id} {type} {role} {is_error} {is_done}")

        if message_id in st.session_state[self.messages_key]:
            LOGGER.info(f"Received duplicate message, ignoring {message_id}")
            return

        if role == 'system':
            LOGGER.info(f"Received system message, ignoring {message_id}")
            return
        
        if type == "text":
            if clob is not None:
                chat_msg = st.chat_message(role)
                if clob.is_closed():
                    chat_msg.write(clob.get_content())
                else:
                    chat_msg.write_stream(clob.generate())
                    clob.close()
                st.session_state[self.messages_key][message_id] = {"content": clob.get_content(), "id": message_id, "type": type, "role": role}

        elif type == "image_file":
            if clob is not None:
                chat_msg = st.chat_message(role)
                clob.close()
                content = clob.get_content()
                if isinstance(content, str) and content.startswith('data:image/png;base64,'):
                    base64_image = content[len('data:image/png;base64,'):]
                    image_data = base64.b64decode(base64_image)
                    image = Image.open(BytesIO(image_data))
                    chat_msg.write(image)
                else:
                    chat_msg.write(content)
                st.session_state[self.messages_key][message_id] = {"content": clob.get_content(), "id": message_id, "type": type, "role": role}

        else:
            LOGGER.error(f"Unknown message type {type}")


class ChatPage:

    agent: Agent = None
    title: str = None
    threads: Threads = None

    def __init__(self, agent, title, threads, thread_id):
        self.agent = agent
        self.title = title
        self.threads = threads
        self.thread_id = thread_id
        self.messages_key = f"{self.threads.user_id}-{thread_id}-messages"
        self.message_queue = self.threads.subscribe(thread_id=thread_id)
        self.received_message = None

        if "chat-page-parser" not in st.session_state:
            st.session_state["chat-page-parser"] = ThreadMessageParser(MyThreadMessageHandler(messages_key=self.messages_key))


    def display_chatbot(self):

        st.markdown(f"## {self.title}")

        if self.messages_key not in st.session_state:
            st.session_state[self.messages_key] = self.threads.get_messages(self.thread_id)
            LOGGER.debug(f"Retrieved {len(st.session_state[self.messages_key])} initial messages for thread {self.thread_id}")
            
        existing_handler = MyThreadMessageHandler(messages_key=self.messages_key)
        for id, message in st.session_state[self.messages_key].items():
            gen = ThreadMessageTextGenerator(message['content'])
            existing_handler.onMessage(self.thread_id, message['id'], message['type'], message['role'], clob=gen) 
            #self.display_chat_message(message['content'], message['type'], message['role'])
        LOGGER.info(f"Re-rendered {len(st.session_state[self.messages_key])}")  

        if prompt := st.chat_input("What's up?"):
            message = self.agent.create_user_message(prompt, self.thread_id)
            st.session_state[self.messages_key][message.id] = {"content": prompt, "id": message.id, "type": 'text', "role": 'user'}
            thread = threading.Thread(target=self.agent.broadcast_response, args=(None, self.thread_id))
            thread.start()
            st.rerun()

        st.session_state["chat-page-parser"].parse(self.message_queue)






        
                    


