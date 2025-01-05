import streamlit as st
from bond_ai.bond.threads import Threads


class ThreadsPage:
     
    def __init__(self, threads):
        self.threads = threads

    def get_current_thread_id(self):
        if 'thread' not in st.session_state:
            threads = self.threads.get_current_threads(count=1)
            if len(threads) > 0:
                st.session_state['thread'] = threads[0]['thread_id']
            else:
                st.session_state['thread'] = self.threads.create_thread()
        return st.session_state['thread']

    def display_threads(self):

        st.markdown("## Threads")

        current_thread_id = self.get_current_thread_id()
        if st.button("Create New Thread"):
            thread_id = self.threads.create_thread()
            st.session_state['thread'] = thread_id
            st.rerun()

        for thread in self.threads.get_current_threads():
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if thread['thread_id'] == current_thread_id:
                    st.markdown(f"<span style='color:lightgreen'>{thread['name']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"{thread['name']}")
            with col2:
                st.markdown(f"{thread['origin']}")
            with col3:
                button1, button2 = st.columns([1, 1])
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


