

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import text
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from bond_ai.bond.functions import Functions
import os
import logging
import importlib

load_dotenv()

LOGGER = logging.getLogger(__name__)

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.engines = {}
            metadata_db_path = os.getenv('METADATA_FILE', '.metadata.db')
            LOGGER.info(f"Using metadata db path: {metadata_db_path}")
            cls._instance.engines['default'] = create_engine(f"sqlite:///{metadata_db_path}", echo=False)

            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                cls._instance.openai_client = OpenAI(api_key=api_key, project=os.getenv('OPENAI_PROJECT'))
                cls._instance.openai_deployment = os.getenv('OPENAI_DEPLOYMENT', 'gpt-4o')
                LOGGER.info("Using OpenAI API")
            elif os.getenv('AZURE_OPENAI_API_KEY'):
                cls._instance.openai_client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2024-08-01-preview"),
                )
                cls._instance.openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
                LOGGER.info("Using Azure OpenAI API")
            else:
                raise ValueError("API key is not set. Please ensure the OPENAI_API_KEY or AZURE_OPENAI_API_KEY is set in the .env file.")

        return cls._instance

    @classmethod
    def initialize(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)


    @classmethod
    def get_db_engine(cls, db_path="default"):
        cls.initialize()  # Ensure _instance is initialized
        if db_path not in cls._instance.engines:
            engine = create_engine(f'sqlite:///{db_path}', echo=True)
            cls._instance.engines[db_path] = engine
        return cls._instance.engines[db_path]

    @classmethod
    def get_db_session(cls, db_path="default"):
        cls.initialize()  # Ensure _instance is initialized
        engine = cls.get_db_engine(db_path)
        Session = scoped_session(sessionmaker(bind=engine))
        return Session()

    @classmethod
    def close_db_engine(cls, db_path="default"):
        cls.initialize()  # Ensure _instance is initialized
        if db_path in cls._instance.engines:
            cls._instance.engines[db_path].dispose()
            del cls._instance.engines[db_path]

    @classmethod
    def get_openai_client(cls):
        cls.initialize()
        return cls._instance.openai_client
    
    @classmethod
    def get_openai_deployment(cls):
        cls.initialize()
        return cls._instance.openai_deployment
    
    @classmethod
    def get_openai_project(cls):
        return os.getenv('OPENAI_PROJECT')
    
    @classmethod
    def get_functions(cls):
        fully_qualified_name = os.getenv('FUNCTIONS_CLASS', f"{Functions.__module__}.{Functions.__qualname__}")
        try:
            module_name, class_name = fully_qualified_name.rsplit(".", 1)
            module = importlib.import_module(module_name)
            functions_class = getattr(module, class_name)
            LOGGER.debug(f"Loaded functions module: {fully_qualified_name}")
            # need to return an instance of the class so class must have a no-arg constructor
            return functions_class()
        except ImportError:
            raise ImportError(f"Could not import functions module: {fully_qualified_name}")

    @classmethod
    def get_pages(cls):
        # pages function must return an list of st.Page objects
        pages = os.getenv('PAGES_FUNCTION', None)
        if pages:
            parts = pages.rsplit(".", 2)
            if len(parts) == 2:
                module = importlib.import_module(parts[0])
                function = getattr(module, parts[1])
                return function()
            elif len(parts) == 3:
                module = importlib.import_module(parts[0])
                cls = getattr(module, parts[1])
                function = getattr(cls, parts[2])
                return function()
            else:
                raise ValueError("PAGES_FUNCTION must be a list of length 2 or 3")
        else:
            return None
        








