from abc import ABC, abstractmethod


from sqlalchemy import ForeignKey, create_engine, Column, String, DateTime, func, PrimaryKeyConstraint, UniqueConstraint, Boolean, JSON, Integer
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.sql import text
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple


LOGGER = logging.getLogger(__name__)

# Well-known group ID for the "Everyone" group.
# Agents associated with this group are accessible to all authenticated users
# without requiring explicit group_users membership rows.
EVERYONE_GROUP_ID = "grp_everyone"


# These are the default ORM classes
# All instances of Metadata should use these classes and augment them as needed
Base = declarative_base()
class Thread(Base):
    __tablename__ = 'threads'
    thread_id = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    name = Column(String, default="New Thread")
    session_id = Column(String, nullable=True)  # remote session ID if any
    session_state = Column(JSON, default=dict)  # remote session state if any
    last_agent_id = Column(String, nullable=True)  # Soft reference, no FK constraint
    scheduled_job_id = Column(String, ForeignKey('scheduled_jobs.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (PrimaryKeyConstraint('thread_id', 'user_id'),)
class AgentRecord(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=True, unique=True, index=True)
    introduction = Column(String, nullable=True, default="")
    reminder = Column(String, nullable=True, default="")
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    default_group_id = Column(String, ForeignKey('groups.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

class FileRecord(Base):
    __tablename__ = "files"
    file_id = Column(String, primary_key=True)  # Unique file ID from provider
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    mime_type = Column(String, default="application/octet-stream")  # Default MIME type
    file_size = Column(Integer, nullable=True)  # Size in bytes
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Unique constraint on file_path + file_hash + owner_user_id
    # This allows same user to upload different versions of same file
    # and different users to upload same file
    __table_args__ = (UniqueConstraint('file_path', 'file_hash', 'owner_user_id', name='_file_path_hash_user_uc'),)
class VectorStore(Base):
    __tablename__ = "vector_stores"
    vector_store_id = Column(String, primary_key=True)  # Use vector_store_id as primary key
    name = Column(String, nullable=False)
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    default_for_agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Unique constraint on name + owner_user_id
    # This allows different users to have vector stores with the same name
    __table_args__ = (UniqueConstraint('name', 'owner_user_id', name='_vector_store_name_user_uc'),)
class AgentGroup(Base):
    __tablename__ = "agent_groups"
    agent_id = Column(String, ForeignKey('agents.agent_id'), primary_key=True)
    group_id = Column(String, ForeignKey('groups.id'), primary_key=True)
    permission = Column(String, nullable=False, default='can_use')  # 'can_use_read_only', 'can_use', or 'can_edit'
    created_at = Column(DateTime, default=datetime.datetime.now)
class Group(Base):
    __tablename__ = "groups"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    owner_user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
class GroupUser(Base):
    __tablename__ = "group_users"
    group_id = Column(String, ForeignKey('groups.id'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    sign_in_method = Column(String, nullable=False)
    name = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)  # T7: DB-backed admin role
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


# ============================================================================
# Connection Models - For MCP/External Service OAuth Integration
# ============================================================================
# Note: Connection configurations are now stored in BOND_MCP_CONFIG environment
# variable (JSON format). The ConnectionConfig table has been removed to avoid
# redundancy. UserConnectionToken and ConnectionOAuthState store user-specific
# data with connection_name validated against the environment config on use.
# ============================================================================

class UserConnectionToken(Base):
    """
    User-specific OAuth tokens for external connections.

    Tokens are encrypted at rest using the JWT secret key.
    Each user can have one token per connection.
    """
    __tablename__ = "user_connection_tokens"

    id = Column(String, primary_key=True, nullable=False)  # UUID
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    connection_name = Column(String, nullable=False, index=True)  # Validated against BOND_MCP_CONFIG on use

    # Encrypted tokens (use token_encryption.py to encrypt/decrypt)
    access_token_encrypted = Column(String, nullable=False)
    refresh_token_encrypted = Column(String, nullable=True)

    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=True)  # Token expiration time
    scopes = Column(String, nullable=True)  # Granted scopes

    # Provider-specific metadata (cloud_id, user info, etc.)
    provider_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # Ensure one token per user per connection
    __table_args__ = (
        UniqueConstraint('user_id', 'connection_name', name='_user_connection_uc'),
    )


class ConnectionOAuthState(Base):
    """
    Temporary storage for OAuth state during authorization flow.

    These records should be cleaned up after 10 minutes or after use.
    Used to verify OAuth callbacks and store PKCE code verifiers.
    """
    __tablename__ = "connection_oauth_states"

    state = Column(String, primary_key=True, nullable=False)  # Random state parameter
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    connection_name = Column(String, nullable=False, index=True)  # Validated against BOND_MCP_CONFIG on use
    code_verifier = Column(String, nullable=True)  # For PKCE
    redirect_uri = Column(String, nullable=True)  # Where to redirect after OAuth
    created_at = Column(DateTime, default=datetime.datetime.now)


class AuthOAuthState(Base):
    """
    Temporary storage for OAuth state during the primary auth login flow.

    Unlike ConnectionOAuthState, this table does NOT have a foreign key to users
    because the user hasn't authenticated yet when the login flow is initiated.
    Records are cleaned up after 10 minutes or after use.
    """
    __tablename__ = "auth_oauth_states"

    state = Column(String, primary_key=True, nullable=False)  # Random state parameter
    provider_name = Column(String, nullable=False)  # e.g., "okta", "google", "cognito"
    code_verifier = Column(String, nullable=True)  # For PKCE
    redirect_uri = Column(String, nullable=True)  # Mobile redirect URI
    platform = Column(String, nullable=True)  # "mobile" or empty
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class AuthCode(Base):
    """
    Short-lived authorization codes for the token exchange flow.

    After OAuth callback, a code is issued and the frontend exchanges it
    for either an HttpOnly cookie (web) or a bearer token (mobile).
    Codes are single-use and expire after 60 seconds.
    """
    __tablename__ = "auth_codes"
    code = Column(String, primary_key=True)  # secrets.token_urlsafe(32)
    access_token = Column(String, nullable=False)  # The JWT
    user_id = Column(String, nullable=False)
    platform = Column(String, nullable=True)  # "mobile" or None (web)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    used_at = Column(DateTime, nullable=True)  # Set on redemption, prevents reuse
    expires_at = Column(DateTime, nullable=False)  # created_at + 60 seconds


class RevokedToken(Base):
    """
    Revoked JWT tokens tracked by their jti claim.

    Used by POST /auth/logout to invalidate tokens before expiry.
    The expires_at field (copied from JWT exp) allows periodic cleanup.
    """
    __tablename__ = "revoked_tokens"
    jti = Column(String, primary_key=True)  # From JWT jti claim
    user_id = Column(String, nullable=False)
    revoked_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at = Column(DateTime, nullable=False)  # Copied from JWT exp, for cleanup


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id = Column(String, primary_key=True, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    agent_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    schedule = Column(String, nullable=False)  # Cron expression
    timezone = Column(String, default="UTC")
    is_enabled = Column(Boolean, default=True, nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending | running | completed | failed
    locked_by = Column(String, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    timeout_seconds = Column(Integer, default=300)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String, nullable=True)  # completed | failed | timed_out
    last_run_error = Column(String, nullable=True)
    last_thread_id = Column(String, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AgentFolder(Base):
    __tablename__ = "agent_folders"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    __table_args__ = (UniqueConstraint('name', 'user_id', name='_folder_name_user_uc'),)


class AgentFolderAssignment(Base):
    __tablename__ = "agent_folder_assignments"
    agent_id = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    folder_id = Column(String, ForeignKey('agent_folders.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    __table_args__ = (PrimaryKeyConstraint('agent_id', 'user_id'),)


class UserAgentSortOrder(Base):
    """Per-user agent ordering. Sort order is global per agent (not per-folder).
    When an agent moves between contexts (main screen <-> folder), its sort_order
    row is deleted so it appears at the end of the new context.
    The frontend filters agents by context first, then sorts by sort_order."""
    __tablename__ = "user_agent_sort_orders"
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    agent_id = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    __table_args__ = (PrimaryKeyConstraint('user_id', 'agent_id'),)


class Metadata(ABC):

    def __init__(self, metadata_db_url):
        self.metadata_db_url = metadata_db_url
        engine_kwargs = {"echo": False}
        if not metadata_db_url.startswith("sqlite"):
            engine_kwargs.update({
                "pool_size": 20,
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            })
        self.engine = create_engine(self.metadata_db_url, **engine_kwargs)
        self._run_migrations()
        self.session = scoped_session(sessionmaker(bind=self.engine))
        self._ensure_everyone_group()
        LOGGER.info(f"Created Metadata instance using database engine: {self.metadata_db_url}")

    def get_engine(self):
        return self.engine

    def _get_alembic_cfg(self):
        """Create an AlembicConfig pointing at the project's alembic directory."""
        from alembic.config import Config as AlembicConfig
        import os

        cfg = AlembicConfig()
        alembic_dir = os.path.join(os.path.dirname(__file__), '..', 'alembic')
        cfg.set_main_option('script_location', os.path.abspath(alembic_dir))
        cfg.set_main_option('sqlalchemy.url', self.metadata_db_url)
        return cfg

    def _run_migrations(self):
        """Run Alembic migrations programmatically.

        For existing databases without alembic_version table, brings the schema
        up to date with any columns added by previous manual migrations, then
        stamps as head. For fresh databases, runs all migrations to create the
        schema.
        """
        from alembic import command
        from sqlalchemy import inspect

        alembic_cfg = self._get_alembic_cfg()

        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()
        has_alembic_version = 'alembic_version' in existing_tables
        has_app_tables = 'users' in existing_tables

        if has_app_tables and not has_alembic_version:
            # Existing database without Alembic — apply any missing columns
            # from pre-Alembic manual migrations, then stamp as current
            self._apply_pre_alembic_fixups(inspector)
            LOGGER.info("Existing database detected without alembic_version. Stamping as head.")
            command.stamp(alembic_cfg, "head")
        else:
            # Fresh database or already Alembic-managed — run upgrade
            LOGGER.info("Running Alembic migrations...")
            command.upgrade(alembic_cfg, "head")

    def _apply_pre_alembic_fixups(self, inspector):
        """Ensure columns added by old manual _migrate_* methods exist.

        These columns were added incrementally over time before Alembic was
        adopted. If an existing database was created from an older version,
        it may be missing some of them. This runs once before the initial
        stamp to bring the schema up to the baseline.
        """
        # Check agents table columns
        if 'agents' in [t for t in inspector.get_table_names()]:
            agent_cols = {col['name'] for col in inspector.get_columns('agents')}

            if 'default_group_id' not in agent_cols:
                with self.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE agents ADD COLUMN default_group_id VARCHAR REFERENCES groups(id)"
                    ))
                    conn.commit()
                LOGGER.info("Pre-Alembic fixup: Added default_group_id column to agents table")

            if 'slug' not in agent_cols:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE agents ADD COLUMN slug VARCHAR"))
                    conn.commit()
                LOGGER.info("Pre-Alembic fixup: Added slug column to agents table")
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_agents_slug ON agents (slug)"
                        ))
                        conn.commit()
                    LOGGER.info("Pre-Alembic fixup: Created unique index on agents.slug")
                except Exception as e:
                    LOGGER.warning(f"Could not create unique index on slug (may already exist): {e}")

        # Check threads table columns
        if 'threads' in [t for t in inspector.get_table_names()]:
            thread_cols = {col['name'] for col in inspector.get_columns('threads')}

            if 'last_agent_id' not in thread_cols:
                with self.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE threads ADD COLUMN last_agent_id VARCHAR"
                    ))
                    conn.commit()
                LOGGER.info("Pre-Alembic fixup: Added last_agent_id column to threads table")

    def create_all(self):
        """Create all tables directly from SQLAlchemy models.

        Used by drop_and_recreate_all() for dev/test resets.
        For normal startup, use _run_migrations() instead.
        """
        Base.metadata.create_all(self.engine)

    def _ensure_everyone_group(self):
        """Create the well-known 'Everyone' group if it doesn't already exist."""
        session = scoped_session(sessionmaker(bind=self.engine))()
        try:
            existing = session.query(Group).filter(Group.id == EVERYONE_GROUP_ID).first()
            if not existing:
                system_user = session.query(User).filter(User.email == "system@bondableai.com").first()
                if not system_user:
                    import uuid
                    system_user = User(
                        id=str(uuid.uuid4()),
                        email="system@bondableai.com",
                        name="System",
                        sign_in_method="system"
                    )
                    session.add(system_user)
                    session.flush()

                everyone_group = Group(
                    id=EVERYONE_GROUP_ID,
                    name="Everyone",
                    description="Agents in this group are accessible to all users",
                    owner_user_id=system_user.id
                )
                session.add(everyone_group)
                session.commit()
                LOGGER.info(f"Created 'Everyone' group with id: {EVERYONE_GROUP_ID}")
        except Exception as e:
            session.rollback()
            LOGGER.warning(f"Everyone group could not be created; agents assigned to it will not be globally visible until this is resolved: {e}")
        finally:
            session.close()

    def drop_and_recreate_all(self):
        """Drop all tables and recreate them. Use with caution - this deletes all data!"""
        from alembic import command

        LOGGER.warning("Dropping all tables and recreating schema. All data will be lost!")
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

        # Stamp as head so Alembic knows the schema is current
        command.stamp(self._get_alembic_cfg(), "head")

        self._ensure_everyone_group()
        LOGGER.info("Schema recreated successfully")

    def get_db_session(self) -> scoped_session:
        if not self.engine:
            self.engine = create_engine(self.metadata_db_url, echo=False)
            self._run_migrations()
            self.session = scoped_session(sessionmaker(bind=self.engine))
            LOGGER.info(f"Re-created Metadata instance using database engine: {self.metadata_db_url}")
        return self.session()

    def close_db_engine(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None
            LOGGER.info(f"Closed database engine")

    def close(self) -> None:
        self.close_db_engine()

    def get_or_create_system_user(self) -> User:
        """
        Get or create the system user for internal operations.

        Returns:
            User: The system user object
        """
        with self.get_db_session() as session:
            system_user = session.query(User).filter(User.email == "system@bondableai.com").first()

            if not system_user:
                # Create system user
                import uuid
                system_user = User(
                    id=str(uuid.uuid4()),
                    email="system@bondableai.com",
                    name="System",
                    sign_in_method="system"
                )
                session.add(system_user)
                session.commit()
                LOGGER.info(f"Created system user with id: {system_user.id}")

            return system_user
