import streamlit as st
from bond_ai.bond.threads import Threads
from bond_ai.bond.agent import Agent, AgentResponseHandler
from typing_extensions import override
import base64



class ChatPage(AgentResponseHandler):

    agent: Agent = None
    title: str = None
    threads: Threads = None

    def __init__(self, agent, title, threads):
        self.agent = agent
        self.title = title
        self.threads = threads
        self.messages_key = None

    def display_chat_message(self, content, type, role):
        with st.chat_message(role):
            if type == "text":
                st.markdown(content)
            elif type == "image_file":
                if isinstance(content, str) and content.startswith('data:image/png;base64,'):
                    base64_image = content[len('data:image/png;base64,'):]
                    image_data = base64.b64decode(base64_image)
                    st.image(image_data)
                else:
                    st.image(content)

    @override
    def on_content(self, content, id, type, role):
        self.display_chat_message(content, type, role)
        st.session_state[self.messages_key][id] = {"content": content, "id": id, "type": type, "role": role}

    @override
    def on_done(self, success=True, message=None):
        st.rerun()

    def display_chatbot(self, thread_id):

        st.markdown(f"## {self.title}")
        self.messages_key = f"{self.threads.user_id}-{thread_id}-messages"

        if self.messages_key not in st.session_state:
            st.session_state[self.messages_key] = self.threads.get_messages(thread_id)

        if prompt := st.chat_input("What's up?"):
            user_message = self.agent.create_user_message(prompt, thread_id)
            st.session_state[self.messages_key][user_message.id] = {"content": prompt, "id": user_message.id, "type": 'text', "role": 'user'}
            for id, message in st.session_state[self.messages_key].items():
                self.display_chat_message(message['content'], message['type'], message['role'])            
            self.agent.handle_response(None, thread_id, self)
        else:
            for id, message in st.session_state[self.messages_key].items():
                self.display_chat_message(message['content'], message['type'], message['role'])




        
                    


