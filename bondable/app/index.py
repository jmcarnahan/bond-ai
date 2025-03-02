import streamlit as st
from bondable.bond.pages import Pages
from bondable.bond.threads import Threads
from bondable.app.threads_page import ThreadsPage
import logging
import os
import re
from streamlit_google_auth import Authenticate
from dotenv import load_dotenv


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
            cookie_name=os.getenv('GOOGLE_AUTH_COOKIE_NAME', "__bond_ai_name"),
            cookie_key=os.getenv('GOOGLE_AUTH_COOKIE_KEY', '__bond_ai_key'),
            redirect_uri=os.getenv('GOOGLE_AUTH_REDIRECT_URI'),
        )
    return st.session_state['authenticator']


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
    agent_pages = Pages.pages().get_pages()

    account = []
    account.append(st.Page(create_home_page(name=name, pages=agent_pages), title="Home"))
    account.append(st.Page(create_threads_page(), title="Threads"))
    pages["Account"] = account

    # thread_id = config.get_threads().get_current_thread_id()
    pages["Agents"] = [st.Page(display_page(page), title=page.get_name()) for page in agent_pages]
    return pages

def main (name, email):
    LOGGER.info("Using app without login")
    pages = main_pages(name, email)
    pg = st.navigation(pages)
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
    pg.run()
    

if __name__ == "__main__":
    st.set_page_config(page_title="Home", layout="wide")
    if os.getenv('AUTH_ENABLED', "True").lower() == "true":
        login_main()
    else:
        main("", "Guest")



