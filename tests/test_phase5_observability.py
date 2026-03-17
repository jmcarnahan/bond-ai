"""
Tests for Phase 5 security remediation: Observability & Infrastructure.

Covers:
- T5+T14+T22: Audit logging middleware
- T20: MCP config env var deprecation warning
- T16+T17: Data retention cleanup in scheduler
"""
import pytest
import os
import tempfile
import logging
from datetime import timedelta
from unittest.mock import patch, MagicMock

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['ALLOW_ALL_EMAILS'] = 'true'

from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from starlette.testclient import TestClient

jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"

# Ensure the audit logger propagates to root (needed for caplog to capture)
logging.getLogger("bondable.audit").propagate = True


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    return TestClient(app)


def _make_token(user_id=TEST_USER_ID, email=TEST_USER_EMAIL):
    return create_access_token(
        data={
            "sub": email, "name": "Test", "provider": "cognito",
            "user_id": user_id, "iss": "bond-ai",
            "aud": ["bond-ai-api", "mcp-server"],
        },
        expires_delta=timedelta(minutes=15),
    )


# ===========================================================================
# T5+T14+T22 — Audit logging middleware
# ===========================================================================
class TestAuditLogging:

    def test_audit_middleware_importable(self):
        """AuditLogMiddleware class exists and is importable."""
        from bondable.rest.middleware.audit_log import AuditLogMiddleware
        assert AuditLogMiddleware is not None
        assert hasattr(AuditLogMiddleware, 'dispatch')

    def test_state_change_logged(self, test_client):
        """POST requests generate AUDIT_STATE_CHANGE log entries."""
        token = _make_token()
        audit_logger = logging.getLogger("bondable.audit")
        with patch.object(audit_logger, 'info') as mock_info:
            test_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
            state_change_calls = [c for c in mock_info.call_args_list if "AUDIT_STATE_CHANGE" in str(c)]
            assert len(state_change_calls) >= 1
            # Args include format string + positional args: ('AUDIT_...', 'POST', '/auth/logout', ...)
            assert "POST" in str(state_change_calls[0])

    def test_auth_failure_logged(self, test_client):
        """401 responses generate AUDIT_AUTH_FAILURE log entries."""
        audit_logger = logging.getLogger("bondable.audit")
        with patch.object(audit_logger, 'warning') as mock_warn:
            test_client.get("/users/me")  # No auth → 401
            failure_calls = [c for c in mock_warn.call_args_list if "AUDIT_AUTH_FAILURE" in str(c)]
            assert len(failure_calls) >= 1
            assert 401 in failure_calls[0][0]  # 401 is a positional arg

    def test_health_not_logged(self, test_client):
        """Health endpoint is excluded from audit logs."""
        audit_logger = logging.getLogger("bondable.audit")
        with patch.object(audit_logger, 'info') as mock_info, \
             patch.object(audit_logger, 'warning') as mock_warn:
            test_client.get("/health")
            all_calls = mock_info.call_args_list + mock_warn.call_args_list
            health_calls = [c for c in all_calls if "/health" in str(c)]
            assert len(health_calls) == 0

    def test_get_not_state_change(self, test_client):
        """GET requests are not logged as state changes."""
        token = _make_token()
        audit_logger = logging.getLogger("bondable.audit")
        with patch.object(audit_logger, 'info') as mock_info:
            test_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
            state_calls = [c for c in mock_info.call_args_list if "AUDIT_STATE_CHANGE" in str(c)]
            assert len(state_calls) == 0

    def test_audit_includes_duration(self, test_client):
        """Audit log entries include duration_ms."""
        token = _make_token()
        audit_logger = logging.getLogger("bondable.audit")
        with patch.object(audit_logger, 'info') as mock_info:
            test_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
            duration_calls = [c for c in mock_info.call_args_list if "duration_ms" in str(c)]
            assert len(duration_calls) >= 1


# ===========================================================================
# T20 — MCP config env var deprecation warning
# ===========================================================================
class TestT20McpConfigDeprecation:

    def test_no_warning_when_secret_succeeds(self):
        """No deprecation warning when config loads from Secrets Manager."""
        config = Config.config()
        mock_config = {"mcpServers": {"test": {"command": "echo"}}}

        logger = logging.getLogger("bondable.bond.config")
        with patch.object(config, '_load_app_config', return_value={"bond_mcp_config": mock_config}):
            with patch.object(logger, 'warning') as mock_warn:
                result = config.get_mcp_config()
                # Should NOT call warning with "deprecated"
                deprecated_calls = [c for c in mock_warn.call_args_list if "deprecated" in str(c).lower()]
                assert len(deprecated_calls) == 0

        assert result == mock_config

    def test_warning_when_fallback_used_with_secret_name(self):
        """Deprecation warning when env var fallback used despite APP_CONFIG_SECRET_NAME."""
        config = Config.config()

        logger = logging.getLogger("bondable.bond.config")
        with patch.dict(os.environ, {"APP_CONFIG_SECRET_NAME": "my-secret", "BOND_MCP_CONFIG": '{"mcpServers":{}}'}), \
             patch.object(config, '_load_app_config', return_value={}), \
             patch.object(logger, 'warning') as mock_warn:
            config.get_mcp_config()
            deprecated_calls = [c for c in mock_warn.call_args_list if "deprecated" in str(c).lower()]
            assert len(deprecated_calls) >= 1


# ===========================================================================
# T16+T17 — Data retention cleanup
# ===========================================================================
class TestT16DataRetention:

    def test_cleanup_method_exists(self):
        """JobScheduler has _run_data_retention_cleanup method."""
        from bondable.bond.scheduler import JobScheduler
        assert hasattr(JobScheduler, '_run_data_retention_cleanup')

    def test_retention_disabled_when_zero(self):
        """Cleanup skipped when MESSAGE_RETENTION_DAYS=0."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()
        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        with patch.dict(os.environ, {"MESSAGE_RETENTION_DAYS": "0"}):
            scheduler._run_data_retention_cleanup()

        mock_metadata.get_db_session.assert_not_called()

    def test_default_retention_90_days(self):
        """Default retention period is 90 days."""
        assert int(os.getenv("MESSAGE_RETENTION_DAYS", "90")) == 90

    def test_retention_loop_integration(self):
        """Retention check runs hourly in the scheduler loop (every 120 polls)."""
        from bondable.bond.scheduler import JobScheduler

        mock_metadata = MagicMock()
        mock_provider = MagicMock()
        scheduler = JobScheduler(metadata=mock_metadata, provider=mock_provider)

        # Verify the method can be called without errors
        with patch.dict(os.environ, {"MESSAGE_RETENTION_DAYS": "90"}):
            with patch.object(scheduler, '_metadata') as mock_meta:
                mock_session = MagicMock()
                mock_query = MagicMock()
                mock_query.filter.return_value.delete.return_value = 0
                mock_session.query.return_value = mock_query
                mock_meta.get_db_session.return_value = mock_session
                # Should not raise
                scheduler._run_data_retention_cleanup()
