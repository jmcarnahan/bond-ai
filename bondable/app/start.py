from streamlit.web import cli
import importlib.resources
from dotenv import load_dotenv
import os
import logging
import sys
import signal


load_dotenv()

LOGGER = logging.getLogger(__name__)

# Configure logging
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

    # Add project root to sys.path
    if project_root not in sys.path:
        sys.path.append(project_root)
        LOGGER.info(f"Project root {project_root} added to sys.path")
        print(f"Project root {project_root} added to sys.path")

    # broker = BondBroker()
    # broker.start()

    # def graceful_shutdown(signum, frame):
    #     LOGGER.info(f"Received signal {signum}, shutting down gracefully...")
    #     broker.stop()
    #     sys.exit(0)

    # # Register signal handlers for SIGINT (Ctrl+C) and SIGTERM (system termination)
    # signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
    # signal.signal(signal.SIGTERM, graceful_shutdown) 

    try:
        streamlit_args = sys.argv[1:]  
        with importlib.resources.path('bondable.app', 'index.py') as app_path:
            LOGGER.info(f"Starting Bond AI {str(app_path)} with parameters: {streamlit_args}")
            cli.main_run.main([str(app_path)] + streamlit_args)
    except:
        LOGGER.error("Received error when running streamlit")
    # finally:
    #     broker.stop()



