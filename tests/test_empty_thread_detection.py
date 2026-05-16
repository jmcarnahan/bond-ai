"""Integration tests for empty thread detection with hidden message support.

Tests the _user_message_exists_clause() SQL logic against a real SQLite database
to verify that hidden user messages (agent introductions) are correctly excluded
when determining whether a thread is "empty".
"""

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from bondable.bond.broker import BondMessage
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
from bondable.bond.providers.metadata import Base, Thread, User
from bondable.bond.providers.threads import ThreadsProvider


class StubThreadsProvider(ThreadsProvider):
    """Minimal concrete implementation of ThreadsProvider for testing."""

    def delete_thread_resource(self, thread_id: str) -> bool:
        return True

    def create_thread_resource(self) -> str:
        return str(uuid.uuid4())

    def has_messages(self, thread_id, last_message_id=None) -> bool:
        return False

    def get_messages(self, thread_id, limit=100, user_id=None) -> Dict[str, BondMessage]:
        return {}


class StubMetadata:
    """Minimal metadata providing a real SQLite session for SQL testing."""

    def __init__(self, engine, session_factory):
        self._engine = engine
        self._session_factory = session_factory

    @contextmanager
    def get_db_session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()


TEST_USER_ID = "test-user-001"


@pytest.fixture
def provider():
    """Create a StubThreadsProvider backed by a real SQLite in-memory database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine))

    meta = StubMetadata(engine, Session)
    prov = StubThreadsProvider(meta)

    # Create the test user
    session = Session()
    session.add(User(id=TEST_USER_ID, email="test@example.com", sign_in_method="test"))
    session.commit()
    session.close()

    yield prov

    Session.remove()
    engine.dispose()


def _make_thread(session, thread_id: str, user_id: str = TEST_USER_ID,
                 created_at: datetime = None):
    """Helper to insert a thread row."""
    t = Thread(
        thread_id=thread_id,
        user_id=user_id,
        name="Test Thread",
        created_at=created_at or datetime.utcnow(),
    )
    session.add(t)
    session.flush()
    return t


def _make_message(session, thread_id: str, role: str = "user",
                  message_type: str = "text", metadata: dict = None,
                  user_id: str = TEST_USER_ID):
    """Helper to insert a bedrock_messages row."""
    # Count existing messages for this thread to set message_index
    count = session.query(BedrockMessage).filter_by(thread_id=thread_id).count()
    msg = BedrockMessage(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        user_id=user_id,
        role=role,
        type=message_type,
        content=json.dumps({"text": "test content"}),
        message_index=count,
        message_metadata=metadata,
    )
    session.add(msg)
    session.flush()
    return msg


class TestEmptyThreadDetection:
    """Tests for _user_message_exists_clause() and dependent methods."""

    def test_visible_user_message_is_not_empty(self, provider):
        """Thread with a normal visible user message should NOT be empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user", metadata={"agent_id": "a1"})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" not in empty_ids

    def test_hidden_bool_user_message_is_empty(self, provider):
        """Thread with only a hidden=True user message should BE empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user",
                          metadata={"agent_id": "a1", "hidden": True})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" in empty_ids

    def test_hidden_string_user_message_is_empty(self, provider):
        """Thread with only a hidden='true' (string) user message should BE empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user",
                          metadata={"agent_id": "a1", "hidden": "true"})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" in empty_ids

    def test_override_role_system_user_message_is_empty(self, provider):
        """Thread with only an override_role='system' user message should BE empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user",
                          metadata={"override_role": "system"})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" in empty_ids

    def test_hidden_plus_visible_user_message_is_not_empty(self, provider):
        """Thread with both hidden and visible user messages should NOT be empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user",
                          metadata={"agent_id": "a1", "hidden": True})
            _make_message(session, "t1", role="user",
                          metadata={"agent_id": "a1"})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" not in empty_ids

    def test_no_messages_is_empty(self, provider):
        """Thread with no messages at all should BE empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" in empty_ids

    def test_only_assistant_messages_is_empty(self, provider):
        """Thread with only assistant messages should BE empty."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="assistant",
                          metadata={"agent_id": "a1"})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" in empty_ids

    def test_null_metadata_user_message_is_not_empty(self, provider):
        """Thread with a user message having NULL metadata should NOT be empty (visible)."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user", metadata=None)
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" not in empty_ids

    def test_empty_dict_metadata_user_message_is_not_empty(self, provider):
        """Thread with a user message having {} metadata should NOT be empty (visible)."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user", metadata={})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" not in empty_ids

    def test_hidden_false_user_message_is_not_empty(self, provider):
        """Thread with a user message having hidden=False should NOT be empty (visible)."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t1")
            _make_message(session, "t1", role="user",
                          metadata={"agent_id": "a1", "hidden": False})
            session.commit()

        empty_ids = provider.get_empty_thread_ids(user_id=TEST_USER_ID)
        assert "t1" not in empty_ids


class TestExcludeEmptyThreadsQuery:
    """Tests for get_current_threads(exclude_empty=True) and get_thread_count(exclude_empty=True)."""

    def test_exclude_empty_filters_hidden_only_threads(self, provider):
        """get_current_threads with exclude_empty should omit threads having only hidden user messages."""
        with provider.metadata.get_db_session() as session:
            # Thread with only a hidden introduction
            _make_thread(session, "t-hidden")
            _make_message(session, "t-hidden", role="user",
                          metadata={"agent_id": "a1", "hidden": True})

            # Thread with a real user message
            _make_thread(session, "t-visible")
            _make_message(session, "t-visible", role="user",
                          metadata={"agent_id": "a1"})

            session.commit()

        threads = provider.get_current_threads(user_id=TEST_USER_ID, exclude_empty=True)
        thread_ids = [t["thread_id"] for t in threads]
        assert "t-visible" in thread_ids
        assert "t-hidden" not in thread_ids

    def test_exclude_empty_count_matches(self, provider):
        """get_thread_count with exclude_empty should agree with the filtered listing."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t-hidden")
            _make_message(session, "t-hidden", role="user",
                          metadata={"agent_id": "a1", "hidden": True})

            _make_thread(session, "t-visible")
            _make_message(session, "t-visible", role="user",
                          metadata={"agent_id": "a1"})

            _make_thread(session, "t-empty")  # no messages

            session.commit()

        count = provider.get_thread_count(user_id=TEST_USER_ID, exclude_empty=True)
        assert count == 1  # only t-visible

        count_all = provider.get_thread_count(user_id=TEST_USER_ID, exclude_empty=False)
        assert count_all == 3

    def test_include_all_threads_returns_everything(self, provider):
        """get_current_threads without exclude_empty should return all threads."""
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t-hidden")
            _make_message(session, "t-hidden", role="user",
                          metadata={"agent_id": "a1", "hidden": True})

            _make_thread(session, "t-visible")
            _make_message(session, "t-visible", role="user",
                          metadata={"agent_id": "a1"})

            session.commit()

        threads = provider.get_current_threads(user_id=TEST_USER_ID, exclude_empty=False)
        thread_ids = [t["thread_id"] for t in threads]
        assert "t-hidden" in thread_ids
        assert "t-visible" in thread_ids


class TestDeleteEmptyThreads:
    """Tests for delete_empty_threads() with hidden message awareness."""

    def test_deletes_threads_with_only_hidden_messages(self, provider):
        """delete_empty_threads should delete threads that only have hidden user messages."""
        old_time = datetime.utcnow() - timedelta(days=2)
        with provider.metadata.get_db_session() as session:
            _make_thread(session, "t-hidden", created_at=old_time)
            _make_message(session, "t-hidden", role="user",
                          metadata={"agent_id": "a1", "hidden": True})

            _make_thread(session, "t-visible", created_at=old_time)
            _make_message(session, "t-visible", role="user",
                          metadata={"agent_id": "a1"})

            session.commit()

        deleted = provider.delete_empty_threads(user_id=TEST_USER_ID, min_age_minutes=0)
        assert deleted == 1

        # Verify the visible thread still exists
        threads = provider.get_current_threads(user_id=TEST_USER_ID, exclude_empty=False)
        thread_ids = [t["thread_id"] for t in threads]
        assert "t-visible" in thread_ids
        assert "t-hidden" not in thread_ids
