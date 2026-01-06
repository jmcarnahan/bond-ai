import logging
import os
import pytest
import time # Added for sleep
from typing import Optional

from bondable.bond.cache import bond_cache_clear
from bondable.bond.config import Config
from bondable.bond.metadata import Metadata, Thread as OrmThread
from bondable.bond.threads import Threads
from tests.common import MySession

LOGGER = logging.getLogger(__name__)
TEST_USER_ID = 'test_user' # Default user for most tests
TEST_DB_URL = 'sqlite:///.metadata-test.db' # In-memory or temporary file DB for tests

class TestThreadOperations:

    def setup_method(self):
        """Set up test environment before each test."""
        bond_cache_clear()
        # Ensure a clean test database file if it exists from a previous run
        if os.path.exists('.metadata-test.db'):
            os.remove('.metadata-test.db')

        os.environ['METADATA_DB_URL'] = TEST_DB_URL

        # Initialize core components. These will use the TEST_DB_URL.
        self.config = Config.config()
        self.metadata = Metadata.metadata()
        self.threads = Threads.threads(user_id=TEST_USER_ID)

    def teardown_method(self):
        """Clean up test environment after each test."""
        try:
            if hasattr(self, 'metadata') and self.metadata:
                unique_thread_ids_to_delete = set()
                with self.metadata.get_db_session() as session:
                    # Collect all unique thread_ids created by any of the test users
                    threads_by_test_users = session.query(OrmThread.thread_id).distinct().all()
                    for row in threads_by_test_users:
                        unique_thread_ids_to_delete.add(row.thread_id)

                for thread_id_to_delete in unique_thread_ids_to_delete:
                    try:
                        self.metadata.delete_thread(thread_id_to_delete)
                        LOGGER.debug(f"Teardown: Successfully processed deletion for thread_id {thread_id_to_delete}")
                    except Exception as e:
                        # Log error but continue to ensure other cleanup happens
                        LOGGER.error(f"Teardown: Error during metadata.delete_thread for {thread_id_to_delete}: {type(e).__name__} - {str(e)}")

                self.metadata.close()
        except Exception as e:
            LOGGER.error(f"Error during overall teardown: {type(e).__name__} - {str(e)}")
        finally:
            if os.path.exists('.metadata-test.db'):
                os.remove('.metadata-test.db')
            if 'METADATA_DB_URL' in os.environ:
                del os.environ['METADATA_DB_URL']

            self.config = None
            self.threads = None
            self.metadata = None
            bond_cache_clear()

    def test_create_thread(self):
        # Test creating a thread without a name (should use DB default "New Thread")
        created_thread_orm = self.threads.create_thread()
        assert created_thread_orm is not None
        assert created_thread_orm.thread_id is not None
        assert created_thread_orm.user_id == TEST_USER_ID
        assert created_thread_orm.name == "New Thread"

        # Test creating a thread with a specific name
        custom_name = "My Custom Thread"
        created_thread_with_name_orm = self.threads.create_thread(name=custom_name)
        assert created_thread_with_name_orm is not None
        assert created_thread_with_name_orm.thread_id is not None
        assert created_thread_with_name_orm.user_id == TEST_USER_ID
        assert created_thread_with_name_orm.name == custom_name

    def test_get_current_threads(self):
        # Ensure no threads exist initially for this user to make the test cleaner
        # This part of teardown should handle this, but let's be explicit for this test.
        with self.metadata.get_db_session() as s:
            s.query(OrmThread).delete()
            s.commit()

        thread_name = "Test Thread for Get Current"
        created_thread_orm = self.threads.create_thread(name=thread_name)
        assert created_thread_orm.thread_id is not None

        threads_list = self.threads.get_current_threads(count=10)
        assert len(threads_list) >= 1

        # Verify the created thread is in the list (it should be the first due to ordering)
        found_thread = next((t for t in threads_list if t['thread_id'] == created_thread_orm.thread_id), None)
        assert found_thread is not None
        assert found_thread['name'] == thread_name

    def test_get_current_thread_id(self):
        # Scenario 1: No threads exist, empty session. Should create a new one.
        # Ensure no threads for TEST_USER_ID before this part
        with self.metadata.get_db_session() as s:
            s.query(OrmThread).delete()
            s.commit()

        session_s1 = MySession()
        created_id_s1 = self.threads.get_current_thread_id(session=session_s1)
        assert created_id_s1 is not None
        assert 'thread' in session_s1
        assert session_s1['thread'] == created_id_s1
        # Verify this thread was indeed created for TEST_USER_ID
        assert self.metadata.get_thread(created_id_s1) is not None

        # Scenario 2: One thread exists, empty session. Should find and use existing.
        # (created_id_s1 is the existing one)
        session_s2 = MySession()
        retrieved_id_s2 = self.threads.get_current_thread_id(session=session_s2)
        assert retrieved_id_s2 == created_id_s1 # Should pick the only existing thread
        assert session_s2['thread'] == created_id_s1

        # Scenario 3: Session already has a thread_id. Should use that.
        pre_existing_thread_id_in_session = "session_thread_123"
        session_s3 = MySession()
        session_s3['thread'] = pre_existing_thread_id_in_session

        retrieved_id_s3 = self.threads.get_current_thread_id(session=session_s3)
        assert retrieved_id_s3 == pre_existing_thread_id_in_session


    def test_update_thread_name_db_direct(self):
        initial_name = "Initial Name for DB Update"
        created_thread_orm = self.threads.create_thread(name=initial_name)
        assert created_thread_orm.thread_id is not None
        assert created_thread_orm.name == initial_name

        updated_name = "Updated Directly in DB"
        self.metadata.update_thread_name(thread_id=created_thread_orm.thread_id, thread_name=updated_name)

        # Verify via Threads service, which might involve its own logic (like name derivation if empty)
        threads_list = self.threads.get_current_threads(count=10)
        updated_thread_info = next((t for t in threads_list if t['thread_id'] == created_thread_orm.thread_id), None)
        assert updated_thread_info is not None
        assert updated_thread_info['name'] == updated_name

        # Verify directly from DB via metadata.get_thread (which returns a dict)
        thread_details_dict = self.metadata.get_thread(created_thread_orm.thread_id)
        assert thread_details_dict is not None
        # get_thread() consolidates info; for this user, name should be updated.
        assert thread_details_dict['name'] == updated_name
        assert TEST_USER_ID in thread_details_dict['users']


    def test_grant_thread_functionality(self):
        user1_id = 'test_user_1'
        user2_id = 'test_user_2'

        user1_threads_service = Threads.threads(user_id=user1_id)

        # 1. User1 creates a thread
        thread_name_by_user1 = "User1's Exclusive Thread"
        created_thread_orm_u1 = user1_threads_service.create_thread(name=thread_name_by_user1)
        assert created_thread_orm_u1.name == thread_name_by_user1
        assert created_thread_orm_u1.user_id == user1_id

        # Verify user1 can see it
        u1_threads = self.metadata.get_current_threads(user1_id)
        assert any(t['thread_id'] == created_thread_orm_u1.thread_id and t['name'] == thread_name_by_user1 for t in u1_threads)

        # Verify user2 cannot see it yet
        u2_threads_before_grant = self.metadata.get_current_threads(user2_id)
        assert not any(t['thread_id'] == created_thread_orm_u1.thread_id for t in u2_threads_before_grant)

        # 2. User1 grants User2 access to this thread with a specific name for User2
        name_for_user2_access = "Shared Thread (User2's View)"
        granted_to_u2_orm = user1_threads_service.grant_thread(
            thread_id=created_thread_orm_u1.thread_id,
            user_id=user2_id,
            name=name_for_user2_access
        )
        assert granted_to_u2_orm.thread_id == created_thread_orm_u1.thread_id
        assert granted_to_u2_orm.user_id == user2_id
        assert granted_to_u2_orm.name == name_for_user2_access

        # Verify user2 can now see it with their specific name
        u2_threads_after_grant = self.metadata.get_current_threads(user2_id)
        u2_thread_info = next((t for t in u2_threads_after_grant if t['thread_id'] == created_thread_orm_u1.thread_id), None)
        assert u2_thread_info is not None
        assert u2_thread_info['name'] == name_for_user2_access

        # Verify user1 still sees their original thread with their original name
        u1_threads_after_grant = self.metadata.get_current_threads(user1_id)
        u1_thread_info = next((t for t in u1_threads_after_grant if t['thread_id'] == created_thread_orm_u1.thread_id), None)
        assert u1_thread_info is not None
        assert u1_thread_info['name'] == thread_name_by_user1

        # 3. Test fail_if_missing=True: Granting a non-existent thread should fail
        with pytest.raises(Exception, match="not found in metadata"):
            self.metadata.grant_thread(
                thread_id="non_existent_thread_id_for_fail_test",
                user_id=user1_id,
                name="This Should Fail",
                fail_if_missing=True
            )

        # 4. Test granting again to user2, but updating the name for user2's access
        updated_name_for_user2 = "User2 Access - Updated Name"
        regranted_to_u2_orm = user1_threads_service.grant_thread(
            thread_id=created_thread_orm_u1.thread_id,
            user_id=user2_id,
            name=updated_name_for_user2
        )
        assert regranted_to_u2_orm.name == updated_name_for_user2

        u2_threads_final_check = self.metadata.get_current_threads(user2_id)
        u2_thread_info_final = next((t for t in u2_threads_final_check if t['thread_id'] == created_thread_orm_u1.thread_id), None)
        assert u2_thread_info_final is not None
        assert u2_thread_info_final['name'] == updated_name_for_user2

    def test_get_thread(self):
        thread_name_for_get = "Thread for Get Test"
        created_thread_orm = self.threads.create_thread(name=thread_name_for_get)
        assert created_thread_orm.thread_id is not None

        thread_dict = self.threads.get_thread(created_thread_orm.thread_id)
        assert thread_dict is not None
        assert thread_dict['thread_id'] == created_thread_orm.thread_id
        assert thread_dict['name'] == thread_name_for_get
        assert TEST_USER_ID in thread_dict['users']
