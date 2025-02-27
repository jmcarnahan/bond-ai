import streamlit as st
import queue
from bond_ai.bond.threads import Threads
from bond_ai.bond.agent import Agent
from bond_ai.bond.broker import Broker, BondMessage, BrokerConnectionEmpty
from bond_ai.bond.page import Page
from typing_extensions import override
import base64
import logging
import threading
from io import BytesIO
from PIL import Image
import time

LOGGER = logging.getLogger(__name__)


class ChatPage(Page):

    agent: Agent = None
    title: str = None

    def __init__(self, agent, title):
        self.agent = agent
        self.title = title
        self.displayed_messages = {}

    def get_id(self):
        return self.agent.assistant_id

    def get_name(self):
        return self.title

    def get_description(self):
        return self.agent.description
    
    def catchup(self):
        for message_id, message in self.displayed_messages.items():
            self.display_message(message)

    def display_message(self, message: BondMessage):

        if message.message_id in self.displayed_messages:
            LOGGER.debug(f"Received duplicate message, ignoring {message.message_id}")
            return

        if message.role == 'system':
            LOGGER.debug(f"Received system message, ignoring {message.message_id}")
            return

        if message.type == "text":
            chat_msg = st.chat_message(message.role)
            if message.clob.is_closed():
                chat_msg.write(message.clob.get_content())
            else:
                chat_msg.write_stream(message.clob.generate())
                message.clob.close()
            self.displayed_messages[message.message_id] = message

        elif message.type == "image_file":
            chat_msg = st.chat_message(message.role)
            content = message.clob.get_content()
            if isinstance(content, str) and content.startswith('data:image/png;base64,'):
                base64_image = content[len('data:image/png;base64,'):]
                image_data = base64.b64decode(base64_image)
                image = Image.open(BytesIO(image_data))
                chat_msg.write(image)
            else:
                chat_msg.write(content)
            self.displayed_messages[message.message_id] = message
 
        else:
            LOGGER.error(f"Unknown message type {message.type}")

    # @st.fragment(run_every="1s")
    # def show_new_messages(self, conn):
    #     try:
    #         self.catchup()
    #         response = conn.wait_for_message(timeout=10)
    #         if response is not None:
    #             self.display_message(response)
    #     except BrokerConnectionEmpty:
    #         return

    def run_thread(self, thread_id, conn):
        thread = threading.Thread(target=self.agent.broadcast_response, args=(None, thread_id), daemon=True)
        thread.start()
        while True:
            try:
                response = conn.wait_for_message(timeout=5)
                if response is None:
                    break
                self.display_message(response)
                if response.is_done:
                    break
            except BrokerConnectionEmpty:
                continue
        thread.join()

    def display(self):

        st.markdown(f"## {self.title}")
        threads = Threads.threads(user_id=st.session_state['user_id'])

        clear_thread = st.session_state.get('clear_thread', False)
        if clear_thread:
            thread_id = threads.create_thread()
            st.session_state['thread'] = thread_id
            LOGGER.info(f"Clear thread -> Created new thread: {thread_id}")
            initial_prompt = self.agent.get_metadata_value('initial_prompt')
            if initial_prompt:
                conn = Broker.broker().connect(thread_id=thread_id, subscriber_id=st.session_state['user_id'])
                message = self.agent.create_user_message(initial_prompt, thread_id, role='system')
                self.run_thread(thread_id, conn)
                LOGGER.info(f"Clear thread -> Sent initial prompt: {initial_prompt}")
            st.session_state['clear_thread'] = False        

        thread_id = st.session_state.get('thread', None)
        LOGGER.debug(f"Retrieved thread from session: {thread_id}")
        if thread_id is None:
            thread_id = threads.get_current_thread_id(session=st.session_state)
            LOGGER.debug(f"Using current thread: {thread_id}")

        # TODO: Need to cache these better rather than pull it each time
        existing_messages = threads.get_messages(thread_id)
        LOGGER.debug(f"Retrieved {len(existing_messages)} initial messages for thread {thread_id}")
        for id, message in existing_messages.items():
            self.display_message(message)

        # self.show_new_messages(conn)

        if prompt := st.chat_input("What's up?"):
            conn = Broker.broker().connect(thread_id=thread_id, subscriber_id=st.session_state['user_id'])
            message = self.agent.create_user_message(prompt, thread_id)
            self.run_thread(thread_id, conn)
            # st.rerun()
            





        
                    


