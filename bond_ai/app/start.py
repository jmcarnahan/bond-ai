from streamlit.web import cli
import importlib.resources
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    with importlib.resources.path('bond_ai.app', 'index.py') as app_path:
        cli.main_run.main([str(app_path)])