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

        # Use OpenAI by default
        openai_client = None
        if not os.getenv('AZURE_OPENAI_API_KEY'):
            openai_api_key=os.getenv('OPENAI_KEY')
            openai_project_id=os.getenv('OPENAI_PROJECT')
            openai_client = OpenAI(api_key=openai_api_key, project=openai_project_id)
            LOGGER.info("Using OpenAI API")
        else:
            openai_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2025-04-01-preview"),
            )
            LOGGER.info("Using Azure OpenAI API")

        metadata_db_url = self.config.get_metadata_db_url()
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
        models = self.agents.get_available_models()
        
        # Handle empty models list
        if not models:
            LOGGER.warning("No models available from provider, using fallback 'gpt-4o'")
            return "gpt-4o"
        
        # Find the default model
        for model in models:
            if model.get('is_default', False):
                return model['name']
        
        # If no default is explicitly set, use the first model
        LOGGER.warning(f"No default model specified, using first available: {models[0]['name']}")
        return models[0]['name']

