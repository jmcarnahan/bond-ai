from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from bond_ai.bond.metadata import Metadata
from bond_ai.bond.page import Page
import os
import logging
import importlib

# TODO: not have this here
import streamlit as st

load_dotenv()

LOGGER = logging.getLogger(__name__)

class Config:
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key, project=os.getenv('OPENAI_PROJECT'))
            self.openai_deployment = os.getenv('OPENAI_DEPLOYMENT', 'gpt-4o')
            LOGGER.debug("Using OpenAI API")
        elif os.getenv('AZURE_OPENAI_API_KEY'):
            self.openai_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2024-08-01-preview"),
            )
            self.openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
            LOGGER.debug("Using Azure OpenAI API")
        else:
            raise ValueError("API key is not set. Please ensure the OPENAI_API_KEY or AZURE_OPENAI_API_KEY is set in the .env file.")
        LOGGER.info("Created Config instance")

    @classmethod
    @st.cache_resource
    def config(cls):
        return Config()

    def get_openai_client(self):
        return self.openai_client
    
    def get_openai_deployment(self):
        return self.openai_deployment
    
    def get_openai_project(self, *args, **kwargs):
        return os.getenv('OPENAI_PROJECT')
    



        








