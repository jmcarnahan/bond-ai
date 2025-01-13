from streamlit.web import cli
import importlib.resources
from dotenv import load_dotenv
import os
import logging
import sys

load_dotenv()

LOGGER = logging.getLogger(__name__)

# TODO: change this to use the config file
logging.basicConfig(
  level=logging.INFO,  
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  
)
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    project_root = os.getcwd()
    
    # Construct the path to the .env file
    dotenv_path = os.path.join(project_root, '.env')
    
    # Load the .env file
    load_dotenv(dotenv_path)

    # add project root to sys.path
    if project_root not in sys.path:
        sys.path.append(project_root)
        LOGGER.info(f"Project root {project_root} added to sys.path")
        print(f"Project root {project_root} added to sys.path")
    

    with importlib.resources.path('bond_ai.app', 'index.py') as app_path:
        cli.main_run.main([str(app_path)])