import logging
LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import streamlit as st
import time
from streamlit_cookies_controller import CookieController
from bondable.bond.auth import GoogleAuth




class StreamlitAuth:
    
    def __init__(self):
        self.auth = GoogleAuth.auth()
        self._cookies = None
        LOGGER.info("Starting Streamlit Auth")

    @classmethod
    @st.cache_resource
    def auth(cls):
        return StreamlitAuth()
    
    def get_cookies(self):
        if not self._cookies:
            self._cookies = CookieController()
        return self._cookies

    def set_cookie(self, user_info):
        self.get_cookies().set(name="bond_user_info", value=self.auth.create_cookie(user_info=user_info), max_age=86400, same_site="strict")
        LOGGER.info(f"Set cookie for user: {user_info['name']} {user_info['email']}")
        time.sleep(2)

    def delete_cookie(self):
        if self.get_cookies().get("bond_user_info"):
            self.get_cookies().remove("bond_user_info")
            LOGGER.info("Deleted cookie")
            time.sleep(2)

    def get_auth_url(self):
        return self.auth.get_auth_url()

    def bond_login(self):
        
        LOGGER.debug("Checking login status")
        if "user" not in st.session_state:
            st.session_state["user"] = None

        if st.session_state["user"] is not None:
            user_info = st.session_state["user"]
            self.set_cookie(user_info)
            return True

        if self.get_cookies().get("bond_user_info"):
            user_info = self.auth.get_user_info_from_cookie(self.get_cookies().get("bond_user_info"))
            if user_info is not None:
                st.session_state["user"] = user_info
                return True
            else:
                LOGGER.error(f"Could not get user info from cookie")
                self.delete_cookie()

        if "code" in st.query_params:
            try:
                user_info = self.auth.get_user_info_from_code(st.query_params["code"])
                st.session_state["user"] = user_info
                del st.query_params["code"]
                st.query_params.clear()
                self.set_cookie(user_info)
                return True
            except Exception as e:
                st.error(f"Error logging in: {e}")
                LOGGER.error(f"Error logging in: {e}")
                del st.query_params["code"]
                st.query_params.clear()
        
        return False
















