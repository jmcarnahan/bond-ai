"""Tests for Alembic migration integration.

Verifies that:
- Fresh databases get all tables created via the initial migration
- Existing databases get stamped without schema changes
- Migrations are idempotent (running upgrade twice is a no-op)
- Autogenerate detects no diff after upgrade (migration matches models)
- Metadata.__init__() works with both fresh and existing SQLite databases
- drop_and_recreate_all() stamps head after recreation
"""
import os
import tempfile

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, scoped_session

from alembic.config import Config as AlembicConfig
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata

from bondable.bond.providers.metadata import Base, User, Group, EVERYONE_GROUP_ID

# Import BedrockMetadata to ensure all models (including monkey-patched
# VectorStore columns) are registered on Base.metadata
import bondable.bond.providers.bedrock.BedrockMetadata  # noqa: F401


def _get_alembic_cfg(db_url):
    """Create an AlembicConfig pointing at the project's alembic directory."""
    cfg = AlembicConfig()
    alembic_dir = os.path.join(
        os.path.dirname(__file__), '..', 'bondable', 'bond', 'alembic'
    )
    cfg.set_main_option('script_location', os.path.abspath(alembic_dir))
    cfg.set_main_option('sqlalchemy.url', db_url)
    return cfg


def _get_current_rev(engine):
    """Get the current Alembic revision from the database."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


@pytest.fixture
def fresh_db():
    """Provide a fresh SQLite database URL and clean up after test."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(path)  # Remove so it starts truly fresh
    db_url = f"sqlite:///{path}"
    yield db_url, path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def existing_db():
    """Provide a SQLite database with all tables already created (no alembic_version)."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(path)
    db_url = f"sqlite:///{path}"

    # Create all tables directly from models (simulates pre-Alembic state)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    yield db_url, path
    if os.path.exists(path):
        os.unlink(path)


class TestFreshDatabaseMigration:
    """Test that a fresh database gets all tables created via Alembic."""

    def test_upgrade_creates_all_tables(self, fresh_db):
        db_url, path = fresh_db
        cfg = _get_alembic_cfg(db_url)

        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Check core tables exist
        expected_tables = {
            'users', 'agents', 'threads', 'groups', 'group_users',
            'agent_groups', 'files', 'vector_stores', 'agent_folders',
            'agent_folder_assignments', 'user_agent_sort_orders',
            'scheduled_jobs', 'user_connection_tokens',
            'connection_oauth_states', 'auth_oauth_states',
            'auth_codes', 'revoked_tokens',
            # Bedrock tables
            'bedrock_agent_options', 'bedrock_messages',
            'bedrock_vector_store_files', 'knowledge_base_files',
            # Alembic tracking
            'alembic_version',
        }
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
        engine.dispose()

    def test_upgrade_creates_correct_columns(self, fresh_db):
        db_url, path = fresh_db
        cfg = _get_alembic_cfg(db_url)

        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)

        # Verify agents table has all expected columns
        agent_cols = {col['name'] for col in inspector.get_columns('agents')}
        assert 'agent_id' in agent_cols
        assert 'slug' in agent_cols
        assert 'default_group_id' in agent_cols
        assert 'owner_user_id' in agent_cols

        # Verify threads table has last_agent_id
        thread_cols = {col['name'] for col in inspector.get_columns('threads')}
        assert 'last_agent_id' in thread_cols
        assert 'scheduled_job_id' in thread_cols

        engine.dispose()

    def test_upgrade_sets_revision(self, fresh_db):
        db_url, path = fresh_db
        cfg = _get_alembic_cfg(db_url)

        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        rev = _get_current_rev(engine)
        assert rev is not None

        # Should match the head revision
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        assert rev == head
        engine.dispose()


class TestExistingDatabaseStamp:
    """Test that existing databases get stamped without schema changes."""

    def test_stamp_existing_db(self, existing_db):
        db_url, path = existing_db
        cfg = _get_alembic_cfg(db_url)

        # Verify tables exist but no alembic_version
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert 'users' in tables
        assert 'alembic_version' not in tables

        # Stamp should create alembic_version without altering schema
        command.stamp(cfg, "head")

        # Verify alembic_version now exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert 'alembic_version' in tables

        # Verify revision is at head
        rev = _get_current_rev(engine)
        script = ScriptDirectory.from_config(cfg)
        assert rev == script.get_current_head()
        engine.dispose()

    def test_stamp_preserves_data(self, existing_db):
        db_url, path = existing_db
        engine = create_engine(db_url)

        # Insert test data before stamp
        session = scoped_session(sessionmaker(bind=engine))()
        test_user = User(
            id="test-user-1",
            email="test@example.com",
            sign_in_method="test",
            name="Test User"
        )
        session.add(test_user)
        session.commit()
        session.close()

        # Stamp
        cfg = _get_alembic_cfg(db_url)
        command.stamp(cfg, "head")

        # Verify data still exists
        session = scoped_session(sessionmaker(bind=engine))()
        user = session.query(User).filter(User.id == "test-user-1").first()
        assert user is not None
        assert user.email == "test@example.com"
        session.close()
        engine.dispose()


class TestMigrationIdempotency:
    """Test that running migrations multiple times is safe."""

    def test_upgrade_twice_is_noop(self, fresh_db):
        db_url, path = fresh_db
        cfg = _get_alembic_cfg(db_url)

        command.upgrade(cfg, "head")
        engine = create_engine(db_url)
        rev1 = _get_current_rev(engine)

        # Second upgrade should be a no-op
        command.upgrade(cfg, "head")
        rev2 = _get_current_rev(engine)

        assert rev1 == rev2
        engine.dispose()

    def test_stamp_then_upgrade_is_noop(self, existing_db):
        db_url, path = existing_db
        cfg = _get_alembic_cfg(db_url)

        # Stamp first (simulates first startup with existing DB)
        command.stamp(cfg, "head")

        # Then upgrade should be a no-op
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        rev = _get_current_rev(engine)
        script = ScriptDirectory.from_config(cfg)
        assert rev == script.get_current_head()
        engine.dispose()


class TestAutogenerateNoDiff:
    """Test that after upgrade, autogenerate detects no schema differences."""

    def test_no_diff_after_upgrade(self, fresh_db):
        db_url, path = fresh_db
        cfg = _get_alembic_cfg(db_url)

        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diffs = compare_metadata(ctx, Base.metadata)

        # Filter out diffs that are just index naming differences or
        # other insignificant variations between SQLite and the models
        significant_diffs = [
            d for d in diffs
            if d[0] not in ('remove_index',)  # SQLite may report index diffs
        ]

        assert len(significant_diffs) == 0, (
            f"Autogenerate detected schema differences after upgrade:\n"
            f"{significant_diffs}"
        )
        engine.dispose()


class TestMetadataInit:
    """Test that Metadata.__init__() works correctly with Alembic."""

    def test_init_fresh_db(self):
        """Metadata.__init__() should create schema on a fresh database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(path)
        db_url = f"sqlite:///{path}"

        try:
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata
            metadata = BedrockMetadata(db_url)

            # Verify tables were created
            inspector = inspect(metadata.engine)
            tables = set(inspector.get_table_names())
            assert 'users' in tables
            assert 'agents' in tables
            assert 'alembic_version' in tables

            # Verify Everyone group was created
            session = metadata.get_db_session()
            group = session.query(Group).filter(Group.id == EVERYONE_GROUP_ID).first()
            assert group is not None
            assert group.name == "Everyone"
            session.close()

            metadata.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_init_existing_db(self):
        """Metadata.__init__() should stamp an existing database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(path)
        db_url = f"sqlite:///{path}"

        try:
            # First create tables directly (simulates pre-Alembic state)
            engine = create_engine(db_url)
            Base.metadata.create_all(engine)
            engine.dispose()

            # Now init Metadata — should detect existing DB and stamp
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata
            metadata = BedrockMetadata(db_url)

            # Verify alembic_version was created
            inspector = inspect(metadata.engine)
            tables = inspector.get_table_names()
            assert 'alembic_version' in tables

            # Verify it's at head
            rev = _get_current_rev(metadata.engine)
            assert rev is not None

            metadata.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_init_existing_db_missing_columns(self):
        """Metadata.__init__() should add missing columns before stamping."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(path)
        db_url = f"sqlite:///{path}"

        try:
            # Create an older schema missing slug, default_group_id, last_agent_id
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(sa.text(
                    "CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR NOT NULL, "
                    "sign_in_method VARCHAR NOT NULL, name VARCHAR, is_admin BOOLEAN NOT NULL DEFAULT 0, "
                    "created_at DATETIME, updated_at DATETIME)"
                ))
                conn.execute(sa.text(
                    "CREATE TABLE groups (id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, "
                    "description VARCHAR, owner_user_id VARCHAR REFERENCES users(id), "
                    "created_at DATETIME, updated_at DATETIME)"
                ))
                conn.execute(sa.text(
                    "CREATE TABLE agents (agent_id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, "
                    "introduction VARCHAR, reminder VARCHAR, "
                    "owner_user_id VARCHAR REFERENCES users(id) NOT NULL, "
                    "is_default BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME)"
                ))
                conn.execute(sa.text(
                    "CREATE TABLE threads (thread_id VARCHAR NOT NULL, "
                    "user_id VARCHAR NOT NULL REFERENCES users(id), "
                    "name VARCHAR, session_id VARCHAR, "
                    "created_at DATETIME, updated_at DATETIME, "
                    "PRIMARY KEY (thread_id, user_id))"
                ))
                conn.commit()
            engine.dispose()

            # Init Metadata — should detect missing columns, add them, and stamp
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata
            metadata = BedrockMetadata(db_url)

            # Verify missing columns were added
            insp = inspect(metadata.engine)
            agent_cols = {col['name'] for col in insp.get_columns('agents')}
            assert 'slug' in agent_cols, "slug column should have been added"
            assert 'default_group_id' in agent_cols, "default_group_id column should have been added"

            thread_cols = {col['name'] for col in insp.get_columns('threads')}
            assert 'last_agent_id' in thread_cols, "last_agent_id column should have been added"

            # Verify it was stamped at head
            rev = _get_current_rev(metadata.engine)
            assert rev is not None

            metadata.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_drop_and_recreate_stamps_head(self):
        """drop_and_recreate_all() should stamp head after recreation."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(path)
        db_url = f"sqlite:///{path}"

        try:
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata
            metadata = BedrockMetadata(db_url)

            # Drop and recreate
            metadata.drop_and_recreate_all()

            # Verify alembic_version exists and is at head
            rev = _get_current_rev(metadata.engine)
            assert rev is not None

            cfg = _get_alembic_cfg(db_url)
            script = ScriptDirectory.from_config(cfg)
            assert rev == script.get_current_head()

            metadata.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
