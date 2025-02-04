import streamlit as st
from bond_ai.bond.threads import Threads
import logging
import re

LOGGER = logging.getLogger(__name__)

class ThreadsPage:
     
    def __init__(self, config):
        self.config = config
        session = config.get_session()
        if 'user_id' not in session:
            raise Exception("No user id provided")
        self.threads = self.config.get_threads()

    def display_threads(self):


        st.markdown("## Threads")
        current_thread_id = self.threads.get_current_thread_id()

        if st.button("Create New Thread"):
            thread_id = self.threads.create_thread()
            st.session_state['thread'] = thread_id
            st.rerun()

        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        for thread in self.threads.get_current_threads():
            
            with col1:
                if thread['thread_id'] == current_thread_id:
                    st.markdown(f"<span style='color:lightgreen'>{thread['name']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"{thread['name']}")
            with col2:
                st.markdown(f"{thread['created_at']}")
            with col3:
                st.markdown(f"{thread['updated_at']}")
            with col4:
                button1, button2, button3 = st.columns([1, 1, 1])
                with button1:
                    if thread['thread_id'] == current_thread_id:
                        st.button(label=f"Select", disabled=True, key=f"Select {thread['thread_id']}")
                    else:
                        if st.button(label=f"Select", key=f"Select {thread['thread_id']}"):
                            st.session_state['thread'] = thread['thread_id']
                            st.rerun()
                with button2:
                    if thread['thread_id'] == current_thread_id:
                        st.button(label=f"Delete", disabled=True, key=f"Delete {thread['thread_id']}")
                    else:
                        if st.button(label=f"Delete", key=f"Delete {thread['thread_id']}"):
                            self.threads.delete_thread(thread['thread_id'])
                            st.rerun()
                with button3:
                    def process_share(thread_id):
                        email = st.session_state.get(f"{thread_id}_share_input", "")
                        LOGGER.info(f"Sharing thread {thread_id} with {email}")
                        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                            self.threads.grant_thread(thread_id=thread_id, user_id=email)
                        else:
                            st.error("Please enter a valid email")
                    with st.popover("Share"):
                        thread_id = thread['thread_id']
                        email = st.text_input("Share this thread with others", 
                                              key=f"{thread_id}_share_input", 
                                              on_change=process_share,
                                              args=(thread_id,))
