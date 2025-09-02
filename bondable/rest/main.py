import logging.config
import yaml
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from bondable.rest.routers import auth, agents, threads, chat, files, mcp, groups

# Configure logging from YAML file
def setup_logging():
    """Load logging configuration from YAML file"""

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logs_dir = os.path.join(project_root, "logs")

    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    config_path = os.path.join(os.path.dirname(__file__), "logging_config.yaml")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logging.config.dictConfig(config)
    else:
        # Fallback to basic configuration if file not found
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
        )
        logging.warning(f"Logging configuration file not found at {config_path}, using default configuration")

setup_logging()
LOGGER = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bond AI REST API",
    description="REST API for Bond AI platform",
    version="1.0.0"
)

# Configure CORS
# Get CORS origins from environment variable or use defaults
cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost,http://localhost:5000,http://localhost:3000")
origins = [origin.strip() for origin in cors_origins_str.split(",")]

# Add production frontend URL if available
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in origins:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGGER.info(f"CORSMiddleware added with origins: {origins}")

# Include routers
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(mcp.router)
app.include_router(groups.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import functions needed by tests (backward compatibility)
from bondable.rest.utils.auth import create_access_token
from bondable.rest.dependencies.providers import get_bond_provider

# Re-export for backward compatibility
__all__ = ["app", "create_access_token", "get_bond_provider"]