import logging
LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import os
import base64
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
from google.oauth2 import id_token, credentials
from bondable.bond.cache import bond_cache
from bondable.bond.config import Config
import dotenv

dotenv.load_dotenv()


class GoogleAuth:
    
    def __init__(self):
        config = Config.config()
        self.auth_info = config.get_auth_info()
        LOGGER.debug(f"Google Auth initialized: redirect_uri={self.auth_info['redirect_uri']} scopes={self.auth_info['scopes']}")

    @classmethod
    @bond_cache
    def auth(cls):
        return GoogleAuth()

    def _get_flow(self):
        return Flow.from_client_config(
            client_config=self.auth_info['auth_creds'],
            scopes=self.auth_info['scopes'],
            redirect_uri=self.auth_info['redirect_uri']
        )
    
    def get_auth_url(self):
        authorization_url, state = self._get_flow().authorization_url(
            # Recommended, enable offline access so that you can refresh an access token without
            # re-prompting the user for permission. Recommended for web server apps.
            access_type='offline',
            # Optional, enable incremental authorization. Recommended as a best practice.
            include_granted_scopes='true',
            # Optional, if your application knows which user is trying to authenticate, it can use this
            # parameter to provide a hint to the Google Authentication Server.
            login_hint='hint@example.com',
            # Optional, set prompt to 'consent' will prompt the user for consent
            prompt='consent')
        return authorization_url

    def _fetch_google_token(self, auth_code):
        flow = self._get_flow()
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        return creds

    def _get_google_user_info(self, creds):
        request = requests.Request()
        user_info = id_token.verify_oauth2_token(creds.id_token, request)
        return user_info
    
    def create_cookie(self, user_info):
      return base64.b64encode(json.dumps(user_info).encode("utf-8")).decode("utf-8")

    def get_user_info_from_cookie(self, cookie):
        try:
            user_info = json.loads(base64.b64decode(cookie).decode("utf-8"))
            LOGGER.info(f"Found user info in cookie: {user_info['name']} {user_info['email']}")
            return user_info
        except Exception as e:
            LOGGER.error(f"Error decoding cookie: {e}")
            return None

    def get_user_info_from_code(self, auth_code):
        try:       
            LOGGER.info(f"Authenticating with auth code: {auth_code}")
            creds = self._fetch_google_token(auth_code)
            user_info = self._get_google_user_info(creds)
            LOGGER.info(f"Authenticated: {user_info['name']} {user_info['email']}")

            if len(self.auth_info['valid_emails']) > 0 and user_info['email'] not in self.auth_info['valid_emails']:
                LOGGER.error(f"Invalid email: {user_info['email']}")
                raise ValueError(f"Cannot authenticate with user {user_info['email']}")

            return user_info
        except Exception as e:
            LOGGER.error(f"Error authenticating with code {auth_code}: {e}")
            raise e






