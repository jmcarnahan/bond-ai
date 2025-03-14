import logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO, 
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)


import streamlit as st
from bondable.bond.pages import Pages
from bondable.bond.threads import Threads
from bondable.app.threads_page import ThreadsPage
from bondable.app.auth import StreamlitAuth
import os
import re
from dotenv import load_dotenv

load_dotenv()


def display_page(page): 
    def dynamic_function():
        return page.display()
    dynamic_function.__name__ = page.get_id()
    return dynamic_function

def create_home_page(name="", pages=[]):
    def home_page():

        st.session_state['clear_thread'] = False

        # header_cols = st.columns([1, 0.2])
        # with header_cols[0]:
        #     st.markdown(f"### Welcome {name}")
        # with header_cols[1]:
        #     if name != "":
        #         if st.button('Log out'):
        #             get_authenticator().logout()


        cols = st.columns(3)
        idx = 0
        for page in pages:
            with cols[idx % 3]:
                with st.container(height=200, border=True):
                    if st.button(label=page.get_name(), key=page.get_id()):
                        # TODO: change this to a query param once that is available in streamlit
                        st.session_state['clear_thread'] = True
                        st.switch_page(st.Page(display_page(page)))
                    if page.get_description() is not None:
                        st.markdown(f"{page.get_description()}")
                idx += 1

            LOGGER.debug(f"Home card: {page.get_name()} {page.get_id()}")

        # reset the page thread to the current thread everytime we show the home page
        # user_id = st.session_state['user_id']   
        # thread_id = Threads.threads(user_id=user_id).get_current_thread_id(session=st.session_state)
        # st.session_state['page_thread'] = thread_id

    return home_page

def create_threads_page():
    page = ThreadsPage()
    def threads_page():
        st.session_state['clear_thread'] = False
        return page.display_threads()
    return threads_page

def create_logout_page(auth: StreamlitAuth):
    def logout_page():
        if st.button("Logout"):
            st.session_state["user"] = None
            auth.delete_cookie()
            st.rerun()
    return logout_page

def create_google_login_page(auth: StreamlitAuth):
    def login_page():
        st.title("Login")
        LOGGER.debug("User is not logged in")
        st.write("Click the button below to log in:")
        auth_url = auth.get_auth_url()

        st.markdown(f"""
    <a href="{auth_url}" target="_self">
        <img src="https://developers.google.com/identity/images/btn_google_signin_dark_normal_web.png" width="200">
    </a>
    """, unsafe_allow_html=True)
    return login_page


def main_pages(auth: StreamlitAuth, name, user_id):
    pages = {}

    st.session_state['user_id'] = user_id
    agent_pages = Pages.pages().get_pages()

    account = []
    account.append(st.Page(create_home_page(name=name, pages=agent_pages), title="Home"))
    account.append(st.Page(create_threads_page(), title="Threads"))
    account.append(st.Page(create_logout_page(auth=auth), title="Logout"))
    pages["Account"] = account

    # thread_id = config.get_threads().get_current_thread_id()
    pages["Agents"] = [st.Page(display_page(page), title=page.get_name()) for page in agent_pages]
    return pages

def main (name, email):
    LOGGER.info("Using app without login")
    pages = main_pages(name, email)
    pg = st.navigation(pages)
    pg.run()

def login_main(auth: StreamlitAuth):
    pages = {}
    if auth.bond_login():
        LOGGER.info(f"Logged in: {st.session_state['user']['name']}")
        pages = main_pages(auth=auth, name=st.session_state["user"]['name'], user_id=st.session_state["user"]['email'])
    else:
        LOGGER.debug(f"Showing login page")
        pages = {'Login': [st.Page(create_google_login_page(auth), title="Login")]}

    LOGGER.debug(f"Starting app with pages: {pages}")
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    st.set_page_config(page_title="Home", layout="wide")
    auth: StreamlitAuth = StreamlitAuth.auth()
    if os.getenv('AUTH_ENABLED', "True").lower() == "true":
        login_main(auth)
    else:
        main("", "Guest")


