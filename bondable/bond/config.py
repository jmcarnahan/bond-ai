import logging
LOGGER = logging.getLogger(__name__)

from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import os
import atexit
from google.cloud import secretmanager
from google.oauth2 import service_account
from bondable.bond.cache import bond_cache

load_dotenv()



class Config:
    
    def __init__(self):

        gcp_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.gcp_project_id = os.getenv('GOOGLE_PROJECT_ID')
        self.credentials = service_account.Credentials.from_service_account_file(gcp_creds_path)
        self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)

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


    def get_secret_value(self, secret_id):
        if self.secrets is None:
            self.secrets = secretmanager.SecretManagerServiceClient(credentials=self.credentials)
        secret_name = f"projects/{self.gcp_project_id}/secrets/{secret_id}/versions/latest"
        response = self.secrets.access_secret_version(name=secret_name)
        return response.payload.data.decode("UTF-8")

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
    



        








