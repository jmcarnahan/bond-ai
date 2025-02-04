from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from bond_ai.bond.metadata import Metadata
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

        self.metadata = Metadata(config=self)

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
        session = None
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
    
    def get_metadata(self) -> Metadata:
        return self.metadata

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
    
    def get_threads(self):
        if 'user_id' not in self.session:
            raise ValueError("User ID is not set in session")
        
        user_id = self.session['user_id']
        threads_key = f"_THREADS_INSTANCE_{user_id}"
        if threads_key in self.session:
            LOGGER.debug(f"Returning cached instance of threads for user {user_id}")
            return self.session[threads_key]
        else:
            from bond_ai.bond.threads import Threads
            threads = Threads(user_id=user_id, config=self)
            LOGGER.debug(f"Created new instance of threads for user {user_id}")
            self.session[threads_key] = threads
            return threads


        








