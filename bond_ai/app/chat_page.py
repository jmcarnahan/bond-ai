import streamlit as st
import queue
from bond_ai.bond.threads import Threads
from bond_ai.bond.agent import Agent
from bond_ai.bond.broker import AgentResponseMessage
from typing_extensions import override
import base64
import logging
import threading

LOGGER = logging.getLogger(__name__)


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


    def display_chat_message(self, content, type, role):
        with st.chat_message(role):
            if type == "text":
                if content.strip() == "" or content.strip().startswith("__FILE__"):
                    return
                st.markdown(content)
            elif type == "image_file":
                if isinstance(content, str) and content.startswith('data:image/png;base64,'):
                    base64_image = content[len('data:image/png;base64,'):]
                    image_data = base64.b64decode(base64_image)
                    st.image(image_data)
                else:
                    st.image(content)


    def display_chatbot(self):

        st.markdown(f"## {self.title}")

        if self.messages_key not in st.session_state:
            st.session_state[self.messages_key] = self.threads.get_messages(self.thread_id)
            LOGGER.debug(f"Retrieved {len(st.session_state[self.messages_key])} initial messages for thread {self.thread_id}")
            
        for id, message in st.session_state[self.messages_key].items():
            self.display_chat_message(message['content'], message['type'], message['role'])

        if prompt := st.chat_input("What's up?"):
            message = self.agent.create_user_message(prompt, self.thread_id)
            st.session_state[self.messages_key][message.id] = {"content": prompt, "id": message.id, "type": 'text', "role": 'user'}
            thread = threading.Thread(target=self.agent.handle_response, args=(None, self.thread_id))
            thread.start()
            st.rerun()

        # cannot use callbacks here because of the nature of threading in streamlit
        message:AgentResponseMessage = self.message_queue.get()
        st.session_state[self.messages_key][message.id] = {"content": message.content, "id": message.id, "type": message.type, "role": message.role}
        LOGGER.debug(f"Received message {message.id}: {message.content[0:20]}")
        st.rerun()




        
                    


