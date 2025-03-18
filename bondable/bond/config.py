import logging
LOGGER = logging.getLogger(__name__)

from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import os
import atexit
import json
import base64
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bondable.bond.cache import bond_cache
import google.auth

load_dotenv()



class Config:
    
    # config should init with a service account
    # this should either be a base64 string or a file 
    # both coming in via a env var
    def __init__(self):        
        try:
            if 'BOND_GCLOUD_SA_CREDS_STRING' in os.environ:
                sa_creds_base64 = os.getenv("BOND_GCLOUD_SA_CREDS_STRING") # this is a bas64 string
                sa_creds = base64.b64decode(sa_creds_base64).decode("utf-8")
                self.credentials = service_account.Credentials.from_service_account_info(json.loads(sa_creds))
                self.gcp_project_id = os.getenv('BOND_GCLOUD_PROJECT_ID', self.credentials.project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)
                LOGGER.info(f"Using GCLOUD credentials from BOND_GCLOUD_SA_CREDS_STRING for project_id: {self.gcp_project_id}")
            elif 'BOND_GCLOUD_SA_CREDS_PATH' in os.environ:
                sa_creds_path = os.getenv('BOND_GCLOUD_SA_CREDS_PATH')
                self.credentials = service_account.Credentials.from_service_account_file(sa_creds_path)
                self.gcp_project_id = os.getenv('BOND_GCLOUD_PROJECT_ID', self.credentials.project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)
                LOGGER.info(f"Using GCLOUD credentials from BOND_GCLOUD_SA_CREDS_PATH for project_id: {self.gcp_project_id}")
            else:
                self.credentials, project_id = google.auth.default()
                self.gcp_project_id = os.getenv('BOND_GCLOUD_PROJECT_ID', project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)
                LOGGER.info(f"Using GCLOUD default credentials for project_id: {self.gcp_project_id}")
        except Exception as e:
            LOGGER.error(f"Error loading GCP credentials: {e}")
            raise e

        openai_api_key = self.get_secret_value(os.getenv('OPENAI_KEY_SECRET_ID', 'openai_api_key'))
        openai_project_id = self.get_secret_value(os.getenv('OPENAI_PROJECT_SECRET_ID', 'openai_project'))

        self.openai_client = OpenAI(api_key=openai_api_key, project=openai_project_id)
        self.openai_deployment = os.getenv('OPENAI_DEPLOYMENT', 'gpt-4o')

        # elif os.getenv('AZURE_OPENAI_API_KEY'):
        #     self.openai_client = AzureOpenAI(
        #         api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        #         azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        #         api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2024-08-01-preview"),
        #     )
        #     self.openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
        #     LOGGER.debug("Using Azure OpenAI API")
        # else:
        #     raise ValueError("API key is not set. Please ensure the OPENAI_API_KEY or AZURE_OPENAI_API_KEY is set in the .env file.")

        atexit.register(self.__del__)
        LOGGER.info("Created Config instance")

    def __del__(self):
        LOGGER.info("Closing Config instance")
        try:
            if hasattr(self, 'secrets') and self.secrets is not None:
                self.secrets.transport.close()
        except Exception as e:
            LOGGER.error(f"Error closing Config instance {e}")
        finally:
            self.secrets = None


    def get_secret_value(self, secret_id, default=""):
        try:
            if self.secrets is None:
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)
            secret_name = f"projects/{self.gcp_project_id}/secrets/{secret_id}/versions/latest"
            response = self.secrets.access_secret_version(name=secret_name)
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            LOGGER.error(f"Error getting secret value {secret_id}: {e}")
            return default

    @classmethod
    @bond_cache
    def config(cls):
        return Config()

    def get_openai_client(self):
        return self.openai_client
    
    def get_openai_deployment(self):
        return self.openai_deployment
    
    def get_openai_project(self, *args, **kwargs):
        return os.getenv('OPENAI_PROJECT')
    
    def get_auth_info(self):
        auth_creds_str = self.get_secret_value(os.getenv('GOOGLE_AUTH_CREDS_SECRET_ID', 'google_auth_creds'), "{}")
        auth_creds = json.loads(auth_creds_str)
        redirect_uri = os.getenv('GOOGLE_AUTH_REDIRECT_URI', 'http://localhost:8080')
        scopes_str = os.getenv('GOOGLE_AUTH_SCOPES', 'openid, https://www.googleapis.com/auth/userinfo.email, https://www.googleapis.com/auth/userinfo.profile')
        scopes = [scope.strip() for scope in scopes_str.split(",")]
        valid_emails = os.getenv('GOOGLE_AUTH_VALID_EMAILS', "").split(",")
        auth_info = {
            "auth_creds": auth_creds,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "valid_emails": valid_emails
        }
        LOGGER.debug(f"Google Auth: {auth_info}")
        return auth_info



        








