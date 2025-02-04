import streamlit as st
from bond_ai.bond.config import Config
from bond_ai.bond.threads import Threads
from bond_ai.bond.agent import Agent
from bond_ai.app.chat_page import ChatPage
from bond_ai.app.threads_page import ThreadsPage
import logging
import os
import re
from streamlit_google_auth import Authenticate
from dotenv import load_dotenv
import uuid

load_dotenv()

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO, 
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

def get_authenticator():
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = Authenticate(
            secret_credentials_path = os.getenv('GOOGLE_AUTH_CREDS_PATH'),
            cookie_name=os.getenv('GOOGLE_AUTH_COOKIE_NAME'),
            cookie_key=os.getenv('GOOGLE_AUTH_COOKIE_KEY'),
            redirect_uri=os.getenv('GOOGLE_AUTH_REDIRECT_URI'),
        )
    return st.session_state['authenticator']

def create_home_page(name=""):
    def home_page():
        st.markdown("## Home Page")
        st.markdown(f"### Welcome {name}")
        if name != "":
            if st.button('Log out'):
                get_authenticator().logout()
    return home_page

def create_threads_page(config):
    page = ThreadsPage(config)
    def threads_page():
        return page.display_threads()
    return threads_page


def create_google_login_page():
    def login_page():
        authenticator = get_authenticator()
        authenticator.check_authentification()
        authenticator.login()
    return login_page

def create_simple_login_page():
    def process_email():
        email = st.session_state["email_input"]
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            st.session_state['connected'] = True
            st.session_state['user_info'] = {'name': "Guest", 'email': email}
            LOGGER.info(f"Connected as {email}")
        else:
            st.error("Please enter a valid email")

    def login_page():
        #st.markdown("#### Enter your email address")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            email = st.text_input("Enter your email", key="email_input", on_change=process_email)
            if st.button('Enter'):
                process_email()
    return login_page


def main_pages(name, user_id):
    pages = {}

    st.session_state['user_id'] = user_id
    config = Config(session=st.session_state)
    openai_client = config.get_openai_client()
    assistants = openai_client.beta.assistants.list(order="desc",limit="20")
    LOGGER.debug(f"Got assistants: {len(assistants.data)}")

    account = []
    account.append(st.Page(create_home_page(name=name), title="Home"))
    account.append(st.Page(create_threads_page(config=config), title="Threads"))
    pages["Account"] = account

    agent_pages = config.get_pages()
    pages["Agents"] = agent_pages

    return pages

def main (name, email):
    LOGGER.debug("Using app without login")
    pages = main_pages(name, email)
    pg = st.navigation(pages)
    st.set_page_config(page_title="Home", layout="wide")
    pg.run()

def login_main():
    pages = {}
    if 'connected' in st.session_state and st.session_state['connected']:
        name  = st.session_state['user_info'].get('name')
        email = st.session_state['user_info'].get('email')
        pages = main_pages(name, email)
    else:
        if os.getenv('GOOGLE_AUTH_ENABLED', "False").lower() == "true":
            LOGGER.info(f"Starting app with login with redirect: {os.getenv('GOOGLE_AUTH_REDIRECT_URI')}")
            pages = {'Login': [st.Page(create_google_login_page(), title="Login")]}
        else:
            LOGGER.info("Using simple login without google auth")
            pages = {'Login': [st.Page(create_simple_login_page(), title="Login")]}
    pg = st.navigation(pages)
    st.set_page_config(page_title="Home", layout="wide")
    pg.run()



if __name__ == "__main__":
    if os.getenv('AUTH_ENABLED', "True").lower() == "true":
        login_main()
    else:
        main("", "Guest")



