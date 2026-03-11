"""
Tests for the Scheduled Jobs feature.
Tests CRUD endpoints, runs endpoint, agent validation, and scheduler engine.
"""

import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

logger = logging.getLogger(__name__)

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_scheduled_jobs.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-scheduled-jobs')

# Import after setting environment
from fastapi.testclient import TestClient
from bondable.rest.main import app, create_access_token
from bondable.bond.config import Config


# Test configuration
TEST_USER_EMAIL = "scheduler-test@example.com"
TEST_USER_ID = "scheduler-test-user-123"
TEST_USER_B_EMAIL = "scheduler-test-b@example.com"
TEST_USER_B_ID = "scheduler-test-user-456"
TEST_AGENT_ID = "test-agent-id-001"


# --- Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Set up test database and clean up after session."""
    # Ensure tables are created
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'metadata'):
        provider.metadata.create_all()

    yield

    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers for user A."""
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Scheduler Test User",
        "provider": "okta",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def auth_headers_user_b():
    """Create authentication headers for user B."""
    token_data = {
        "sub": TEST_USER_B_EMAIL,
        "name": "Scheduler Test User B",
        "provider": "okta",
        "user_id": TEST_USER_B_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(autouse=True)
def mock_agent_access():
    """Mock agent access check to return True for all CRUD tests by default."""
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'agents'):
        with patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            yield
    else:
        yield


def _create_job(test_client, auth_headers, name="Test Job", schedule="0 9 * * *"):
    """Helper to create a job and return its response data."""
    payload = {
        "agent_id": TEST_AGENT_ID,
        "name": name,
        "prompt": f"Prompt for {name}",
        "schedule": schedule,
    }
    response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


# =============================================================================
# CRUD Tests
# =============================================================================

class TestScheduledJobsCRUD:
    """Test CRUD operations for scheduled jobs."""

    def test_list_jobs_empty(self, test_client, auth_headers):
        """Test listing jobs when none exist."""
        response = test_client.get("/scheduled-jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_job_success(self, test_client, auth_headers):
        """Test creating a scheduled job."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "Test Daily Report",
            "prompt": "Generate a daily summary report",
            "schedule": "0 9 * * *",
            "timezone": "UTC",
            "is_enabled": True,
            "timeout_seconds": 300,
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Daily Report"
        assert data["schedule"] == "0 9 * * *"
        assert data["agent_id"] == TEST_AGENT_ID
        assert data["is_enabled"] is True
        assert data["status"] == "pending"
        assert data["next_run_at"] is not None
        assert data["user_id"] == TEST_USER_ID

    def test_create_job_invalid_cron(self, test_client, auth_headers):
        """Test creating a job with invalid cron expression returns 422."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "Bad Schedule",
            "prompt": "Do something",
            "schedule": "invalid cron expression",
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_create_job_missing_fields(self, test_client, auth_headers):
        """Test creating a job with missing required fields returns 422."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            # Missing name, prompt, schedule
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_list_jobs_with_data(self, test_client, auth_headers):
        """Test listing jobs returns created jobs."""
        response = test_client.get("/scheduled-jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(j["name"] == "Test Daily Report" for j in data)

    def test_get_job_success(self, test_client, auth_headers):
        """Test getting a single job by ID."""
        job_data = _create_job(test_client, auth_headers, name="Get Test Job", schedule="0 */4 * * *")

        response = test_client.get(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_data["id"]
        assert data["name"] == "Get Test Job"

    def test_get_job_not_found(self, test_client, auth_headers):
        """Test getting a non-existent job returns 404."""
        response = test_client.get(f"/scheduled-jobs/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    def test_get_job_wrong_user(self, test_client, auth_headers, auth_headers_user_b):
        """Test that user B cannot access user A's job."""
        job_data = _create_job(test_client, auth_headers, name="User A's Job")

        # Try to access as user B
        response = test_client.get(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers_user_b)
        assert response.status_code == 404

    def test_user_scoped_list(self, test_client, auth_headers, auth_headers_user_b):
        """Test that users only see their own jobs."""
        # Create a job as user B
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "User B's Job",
            "prompt": "User B prompt",
            "schedule": "0 12 * * *",
        }
        test_client.post("/scheduled-jobs", json=payload, headers=auth_headers_user_b)

        # List as user B - should see only their job
        response = test_client.get("/scheduled-jobs", headers=auth_headers_user_b)
        assert response.status_code == 200
        data = response.json()
        assert all(j["user_id"] == TEST_USER_B_ID for j in data)

    def test_update_job_success(self, test_client, auth_headers):
        """Test updating a scheduled job."""
        job_data = _create_job(test_client, auth_headers, name="Update Me")

        update_payload = {
            "name": "Updated Name",
            "prompt": "Updated prompt",
        }
        response = test_client.put(f"/scheduled-jobs/{job_data['id']}", json=update_payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["prompt"] == "Updated prompt"
        assert data["schedule"] == "0 9 * * *"  # Unchanged

    def test_update_job_schedule_recomputes_next_run(self, test_client, auth_headers):
        """Test that updating the schedule recomputes next_run_at."""
        job_data = _create_job(test_client, auth_headers, name="Recompute Test")

        update_payload = {
            "schedule": "0 */2 * * *",  # Every 2 hours
        }
        response = test_client.put(f"/scheduled-jobs/{job_data['id']}", json=update_payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["schedule"] == "0 */2 * * *"
        assert data["next_run_at"] is not None

    def test_delete_job_success(self, test_client, auth_headers):
        """Test deleting a scheduled job."""
        job_data = _create_job(test_client, auth_headers, name="Delete Me")

        response = test_client.delete(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers)
        assert response.status_code == 204

        # Verify it's gone
        get_response = test_client.get(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_delete_job_wrong_user(self, test_client, auth_headers, auth_headers_user_b):
        """Test that user B cannot delete user A's job."""
        job_data = _create_job(test_client, auth_headers, name="Protected Job")

        # Try to delete as user B
        response = test_client.delete(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers_user_b)
        assert response.status_code == 404

        # Verify it still exists for user A
        get_response = test_client.get(f"/scheduled-jobs/{job_data['id']}", headers=auth_headers)
        assert get_response.status_code == 200


# =============================================================================
# Agent Validation Tests
# =============================================================================

class TestAgentValidation:
    """Test agent access validation on job creation."""

    @pytest.fixture(autouse=True)
    def mock_agent_access(self):
        """Override the module-level mock to NOT auto-allow agent access."""
        yield  # Don't mock — let the test control the mock

    def test_create_job_with_inaccessible_agent_returns_403(self, test_client, auth_headers):
        """Test creating a job with an agent the user can't access returns 403."""
        config = Config.config()
        provider = config.get_provider()

        with patch.object(provider.agents, 'can_user_access_agent', return_value=False):
            payload = {
                "agent_id": "inaccessible-agent-id",
                "name": "Bad Agent Job",
                "prompt": "Do something",
                "schedule": "0 9 * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 403
            assert "access denied" in response.json()["detail"].lower()

    def test_create_job_with_agent_check_exception_returns_403(self, test_client, auth_headers):
        """Test creating a job when agent check throws an exception returns 403."""
        config = Config.config()
        provider = config.get_provider()

        with patch.object(provider.agents, 'can_user_access_agent', side_effect=Exception("DB error")):
            payload = {
                "agent_id": "error-agent-id",
                "name": "Error Agent Job",
                "prompt": "Do something",
                "schedule": "0 9 * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 403


# =============================================================================
# Runs Endpoint Tests
# =============================================================================

class TestRunsEndpoint:
    """Test the /scheduled-jobs/{job_id}/runs endpoint."""

    def test_list_runs_empty(self, test_client, auth_headers):
        """Test listing runs for a job with no runs returns empty list."""
        job_data = _create_job(test_client, auth_headers, name="No Runs Job")

        response = test_client.get(f"/scheduled-jobs/{job_data['id']}/runs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_runs_not_found_for_wrong_user(self, test_client, auth_headers, auth_headers_user_b):
        """Test listing runs returns 404 if job belongs to different user."""
        job_data = _create_job(test_client, auth_headers, name="User A Runs Job")

        response = test_client.get(f"/scheduled-jobs/{job_data['id']}/runs", headers=auth_headers_user_b)
        assert response.status_code == 404

    def test_list_runs_not_found_for_nonexistent_job(self, test_client, auth_headers):
        """Test listing runs returns 404 for non-existent job."""
        response = test_client.get(f"/scheduled-jobs/{uuid.uuid4()}/runs", headers=auth_headers)
        assert response.status_code == 404

    def test_list_runs_with_session_state_status(self, test_client, auth_headers):
        """Test that run status is derived from thread session_state, not thread name."""
        from bondable.bond.providers.metadata import Thread, ScheduledJob as ScheduledJobModel

        job_data = _create_job(test_client, auth_headers, name="Runs Status Test")
        job_id = job_data["id"]

        # Manually insert a thread associated with this job, simulating a completed run
        config = Config.config()
        provider = config.get_provider()
        session = provider.metadata.get_db_session()
        try:
            thread = Thread(
                thread_id=f"run-thread-{uuid.uuid4()}",
                user_id=TEST_USER_ID,
                name="[Scheduled] Runs Status Test - 2026-03-10 09:00",
                scheduled_job_id=job_id,
                session_state={"scheduled_run_status": "completed"},
            )
            session.add(thread)
            session.commit()
        finally:
            session.close()

        response = test_client.get(f"/scheduled-jobs/{job_id}/runs", headers=auth_headers)
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) >= 1
        assert runs[0]["status"] == "completed"

    def test_list_runs_failed_status_from_session_state(self, test_client, auth_headers):
        """Test that failed run status is correctly read from session_state."""
        from bondable.bond.providers.metadata import Thread

        job_data = _create_job(test_client, auth_headers, name="Failed Run Test")
        job_id = job_data["id"]

        # Insert a thread with failed status
        config = Config.config()
        provider = config.get_provider()
        session = provider.metadata.get_db_session()
        try:
            thread = Thread(
                thread_id=f"fail-thread-{uuid.uuid4()}",
                user_id=TEST_USER_ID,
                name="[Scheduled] Failed Run Test - 2026-03-10 10:00",
                scheduled_job_id=job_id,
                session_state={"scheduled_run_status": "failed", "scheduled_run_error": "Agent timeout"},
            )
            session.add(thread)
            session.commit()
        finally:
            session.close()

        response = test_client.get(f"/scheduled-jobs/{job_id}/runs", headers=auth_headers)
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) >= 1
        # Find the failed run
        failed_run = next((r for r in runs if r["status"] == "failed"), None)
        assert failed_run is not None, "Expected a failed run but none found"

    def test_list_runs_null_status_without_session_state(self, test_client, auth_headers):
        """Test that run without session_state has null status (not incorrectly 'completed')."""
        from bondable.bond.providers.metadata import Thread

        job_data = _create_job(test_client, auth_headers, name="No Status Run Test")
        job_id = job_data["id"]

        # Insert a thread without session_state
        config = Config.config()
        provider = config.get_provider()
        session = provider.metadata.get_db_session()
        try:
            thread = Thread(
                thread_id=f"nostatus-thread-{uuid.uuid4()}",
                user_id=TEST_USER_ID,
                name="[Scheduled] No Status Run Test - 2026-03-10 11:00",
                scheduled_job_id=job_id,
                session_state={},
            )
            session.add(thread)
            session.commit()
        finally:
            session.close()

        response = test_client.get(f"/scheduled-jobs/{job_id}/runs", headers=auth_headers)
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) >= 1
        # The thread without scheduled_run_status in session_state should have null status
        nostatus_run = next((r for r in runs if r["thread_name"].startswith("[Scheduled] No Status")), None)
        assert nostatus_run is not None
        assert nostatus_run["status"] is None, "Expected null status for thread without session_state key"

    def test_list_runs_pagination(self, test_client, auth_headers):
        """Test runs endpoint respects offset and limit."""
        from bondable.bond.providers.metadata import Thread

        job_data = _create_job(test_client, auth_headers, name="Pagination Test")
        job_id = job_data["id"]

        config = Config.config()
        provider = config.get_provider()
        session = provider.metadata.get_db_session()
        try:
            for i in range(5):
                thread = Thread(
                    thread_id=f"page-thread-{uuid.uuid4()}",
                    user_id=TEST_USER_ID,
                    name=f"[Scheduled] Pagination Test - run {i}",
                    scheduled_job_id=job_id,
                    session_state={"scheduled_run_status": "completed"},
                )
                session.add(thread)
            session.commit()
        finally:
            session.close()

        # Get first 2
        response = test_client.get(
            f"/scheduled-jobs/{job_id}/runs?offset=0&limit=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Get next 2
        response = test_client.get(
            f"/scheduled-jobs/{job_id}/runs?offset=2&limit=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) == 2


# =============================================================================
# FK Cascade Tests
# =============================================================================

class TestFKCascade:
    """Test FK cascade behavior on job deletion."""

    def test_delete_job_with_associated_threads_succeeds(self, test_client, auth_headers):
        """Test that deleting a job with associated threads doesn't fail (SET NULL).
        This test verifies the ondelete='SET NULL' FK constraint."""
        from bondable.bond.providers.metadata import Thread

        job_data = _create_job(test_client, auth_headers, name="FK Cascade Test")
        job_id = job_data["id"]

        # Create threads associated with this job
        config = Config.config()
        provider = config.get_provider()
        session = provider.metadata.get_db_session()
        thread_id = f"fk-thread-{uuid.uuid4()}"
        try:
            thread = Thread(
                thread_id=thread_id,
                user_id=TEST_USER_ID,
                name="[Scheduled] FK Cascade Test - 2026-03-10 09:00",
                scheduled_job_id=job_id,
                session_state={"scheduled_run_status": "completed"},
            )
            session.add(thread)
            session.commit()
        finally:
            session.close()

        # Delete the job — should succeed, not raise IntegrityError
        response = test_client.delete(f"/scheduled-jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify the thread still exists but scheduled_job_id is NULL
        session = provider.metadata.get_db_session()
        try:
            thread_record = session.query(Thread).filter(
                Thread.thread_id == thread_id,
                Thread.user_id == TEST_USER_ID,
            ).first()
            assert thread_record is not None, "Thread should still exist after job deletion"
            # Note: SQLite doesn't enforce ON DELETE SET NULL by default,
            # so we verify the delete succeeded (the important part).
            # On PostgreSQL, scheduled_job_id would be set to NULL.
        finally:
            session.close()


# =============================================================================
# Cron Validation Tests
# =============================================================================

class TestCronValidation:
    """Test cron expression validation."""

    def test_valid_cron_expressions(self):
        """Test that valid cron expressions are accepted."""
        from croniter import croniter

        valid_expressions = [
            "0 * * * *",        # Every hour
            "0 */4 * * *",      # Every 4 hours
            "0 9 * * *",        # Daily at 9 AM
            "0 9 * * 1",        # Weekly on Monday
            "0 9 1 * *",        # First of month
            "*/5 * * * *",      # Every 5 minutes
            "0 0 * * *",        # Midnight daily
        ]
        for expr in valid_expressions:
            assert croniter.is_valid(expr), f"Expected '{expr}' to be valid"

    def test_invalid_cron_expressions(self):
        """Test that invalid cron expressions are rejected."""
        from croniter import croniter

        invalid_expressions = [
            "invalid",
            "* * *",
            "60 * * * *",
            "",
            "every hour",
        ]
        for expr in invalid_expressions:
            assert not croniter.is_valid(expr), f"Expected '{expr}' to be invalid"

    def test_next_run_computation(self):
        """Test that next_run_at is correctly computed."""
        from croniter import croniter

        now = datetime(2026, 3, 10, 12, 0, 0)
        cron = croniter("0 9 * * *", now)
        next_run = cron.get_next(datetime)
        # Next 9 AM after March 10, 2026 12:00 should be March 11, 2026 09:00
        assert next_run.hour == 9
        assert next_run.day == 11


# =============================================================================
# Scheduler Engine Tests
# =============================================================================

class TestSchedulerEngine:
    """Test the scheduler engine."""

    def test_scheduler_start_stop(self):
        """Test scheduler start and stop lifecycle."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)
        scheduler.start()
        assert not scheduler._stop_event.is_set()

        scheduler.stop()
        assert scheduler._stop_event.is_set()

    def test_poll_picks_up_due_jobs(self):
        """Test that _poll_and_execute picks up due jobs."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        # Create a mock session with a due job
        mock_session = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "test-job-1"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Test Job"
        mock_job.prompt = "Do something"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300
        mock_job.is_enabled = True
        mock_job.status = "pending"
        mock_job.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        # First query (due jobs): returns the job; second query (all running for zombie check): returns empty
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.with_for_update.return_value.limit.return_value.all.return_value = [mock_job]
        mock_query_result.filter.return_value.with_for_update.return_value.all.return_value = []
        mock_session.query.return_value = mock_query_result
        mock_metadata.get_db_session.return_value = mock_session

        # Mock _execute_job to prevent actual execution
        scheduler._execute_job_by_id = MagicMock()

        scheduler._poll_and_execute()

        # Verify the job was picked up and marked as running
        assert mock_job.status == "running"
        scheduler._execute_job_by_id.assert_called_once_with(mock_job.id, mock_job.name)

    def test_poll_skips_disabled_jobs(self):
        """Test that disabled jobs are not picked up."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        # Return no jobs (disabled/future jobs filtered by query)
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = []
        mock_metadata.get_db_session.return_value = mock_session

        scheduler._execute_job_by_id = MagicMock()
        scheduler._poll_and_execute()

        scheduler._execute_job_by_id.assert_not_called()

    def test_zombie_detection_uses_per_job_timeout(self):
        """Test that zombie detection uses each job's timeout_seconds * 2."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Job with 60s timeout, locked 130s ago — should be zombie (> 60*2=120)
        zombie_job = MagicMock()
        zombie_job.id = "zombie-1"
        zombie_job.timeout_seconds = 60
        zombie_job.locked_at = now - timedelta(seconds=130)
        zombie_job.status = "running"

        # Job with 300s timeout, locked 130s ago — should NOT be zombie (< 300*2=600)
        active_job = MagicMock()
        active_job.id = "active-1"
        active_job.timeout_seconds = 300
        active_job.locked_at = now - timedelta(seconds=130)
        active_job.status = "running"

        mock_session = MagicMock()
        # Due jobs query: empty
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.limit.return_value.all.return_value = []
        # Running jobs query (for zombie detection): return both
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [zombie_job, active_job]
        mock_metadata.get_db_session.return_value = mock_session

        scheduler._execute_job_by_id = MagicMock()
        scheduler._poll_and_execute()

        # Only the zombie job should be picked up
        assert zombie_job.status == "running"  # marked by poll
        scheduler._execute_job_by_id.assert_called_once()
        call_args = scheduler._execute_job_by_id.call_args[0]
        assert call_args[0] == "zombie-1"

    def test_execute_job_creates_thread(self):
        """Test that _execute_job creates a thread with correct name."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User, ScheduledJob as SJModel

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        # Mock user and job lookup
        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Test Job"
        mock_job.prompt = "Run this"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        # session.query().filter().first() returns job first, then user, then thread record
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job in _execute_job
            mock_user,   # User lookup
            MagicMock(), # Thread record for setting scheduled_job_id
            mock_job,    # Re-load job after stream_response (session may be stale)
            None,        # Thread record for _set_thread_run_status
        ]
        mock_metadata.get_db_session.return_value = mock_session

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.thread_id = "thread-123"
        mock_provider.threads.create_thread.return_value = mock_thread

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.stream_response.return_value = iter(["response chunk"])
        mock_provider.agents.get_agent.return_value = mock_agent
        mock_provider.agents.can_user_access_agent.return_value = True

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Verify thread was created
        mock_provider.threads.create_thread.assert_called_once()
        call_args = mock_provider.threads.create_thread.call_args
        assert call_args[1]["user_id"] == "test-user"
        assert "[Scheduled]" in call_args[1]["name"]

    def test_execute_job_records_failure(self):
        """Test that job failure is recorded correctly."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        # Use a single mock_job object so assertions work on the same reference
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Failing Job"
        mock_job.prompt = "Run this"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        # First session: execution (agent throws, gets rolled back + closed)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job in _execute_job
            mock_user,   # User lookup
        ]

        # Fresh session for _record_failure_by_id (no thread_id since agent failed before thread creation)
        mock_failure_session = MagicMock()
        mock_failure_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job by ID in _record_failure_by_id
            mock_job,    # Re-load job in _record_failure_with_session
        ]

        mock_metadata.get_db_session.side_effect = [
            mock_session,          # _execute_job_by_id initial session
            mock_failure_session,  # _record_failure_by_id fresh session
        ]

        # Mock agent that throws (before thread creation due to B1 reorder)
        mock_provider.agents.get_agent.side_effect = Exception("Agent not found")

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Job should be marked as failed
        assert mock_job.last_run_status == "failed"
        assert mock_job.status == "pending"
        assert mock_job.locked_by is None

    def test_execute_job_computes_next_run(self):
        """Test that next_run_at is recomputed after execution."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Test Job"
        mock_job.prompt = "Run"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300
        mock_job.next_run_at = None

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job
            mock_user,   # User lookup
            MagicMock(), # Thread record for scheduled_job_id
            mock_job,    # Re-load job after stream_response (session may be stale)
            None,        # Thread record for _set_thread_run_status
        ]
        mock_metadata.get_db_session.return_value = mock_session

        mock_thread = MagicMock()
        mock_thread.thread_id = "thread-123"
        mock_provider.threads.create_thread.return_value = mock_thread

        mock_agent = MagicMock()
        mock_agent.stream_response.return_value = iter(["done"])
        mock_provider.agents.get_agent.return_value = mock_agent
        mock_provider.agents.can_user_access_agent.return_value = True

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # next_run_at should have been set
        assert mock_job.next_run_at is not None
        assert mock_job.status == "pending"
        assert mock_job.last_run_status == "completed"

    def test_jwt_creation_has_correct_claims(self):
        """Test that JWT tokens created for jobs have correct claims."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User
        import jwt as pyjwt

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "google"

        # Call the JWT creation method
        token = scheduler._create_jwt_for_user(mock_user)

        # Decode and verify claims
        config = Config.config()
        jwt_config = config.get_jwt_config()
        decoded = pyjwt.decode(
            token,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            options={"verify_aud": False}
        )

        assert decoded["sub"] == "user@example.com"
        assert decoded["user_id"] == "user-123"
        assert decoded["name"] == "Test User"
        assert decoded["provider"] == "google"
        assert decoded["iss"] == "bond-ai"
        assert decoded["aud"] == "mcp-server"

    def test_compute_next_run_fallback_logs_warning(self):
        """Test that _compute_next_run logs a warning on fallback."""
        from bondable.bond.scheduler import JobScheduler

        with patch('bondable.bond.scheduler.LOGGER') as mock_logger:
            result = JobScheduler._compute_next_run("bad cron", tz="Invalid/Timezone")

            # Should return a datetime (fallback)
            assert isinstance(result, datetime)
            # Should have logged a warning
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Falling back" in warning_msg

    def test_execute_job_stores_run_status_on_thread(self):
        """Test that _execute_job stores run status in thread session_state."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Status Test"
        mock_job.prompt = "Run"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        # Track the thread record to verify session_state is set
        mock_thread_record = MagicMock()
        mock_thread_record.session_state = {}

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,            # Re-load job
            mock_user,           # User lookup
            mock_thread_record,  # Thread for scheduled_job_id
            mock_job,            # Re-load job after stream_response (session may be stale)
            mock_thread_record,  # Thread for _set_thread_run_status
        ]
        mock_metadata.get_db_session.return_value = mock_session

        mock_thread = MagicMock()
        mock_thread.thread_id = "thread-123"
        mock_provider.threads.create_thread.return_value = mock_thread

        mock_agent = MagicMock()
        mock_agent.stream_response.return_value = iter(["done"])
        mock_provider.agents.get_agent.return_value = mock_agent
        mock_provider.agents.can_user_access_agent.return_value = True

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Verify session_state was updated with run status
        assert mock_thread_record.session_state.get("scheduled_run_status") == "completed"

    def test_execute_job_no_orphaned_thread_on_agent_failure(self):
        """B1: Thread should NOT be created when agent validation fails."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "job-orphan-test"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "deleted-agent"
        mock_job.name = "Orphan Test"
        mock_job.prompt = "Run"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job
            mock_user,   # User lookup
        ]

        mock_failure_session = MagicMock()
        mock_failure_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,    # Re-load job by ID
            mock_job,    # Re-load job in _record_failure_with_session
        ]

        mock_metadata.get_db_session.side_effect = [
            mock_session,
            mock_failure_session,
        ]

        # Agent lookup returns None (agent deleted)
        mock_provider.agents.get_agent.return_value = None

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Verify thread was NOT created
        mock_provider.threads.create_thread.assert_not_called()
        # Job should be marked as failed
        assert mock_job.last_run_status == "failed"

    def test_execute_job_stores_failed_status_on_thread(self):
        """B2: Failed run should write status to thread session_state."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "job-fail-status"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Fail Status Test"
        mock_job.prompt = "Run"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        mock_thread_record = MagicMock()
        mock_thread_record.session_state = {}

        # First session: used during execution (then rolled back and closed)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,            # Re-load job
            mock_user,           # User lookup
            mock_thread_record,  # Thread for scheduled_job_id
        ]

        # Second session: used by _record_failure_by_id (fresh session)
        mock_failure_session = MagicMock()
        mock_failure_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,            # Re-load job by ID in _record_failure_by_id
            mock_thread_record,  # Thread for _set_thread_run_status (failed)
            mock_job,            # Re-load job in _record_failure_with_session
        ]

        mock_metadata.get_db_session.side_effect = [
            mock_session,          # _execute_job_by_id initial session
            mock_failure_session,  # _record_failure_by_id fresh session
        ]

        # Thread creation succeeds
        mock_thread = MagicMock()
        mock_thread.thread_id = "thread-fail-123"
        mock_provider.threads.create_thread.return_value = mock_thread

        # Agent succeeds but stream_response raises
        mock_agent = MagicMock()
        mock_agent.stream_response.side_effect = Exception("Stream failed")
        mock_provider.agents.get_agent.return_value = mock_agent
        mock_provider.agents.can_user_access_agent.return_value = True

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Verify original session was rolled back and closed
        mock_session.rollback.assert_called()
        mock_session.close.assert_called()
        # Verify thread session_state has failed status (via fresh session)
        assert mock_thread_record.session_state.get("scheduled_run_status") == "failed"
        assert "Stream failed" in mock_thread_record.session_state.get("scheduled_run_error", "")
        # Job should also be marked as failed
        assert mock_job.last_run_status == "failed"

    def test_execute_job_logs_warning_when_job_disappears(self):
        """B3: Correct warning logged when job is deleted mid-execution."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        # Re-load returns None (job deleted between poll and execute)
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_metadata.get_db_session.return_value = mock_session

        mock_job = MagicMock()
        mock_job.id = "disappearing-job"
        mock_job.name = "Disappearing Job"

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.LOGGER') as mock_logger:
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

            # Should log warning with the original job_id
            mock_logger.warning.assert_called_once()
            warning_args = mock_logger.warning.call_args[0]
            assert "disappearing-job" in warning_args[1]

        # Thread should NOT have been created
        mock_provider.threads.create_thread.assert_not_called()

    def test_poll_captures_ids_before_session_close(self):
        """Regression: _poll_and_execute must capture job IDs before closing
        the session to avoid DetachedInstanceError on ORM objects."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        mock_job = MagicMock()
        mock_job.id = "detach-test-job"
        mock_job.name = "Detach Test"
        mock_job.is_enabled = True
        mock_job.next_run_at = now - timedelta(minutes=5)
        mock_job.status = "pending"
        mock_job.timeout_seconds = 300
        mock_job.locked_at = None

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.limit.return_value.all.return_value = [mock_job]
        mock_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = []
        mock_metadata.get_db_session.return_value = mock_session

        # Mock _execute_job_by_id to verify it receives IDs, not ORM objects
        scheduler._execute_job_by_id = MagicMock()
        scheduler._poll_and_execute()

        scheduler._execute_job_by_id.assert_called_once_with("detach-test-job", "Detach Test")

    def test_execute_job_session_rollback_on_commit_failure(self):
        """Regression (R3-B2): If session.commit() fails mid-execution,
        the except block must rollback before recording failure."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "okta"

        mock_job = MagicMock()
        mock_job.id = "rollback-test"
        mock_job.user_id = "test-user"
        mock_job.agent_id = "test-agent"
        mock_job.name = "Rollback Test"
        mock_job.prompt = "Run"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_job.timeout_seconds = 300

        mock_thread_record = MagicMock()
        mock_thread_record.session_state = {}
        mock_thread_record.scheduled_job_id = None

        # First commit fails (scheduled_job_id commit), triggering except block
        mock_session.commit.side_effect = Exception("DB commit failed")

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,            # Re-load job
            mock_user,           # User lookup
            mock_thread_record,  # Thread for scheduled_job_id
        ]

        # Fresh session for _record_failure_by_id
        mock_failure_session = MagicMock()
        mock_failure_session.query.return_value.filter.return_value.first.side_effect = [
            mock_job,            # Re-load job by ID
            mock_thread_record,  # Thread for _set_thread_run_status (failed)
            mock_job,            # Re-load job in _record_failure_with_session
        ]

        mock_metadata.get_db_session.side_effect = [
            mock_session,          # _execute_job_by_id initial session
            mock_failure_session,  # _record_failure_by_id fresh session
        ]

        mock_thread = MagicMock()
        mock_thread.thread_id = "thread-rollback"
        mock_provider.threads.create_thread.return_value = mock_thread
        mock_provider.agents.get_agent.return_value = MagicMock()
        mock_provider.agents.can_user_access_agent.return_value = True

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch('bondable.bond.scheduler.create_access_token', return_value="mock-token"):
            scheduler._execute_job_by_id(mock_job.id, mock_job.name)

        # Original session must be rolled back and closed
        mock_session.rollback.assert_called()
        mock_session.close.assert_called()
        # Job should be marked as failed
        assert mock_job.last_run_status == "failed"

    def test_record_failure_by_id_uses_fresh_session(self):
        """Regression: _record_failure_by_id must load the job from a
        fresh session since the original job object is detached."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "failure-by-id-test"
        mock_job.schedule = "0 * * * *"
        mock_job.timezone = "UTC"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_job
        mock_metadata.get_db_session.return_value = mock_session

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)
        scheduler._record_failure_by_id("failure-by-id-test", "Something broke")

        # Verify it queried for the job by ID
        mock_session.query.assert_called()
        # Verify it recorded the failure
        assert mock_job.last_run_status == "failed"
        assert mock_job.status == "pending"
        mock_session.commit.assert_called()
        mock_session.close.assert_called()


class TestDefaultAgentSchedulingBlocked:
    """Regression: The default (Home) agent must not be schedulable."""

    @pytest.fixture(autouse=True)
    def mock_agent_access_for_default(self):
        """Override module-level mock so we can control agent record lookup."""
        yield

    def test_create_job_with_default_agent_returns_403(self, test_client, auth_headers):
        """Scheduling the default Home agent must return 403."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = True

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record):
            payload = {
                "agent_id": "home-agent-id",
                "name": "Home Agent Job",
                "prompt": "Do something",
                "schedule": "0 9 * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 403
            assert "default" in response.json()["detail"].lower() or "home" in response.json()["detail"].lower()

    def test_create_job_with_non_default_agent_allowed(self, test_client, auth_headers):
        """Non-default agents should pass the default-agent check."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            payload = {
                "agent_id": TEST_AGENT_ID,
                "name": "Normal Agent Job",
                "prompt": "Do something",
                "schedule": "0 9 * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 201


class TestTimezoneAndTimeoutValidation:
    """Tests for timezone and timeout_seconds validation on create/update."""

    def test_create_job_with_invalid_timezone_returns_422(self, test_client, auth_headers):
        """Creating a job with an invalid timezone must return 422."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "Bad TZ Job",
            "prompt": "Run",
            "schedule": "0 9 * * *",
            "timezone": "Invalid/Nowhere",
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422
        assert "Invalid timezone" in response.json()["detail"]

    def test_create_job_with_low_timeout_returns_422(self, test_client, auth_headers):
        """Creating a job with timeout_seconds < 60 must return 422."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "Low Timeout Job",
            "prompt": "Run",
            "schedule": "0 9 * * *",
            "timeout_seconds": 30,
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422
        assert "timeout_seconds" in response.json()["detail"]

    def test_update_job_with_invalid_timezone_returns_422(self, test_client, auth_headers):
        """Updating a job with an invalid timezone must return 422."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        # First create a valid job
        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            create_resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": "TZ Update Test",
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            job_id = create_resp.json()["id"]

        # Then update with invalid timezone
        update_resp = test_client.put(f"/scheduled-jobs/{job_id}", json={
            "timezone": "Fake/Zone",
        }, headers=auth_headers)
        assert update_resp.status_code == 422
        assert "Invalid timezone" in update_resp.json()["detail"]

    def test_update_job_with_low_timeout_returns_422(self, test_client, auth_headers):
        """Updating a job with timeout_seconds < 60 must return 422."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        # First create a valid job
        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            create_resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": "Timeout Update Test",
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            job_id = create_resp.json()["id"]

        # Then update with low timeout
        update_resp = test_client.put(f"/scheduled-jobs/{job_id}", json={
            "timeout_seconds": 10,
        }, headers=auth_headers)
        assert update_resp.status_code == 422
        assert "timeout_seconds" in update_resp.json()["detail"]

    def test_create_job_with_valid_timezone_succeeds(self, test_client, auth_headers):
        """Creating a job with a valid timezone should succeed."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            payload = {
                "agent_id": TEST_AGENT_ID,
                "name": "Valid TZ Job",
                "prompt": "Run",
                "schedule": "0 9 * * *",
                "timezone": "America/Chicago",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 201
            assert response.json()["timezone"] == "America/Chicago"

    def test_create_job_with_high_timeout_returns_422(self, test_client, auth_headers):
        """Creating a job with timeout_seconds > MAX returns 422."""
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "High Timeout Job",
            "prompt": "Run",
            "schedule": "0 9 * * *",
            "timeout_seconds": 99999,
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422
        assert "timeout_seconds" in response.json()["detail"]

    def test_update_job_with_high_timeout_returns_422(self, test_client, auth_headers):
        """Updating a job with timeout_seconds > MAX returns 422."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            create_resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": "High Timeout Update Test",
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            job_id = create_resp.json()["id"]

        update_resp = test_client.put(f"/scheduled-jobs/{job_id}", json={
            "timeout_seconds": 99999,
        }, headers=auth_headers)
        assert update_resp.status_code == 422
        assert "timeout_seconds" in update_resp.json()["detail"]


class TestScheduleIntervalAndLimits:
    """Tests for minimum schedule interval and per-user job limits."""

    @patch('bondable.rest.routers.scheduled_jobs.MIN_SCHEDULE_INTERVAL_MINUTES', 60)
    def test_create_job_too_frequent_returns_422(self, test_client, auth_headers):
        """Schedule more frequent than MIN_SCHEDULE_INTERVAL_MINUTES is rejected."""
        # Min set to 60 min, so */5 (every 5 min) should be rejected
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": "Too Frequent Job",
            "prompt": "Run",
            "schedule": "*/5 * * * *",
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422
        assert "too frequent" in response.json()["detail"].lower() or "interval" in response.json()["detail"].lower()

    def test_create_job_hourly_succeeds(self, test_client, auth_headers):
        """Hourly schedule (60 min interval) should be allowed with default min of 60."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            payload = {
                "agent_id": TEST_AGENT_ID,
                "name": "Hourly Job",
                "prompt": "Run",
                "schedule": "0 * * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 201

    def test_create_job_frequent_allowed_when_env_lowered(self, test_client, auth_headers):
        """When MIN_SCHEDULE_INTERVAL_MINUTES is lowered, frequent schedules are allowed."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch('bondable.rest.routers.scheduled_jobs.MIN_SCHEDULE_INTERVAL_MINUTES', 1), \
             patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            payload = {
                "agent_id": TEST_AGENT_ID,
                "name": "Frequent OK Job",
                "prompt": "Run",
                "schedule": "*/5 * * * *",
            }
            response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
            assert response.status_code == 201

    @patch('bondable.rest.routers.scheduled_jobs.MIN_SCHEDULE_INTERVAL_MINUTES', 60)
    def test_update_job_too_frequent_returns_422(self, test_client, auth_headers):
        """Updating schedule to too-frequent interval is rejected."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            create_resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": "Update Freq Test",
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            job_id = create_resp.json()["id"]

        update_resp = test_client.put(f"/scheduled-jobs/{job_id}", json={
            "schedule": "*/2 * * * *",
        }, headers=auth_headers)
        assert update_resp.status_code == 422


class TestPerUserJobLimit:
    """Tests for per-user job limit enforcement."""

    def test_per_user_job_limit_enforced(self, test_client, auth_headers):
        """Creating more jobs than MAX_JOBS_PER_USER should return 422."""
        config = Config.config()
        provider = config.get_provider()

        # Count existing jobs for this user so we set the limit just above
        from bondable.bond.providers.metadata import ScheduledJob as SJModel
        session = provider.metadata.get_db_session()
        existing_count = session.query(SJModel).filter(
            SJModel.user_id == TEST_USER_ID
        ).count()
        session.close()

        # Set limit to existing_count + 2 so we can create exactly 2 more
        limit = existing_count + 2

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch('bondable.rest.routers.scheduled_jobs.MAX_JOBS_PER_USER', limit), \
             patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            # Create 2 jobs (filling to the limit)
            created_ids = []
            for i in range(2):
                resp = test_client.post("/scheduled-jobs", json={
                    "agent_id": TEST_AGENT_ID,
                    "name": f"Limit Test Job {uuid.uuid4().hex[:8]}",
                    "prompt": "Run",
                    "schedule": "0 9 * * *",
                }, headers=auth_headers)
                assert resp.status_code == 201, f"Job {i+1} should succeed"
                created_ids.append(resp.json()["id"])

            # Next job should fail with 422
            resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": f"Over Limit Job {uuid.uuid4().hex[:8]}",
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert resp.status_code == 422
            assert "maximum" in resp.json()["detail"].lower()

            # Clean up created jobs
            for job_id in created_ids:
                test_client.delete(f"/scheduled-jobs/{job_id}", headers=auth_headers)


class TestMinIntervalBoundary:
    """Tests for exact boundary of minimum schedule interval."""

    @patch('bondable.rest.routers.scheduled_jobs.MAX_JOBS_PER_USER', 100)
    @patch('bondable.rest.routers.scheduled_jobs.MIN_SCHEDULE_INTERVAL_MINUTES', 60)
    def test_exact_boundary_interval_accepted(self, test_client, auth_headers):
        """A schedule with exactly MIN_SCHEDULE_INTERVAL_MINUTES gap should be accepted (strict < comparison)."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            # "0 */1 * * *" runs every hour (60-min gap) — should be accepted
            resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": f"Boundary Test {uuid.uuid4().hex[:8]}",
                "prompt": "Run",
                "schedule": "0 */1 * * *",
            }, headers=auth_headers)
            assert resp.status_code == 201
            # Clean up
            test_client.delete(f"/scheduled-jobs/{resp.json()['id']}", headers=auth_headers)

    @patch('bondable.rest.routers.scheduled_jobs.MIN_SCHEDULE_INTERVAL_MINUTES', 60)
    def test_just_under_boundary_rejected(self, test_client, auth_headers):
        """A schedule with gap just under MIN_SCHEDULE_INTERVAL_MINUTES should be rejected."""
        # "*/59 * * * *" fires every 59 minutes — just under the 60-min boundary
        payload = {
            "agent_id": TEST_AGENT_ID,
            "name": f"Under Boundary {uuid.uuid4().hex[:8]}",
            "prompt": "Run",
            "schedule": "*/59 * * * *",
        }
        response = test_client.post("/scheduled-jobs", json=payload, headers=auth_headers)
        assert response.status_code == 422


class TestDeleteWhileRunning:
    """Tests for delete-while-running guard."""

    @patch('bondable.rest.routers.scheduled_jobs.MAX_JOBS_PER_USER', 100)
    def test_delete_running_job_returns_409(self, test_client, auth_headers):
        """Deleting a job with status='running' must return 409 Conflict."""
        config = Config.config()
        provider = config.get_provider()

        mock_record = MagicMock()
        mock_record.is_default = False

        # Create a fresh job with a unique name
        unique_name = f"Running Job {uuid.uuid4().hex[:8]}"
        with patch.object(provider.agents, 'get_agent_record', return_value=mock_record), \
             patch.object(provider.agents, 'can_user_access_agent', return_value=True):
            create_resp = test_client.post("/scheduled-jobs", json={
                "agent_id": TEST_AGENT_ID,
                "name": unique_name,
                "prompt": "Run",
                "schedule": "0 9 * * *",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            job_id = create_resp.json()["id"]

        # Manually set job to running in the DB
        from bondable.bond.providers.metadata import ScheduledJob as SJModel
        session = provider.metadata.get_db_session()
        job = session.query(SJModel).filter(SJModel.id == job_id).first()
        job.status = "running"
        session.commit()
        session.close()

        # Attempt to delete — should fail with 409
        delete_resp = test_client.delete(f"/scheduled-jobs/{job_id}", headers=auth_headers)
        assert delete_resp.status_code == 409
        assert "running" in delete_resp.json()["detail"].lower()

        # Reset status so cleanup works
        session = provider.metadata.get_db_session()
        job = session.query(SJModel).filter(SJModel.id == job_id).first()
        job.status = "pending"
        session.commit()
        session.close()

        # Now delete should succeed
        delete_resp = test_client.delete(f"/scheduled-jobs/{job_id}", headers=auth_headers)
        assert delete_resp.status_code == 204


class TestSQLiteDialectGuard:
    """Tests for SQLite dialect detection in scheduler."""

    def test_scheduler_detects_sqlite(self):
        """Scheduler should detect SQLite and disable FOR UPDATE."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        # Simulate SQLite engine
        mock_session = MagicMock()
        mock_engine = MagicMock()
        mock_engine.dialect.name = "sqlite"
        mock_session.get_bind.return_value = mock_engine
        mock_metadata.get_db_session.return_value = mock_session

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)
        # Trigger lazy detection
        assert scheduler._detect_sqlite() is True

    def test_scheduler_detects_postgres(self):
        """Scheduler should detect PostgreSQL and keep FOR UPDATE enabled."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        mock_session = MagicMock()
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_session.get_bind.return_value = mock_engine
        mock_metadata.get_db_session.return_value = mock_session

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)
        # Trigger lazy detection
        assert scheduler._detect_sqlite() is False


class TestJWTExpiryMatchesTimeout:
    """Test that JWT expiry matches job timeout."""

    def test_jwt_expiry_scales_with_timeout(self):
        """JWT token expiry should be at least timeout_seconds + buffer."""
        from bondable.bond.scheduler import JobScheduler
        from bondable.bond.providers.metadata import User
        import jwt as pyjwt

        mock_metadata = MagicMock()
        mock_provider = MagicMock()

        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"
        mock_user.sign_in_method = "google"

        # With default 300s timeout → max(15, 300/60+5) = max(15, 10) = 15 min
        token_short = scheduler._create_jwt_for_user(mock_user, timeout_seconds=300)

        # With 3600s timeout → max(15, 3600/60+5) = max(15, 65) = 65 min
        token_long = scheduler._create_jwt_for_user(mock_user, timeout_seconds=3600)

        config = Config.config()
        jwt_config = config.get_jwt_config()

        decoded_short = pyjwt.decode(
            token_short,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            options={"verify_aud": False}
        )
        decoded_long = pyjwt.decode(
            token_long,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            options={"verify_aud": False}
        )

        # Long timeout JWT should expire later than short timeout JWT
        assert decoded_long["exp"] > decoded_short["exp"]
        # The difference between the two expiries should be ~50 min (65 - 15)
        exp_diff_minutes = (decoded_long["exp"] - decoded_short["exp"]) / 60
        assert exp_diff_minutes >= 45  # at least 45 min difference
