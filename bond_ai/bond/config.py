

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import text
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import os
import logging
import importlib

load_dotenv()

LOGGER = logging.getLogger(__name__)


class Config:
    
    def __custom_init__(self, *args, **kwargs):
        if kwargs.get('session') is not None:
            self.session = kwargs['session']
        else:
            self.session = {}

        self.engines = {}
        metadata_db_path = os.getenv('METADATA_FILE', '.metadata.db')
        LOGGER.info(f"Using metadata db path: {metadata_db_path}")
        self.engines['default'] = create_engine(f"sqlite:///{metadata_db_path}", echo=False)

        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key, project=os.getenv('OPENAI_PROJECT'))
            self.openai_deployment = os.getenv('OPENAI_DEPLOYMENT', 'gpt-4o')
            LOGGER.info("Using OpenAI API")
        elif os.getenv('AZURE_OPENAI_API_KEY'):
            self.openai_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2024-08-01-preview"),
            )
            self.openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
            LOGGER.info("Using Azure OpenAI API")
        else:
            raise ValueError("API key is not set. Please ensure the OPENAI_API_KEY or AZURE_OPENAI_API_KEY is set in the .env file.")

    def __new__(cls, *args, **kwargs):
        if kwargs.get('session') is not None:
            session = kwargs['session']
            if '_bond_config' in session:
                LOGGER.debug(f"Returning cached instance of config from session")
                return session['_bond_config']
        
        instance = super(Config, cls).__new__(cls)
        instance.__custom_init__(*args, **kwargs)
        if session is not None:
            session['_bond_config'] = instance
        LOGGER.info(f"Returning new instance of config")
        return instance

    def get_session(self):
        return self.session

    def get_db_engine(self, db_path="default"):
        if db_path not in self.engines:
            engine = create_engine(f'sqlite:///{db_path}', echo=True)
            self.engines[db_path] = engine
        return self.engines[db_path]

    def get_db_session(self, db_path="default"):
        engine = self.get_db_engine(db_path)
        Session = scoped_session(sessionmaker(bind=engine))
        return Session()

    def close_db_engine(self, db_path="default"):
        if db_path in self.engines:
            self.engines[db_path].dispose()
            del self.engines[db_path]

    def get_openai_client(self):
        return self.openai_client
    
    def get_openai_deployment(self):
        return self.openai_deployment
    
    def get_openai_project(self, *args, **kwargs):
        return os.getenv('OPENAI_PROJECT')
    
    def _get_instance(self, env_var, session_var, parent_class, default_class):
        if self.session is not None and session_var in self.session:
            LOGGER.debug(f"Returning cached instance: ({env_var}) from var: ({session_var})")
            return self.session[session_var]
        else:
            cls = self.__class__
            fully_qualified_name = os.getenv(env_var, f"{default_class.__module__}.{default_class.__qualname__}")
            try:
                module_name, class_name = fully_qualified_name.rsplit(".", 1)
                module = importlib.import_module(module_name)
                instance_class = getattr(module, class_name)
                if not issubclass(instance_class, parent_class):
                    raise ValueError(f"Class {class_name} must extend {parent_class}")
                instance = instance_class(config=self)
                if self.session is not None:
                    self.session[session_var] = instance
                LOGGER.info(f"Created new instance: ({fully_qualified_name})")      
                return instance
            except ImportError:
                raise ImportError(f"Could not import module: {fully_qualified_name}")

    def get_functions(self):
        from bond_ai.bond.functions import Functions, DefaultFunctions
        return self._get_instance('FUNCTIONS_CLASS', '_FUNCTIONS_INSTANCE', Functions, DefaultFunctions)

    def get_pages(self):
        from bond_ai.bond.pages import Pages, DefaultPages
        pages: Pages = self._get_instance('PAGES_CLASS', '_PAGES_INSTANCE', Pages, DefaultPages)
        return pages.get_pages()

        








