import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context

# Ensure the project root is on the path so we can import bondable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import Base and all model modules to register them on Base.metadata
from bondable.bond.providers.metadata import Base  # noqa: E402
# Import BedrockMetadata to register Bedrock-specific models (including
# the monkey-patched VectorStore columns) on Base.metadata
import bondable.bond.providers.bedrock.BedrockMetadata  # noqa: E402, F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Get the database URL.

    Priority:
    1. sqlalchemy.url set programmatically via AlembicConfig (from _run_migrations)
    2. METADATA_DB_URL env var (CLI usage)
    3. Application Config class (AWS Secrets Manager, etc.)
    4. Fallback to SQLite
    """
    # Check if URL was set programmatically (e.g., from _run_migrations)
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    # Check env var (CLI usage)
    url = os.getenv('METADATA_DB_URL', '')
    if url:
        return url

    # Try to use the application Config class
    try:
        from bondable.bond.config import Config
        return Config.config().get_metadata_db_url()
    except Exception:  # nosec B110 — fallback is intentional for CLI/offline usage
        pass

    # Final fallback
    return "sqlite:////tmp/.metadata.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    url = get_url()

    connectable = create_engine(url)

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=url.startswith("sqlite"),
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
