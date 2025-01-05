import streamlit as st
# import io
# import json
# from PIL import Image
# from config import Config
# from functions import Functions
# from threads import Threads
# from agent import Agent, AgentResponseHandler
# from typing_extensions import override
# import base64
from app.dashboard_data import DashboardData



class Dashboard():

    def __init__(self, threads):
        self.threads = threads
        self.dashboard_data = DashboardData(threads)


    # agent: Agent = None
    # title: str = None
    # threads: Threads = None

    # def __init__(self, assistant_id, title, threads):
    #     if 'functions' not in st.session_state:
    #         st.session_state['functions'] = Functions()
    #     self.agent = Agent(assistant_id=assistant_id, functions=st.session_state['functions'])
    #     self.title = title
    #     self.threads = threads
    #     self.messages_key = None

    # def display_chat_message(self, content, type, role):
    #     with st.chat_message(role):
    #         if type == "text":
    #             st.markdown(content)
    #         elif type == "image_file":
    #             if isinstance(content, str) and content.startswith('data:image/png;base64,'):
    #                 base64_image = content[len('data:image/png;base64,'):]
    #                 image_data = base64.b64decode(base64_image)
    #                 st.image(image_data)
    #             else:
    #                 st.image(content)

    # @override
    # def on_content(self, content, id, type, role):
    #     self.display_chat_message(content, type, role)
    #     st.session_state[self.messages_key][id] = {"content": content, "id": id, "type": type, "role": role}

    def display(self):

        # st.markdown(f"## {self.title}")
        thread_id = None
        if 'thread' in st.session_state:
            thread_id = st.session_state['thread']

        with st.expander("Data Description", expanded=True):
            with st.container(height=300, border=False):
                self.dashboard_data.display(thread_id=thread_id)

        # Create the bottom panel
        with st.container():
            st.markdown("## Bottom Panel")
            st.write("This is the bottom panel of the app.")
            st.button("Bottom Panel Button")


        # thread_id = self.threads.get_current_thread_id()
        # self.messages_key = f"{self.threads.user_id}-{thread_id}-messages"

        # # Initialize chat history
        # if self.messages_key not in st.session_state:
        #     st.session_state[self.messages_key] = self.threads.get_messages(thread_id)
        
        # for message in st.session_state[self.messages_key].values():
        #     self.display_chat_message(message['content'], message['type'], message['role'])

        # if prompt := st.chat_input("What is up?"):
        #     user_message = self.agent.create_user_message(prompt, thread_id)
        #     st.session_state[self.messages_key][id] = {"content": prompt, "id": user_message.id, "type": 'text', "role": 'user'}
        #     self.display_chat_message(prompt, 'text', 'user')
        #     self.agent.handle_response(prompt, thread_id, self)




        
                    


