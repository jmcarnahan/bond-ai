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
        with importlib.resources.path('bond_ai.app', 'index.py') as app_path:
            LOGGER.info(f"Starting Bond AI {str(app_path)} with parameters: {streamlit_args}")
            cli.main_run.main([str(app_path)] + streamlit_args)
    except:
        LOGGER.error("Received error when running streamlit")
    # finally:
    #     broker.stop()


# import os
# import sys
# import signal
# import importlib.resources
# import logging
# import subprocess
# import time
# from dotenv import load_dotenv
# from bond_ai.bond.broker import BondBroker


# LOGGER = logging.getLogger(__name__)

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# )
# logging.getLogger("httpx").setLevel(logging.WARNING)


# def main():
#     # Load environment variables
#     project_root = os.getcwd()
#     dotenv_path = os.path.join(project_root, '.env')
#     load_dotenv(dotenv_path)

#     # Add project root to sys.path
#     if project_root not in sys.path:
#         sys.path.append(project_root)
#         LOGGER.info(f"Project root {project_root} added to sys.path")

#     # Start the BondBroker
#     broker = BondBroker()
#     broker.start()

#     # Construct Streamlit command
#     with importlib.resources.path('bond_ai.app', 'index.py') as app_path:
#         streamlit_command = ["streamlit", "run", str(app_path)] + sys.argv[1:]
#         LOGGER.info(f"Starting Streamlit with command: {' '.join(streamlit_command)}")

#     # Start Streamlit in a separate process
#     streamlit_process = subprocess.Popen(streamlit_command, stdout=sys.stdout, stderr=sys.stderr)

#     # Handle shutdown with signals
#     shutdown_event = False

#     def graceful_shutdown(signum, frame):
#         nonlocal shutdown_event
#         if not shutdown_event:
#             LOGGER.info(f"Received signal {signum}, shutting down gracefully...")
#             shutdown_event = True
#             broker.stop()
#             streamlit_process.terminate()
#             streamlit_process.wait()
#             LOGGER.info("Shutdown complete.")
#             sys.exit(0)

#     # Register signal handlers
#     signal.signal(signal.SIGINT, graceful_shutdown)
#     signal.signal(signal.SIGTERM, graceful_shutdown)

#     # Wait for Streamlit process to complete
#     try:
#         while streamlit_process.poll() is None:
#             time.sleep(0.5)
#     except KeyboardInterrupt:
#         graceful_shutdown(signal.SIGINT, None)
#     finally:
#         if streamlit_process.poll() is None:
#             streamlit_process.terminate()
#             streamlit_process.wait()
#         broker.stop()

# if __name__ == "__main__":
#     main()
