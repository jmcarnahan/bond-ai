import logging
from bondable.bond.cache import bond_cache
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.openai.OAIAFiles import OAIAFilesProvider
from bondable.bond.providers.openai.OAIAVectorstores import OAIAVectorStoresProvider
from bondable.bond.providers.openai.OAIAThreads import OAIAThreadsProvider
from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from openai import OpenAI, AzureOpenAI
from typing_extensions import override
import os

LOGGER = logging.getLogger(__name__)


class OAIAProvider(Provider):

    def __init__(self):
        super().__init__()
        self.config = Config.config()

        openai_api_key = self.config.get_secret_value(os.getenv('OPENAI_KEY_SECRET_ID', 'openai_api_key'))
        openai_project_id = self.config.get_secret_value(os.getenv('OPENAI_PROJECT_SECRET_ID', 'openai_project'))
        openai_client = OpenAI(api_key=openai_api_key, project=openai_project_id)
        metadata_db_url = self.config.get_metadata_db_url()

        # openai_deployment = os.getenv('OPENAI_DEPLOYMENT', 'gpt-4o')

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

        self.metadata = OAIAMetadata(metadata_db_url)
        self.files = OAIAFilesProvider(openai_client, self.metadata)
        self.vectorstores = OAIAVectorStoresProvider(openai_client, self.metadata, self.files) 
        self.threads = OAIAThreadsProvider(openai_client, self.metadata)
        self.agents = OAIAAgentProvider(openai_client, self.metadata)
        

    @classmethod
    @bond_cache
    def provider(cls) -> Provider:
        return OAIAProvider()


    @override
    def get_default_model(self) -> str:
        return "gpt-4o"

