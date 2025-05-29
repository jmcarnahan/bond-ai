import logging.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from bondable.rest.routers import auth, agents, threads, chat, files, mcp

# Configure logging
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "WARNING",
            "handlers": ["default"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bond AI REST API",
    description="REST API for Bond AI platform",
    version="1.0.0"
)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORSMiddleware added with origins: {origins}")

# Include routers
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(mcp.router)

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