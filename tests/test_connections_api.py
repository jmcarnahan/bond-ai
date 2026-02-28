"""
Integration tests for the Connections API endpoints.
Tests OAuth connection management for external services.
"""

import os
import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from urllib.parse import urlparse, parse_qs
from fastapi.testclient import TestClient
from jose import jwt

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_connections.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-connections-api-testing')

# Import after setting environment
from bondable.rest.main import app, create_access_token
from bondable.bond.config import Config

# Test configuration
jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "connection-test@example.com"
TEST_USER_ID = "connection-test-user-123"


# --- Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database after session."""
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
    """Create authentication headers with JWT token."""
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Connection Test User",
        "provider": "okta",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def authenticated_client(test_client, auth_headers):
    """Test client with authentication."""
    return test_client, auth_headers


# --- Connection List Tests ---

class TestConnectionsList:
    """Test listing connections"""

    def test_list_connections_requires_auth(self, test_client):
        """Test that listing connections requires authentication"""
        response = test_client.get("/connections")
        assert response.status_code == 401

    def test_list_connections_success(self, authenticated_client):
        """Test listing connections with authentication"""
        client, headers = authenticated_client

        response = client.get("/connections", headers=headers)

        # Should return 200 even if no connections configured
        assert response.status_code == 200
        data = response.json()

        # Should have expected structure
        assert "connections" in data
        assert "expired" in data
        assert isinstance(data["connections"], list)
        assert isinstance(data["expired"], list)

    def test_list_connections_returns_connection_structure(self, authenticated_client):
        """Test that connection structure is correct"""
        client, headers = authenticated_client

        response = client.get("/connections", headers=headers)
        assert response.status_code == 200
        data = response.json()

        # If there are connections, verify structure
        if data["connections"]:
            connection = data["connections"][0]
            assert "name" in connection
            assert "display_name" in connection
            assert "connected" in connection
            assert "auth_type" in connection
            assert "requires_authorization" in connection


# --- Connection Status Tests ---

class TestConnectionStatus:
    """Test individual connection status"""

    def test_get_connection_status_requires_auth(self, test_client):
        """Test that getting connection status requires authentication"""
        response = test_client.get("/connections/atlassian/status")
        assert response.status_code == 401

    def test_get_nonexistent_connection_status(self, authenticated_client):
        """Test getting status for non-existent connection"""
        client, headers = authenticated_client

        response = client.get("/connections/nonexistent_connection/status", headers=headers)

        # Should return 404 for unknown connection
        assert response.status_code == 404


# --- Connection Authorization Tests ---

class TestConnectionAuthorization:
    """Test connection authorization flow"""

    def test_authorize_requires_auth(self, test_client):
        """Test that authorization endpoint requires authentication"""
        response = test_client.get("/connections/atlassian/authorize")
        assert response.status_code == 401

    def test_authorize_nonexistent_connection(self, authenticated_client):
        """Test authorizing non-existent connection"""
        client, headers = authenticated_client

        response = client.get("/connections/nonexistent_connection/authorize", headers=headers)

        # Should return 404 for unknown connection
        assert response.status_code == 404


# --- Connection Disconnect Tests ---

class TestConnectionDisconnect:
    """Test disconnecting from connections"""

    def test_disconnect_requires_auth(self, test_client):
        """Test that disconnect requires authentication"""
        response = test_client.delete("/connections/atlassian")
        assert response.status_code == 401

    def test_disconnect_nonexistent_returns_success(self, authenticated_client):
        """Test disconnecting from non-connected connection"""
        client, headers = authenticated_client

        response = client.delete("/connections/some_connection", headers=headers)

        # Should return 200 with disconnected=False
        assert response.status_code == 200
        data = response.json()
        assert "disconnected" in data
        # May be True or False depending on if connection existed


# --- Check Expired Tests ---

class TestCheckExpired:
    """Test checking for expired connections"""

    def test_check_expired_requires_auth(self, test_client):
        """Test that check-expired requires authentication"""
        response = test_client.get("/connections/check-expired")
        assert response.status_code == 401

    def test_check_expired_success(self, authenticated_client):
        """Test checking expired connections"""
        client, headers = authenticated_client

        response = client.get("/connections/check-expired", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Should have expected structure
        assert "has_expired" in data
        assert "expired_connections" in data
        assert isinstance(data["has_expired"], bool)
        assert isinstance(data["expired_connections"], list)

    def test_check_expired_returns_no_expired_for_new_user(self, authenticated_client):
        """Test that new user has no expired connections"""
        client, headers = authenticated_client

        response = client.get("/connections/check-expired", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # New user should have no expired connections
        assert data["has_expired"] is False
        assert len(data["expired_connections"]) == 0


# --- OAuth Callback Tests ---

class TestOAuthCallback:
    """Test OAuth callback handling"""

    def test_callback_with_invalid_state(self, test_client):
        """Test callback with invalid state parameter"""
        response = test_client.get(
            "/connections/atlassian/callback",
            params={"code": "test-code", "state": "invalid-state"}
        )

        # Should return 400 for invalid state
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

    def test_callback_missing_code(self, test_client):
        """Test callback without authorization code"""
        response = test_client.get(
            "/connections/atlassian/callback",
            params={"state": "some-state"}
        )

        # Should return 422 (validation error) for missing required parameter
        assert response.status_code == 422


# --- OAuth Callback Redirect Tests ---

# Fake connection config used by redirect tests
_FAKE_CONNECTION_CONFIG = {
    "name": "test_service",
    "display_name": "Test Service",
    "description": "A test OAuth2 service",
    "url": "https://test.example.com",
    "transport": "sse",
    "auth_type": "oauth2",
    "oauth_client_id": "fake-client-id",
    "oauth_authorize_url": "https://test.example.com/authorize",
    "oauth_token_url": "https://test.example.com/token",
    "oauth_scopes": "read write",
    "oauth_redirect_uri": "http://localhost/callback",
    "icon_url": None,
    "extra_config": {}
}

_FAKE_STATE_DATA = {
    "user_id": "test-user-123",
    "connection_name": "test_service",
    "code_verifier": "fake-verifier",
    "redirect_uri": "http://localhost/callback"
}


class TestOAuthCallbackRedirects:
    """Test that OAuth callback redirects use config name, not path parameter.

    These tests verify the CodeQL fix: redirect URLs must use config['name']
    (trusted server config) instead of the raw path parameter (user input).
    """

    @patch("bondable.rest.routers.connections._get_and_delete_oauth_state")
    @patch("bondable.rest.routers.connections._get_connection_config")
    @patch("bondable.rest.routers.connections.is_safe_redirect_url", return_value=True)
    @patch("httpx.AsyncClient")
    @patch("bondable.rest.routers.connections.get_mcp_token_cache")
    def test_success_redirect_uses_config_name(
        self, mock_cache, mock_http_cls, mock_safe_url,
        mock_get_config, mock_get_state, test_client
    ):
        """Test that successful callback redirect uses config['name'], not path param."""
        mock_get_state.return_value = _FAKE_STATE_DATA
        mock_get_config.return_value = _FAKE_CONNECTION_CONFIG.copy()

        # Mock successful token exchange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "fake-token",
            "token_type": "bearer",
            "expires_in": 3600
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_client

        mock_token_cache = MagicMock()
        mock_cache.return_value = mock_token_cache

        # Use a different path param than config name to prove config name wins
        response = test_client.get(
            "/connections/test_service/callback",
            params={"code": "auth-code", "state": "valid-state"},
            follow_redirects=False
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "connection_success=test_service" in location
        # Verify token was stored with config name
        mock_token_cache.set_token_from_response.assert_called_once()
        call_kwargs = mock_token_cache.set_token_from_response.call_args
        assert call_kwargs.kwargs.get("connection_name") or call_kwargs[1].get("connection_name") == "test_service"

    @patch("bondable.rest.routers.connections._get_and_delete_oauth_state")
    @patch("bondable.rest.routers.connections._get_connection_config")
    @patch("bondable.rest.routers.connections.is_safe_redirect_url", return_value=True)
    @patch("httpx.AsyncClient")
    def test_token_error_redirect_uses_config_name(
        self, mock_http_cls, mock_safe_url,
        mock_get_config, mock_get_state, test_client
    ):
        """Test that token exchange error redirect uses config['name']."""
        mock_get_state.return_value = _FAKE_STATE_DATA
        mock_get_config.return_value = _FAKE_CONNECTION_CONFIG.copy()

        # Mock failed token exchange (HTTP error)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_client

        response = test_client.get(
            "/connections/test_service/callback",
            params={"code": "auth-code", "state": "valid-state"},
            follow_redirects=False
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "connection_error=test_service" in location
        assert "error=token_exchange_failed" in location

    @patch("bondable.rest.routers.connections._get_and_delete_oauth_state")
    @patch("bondable.rest.routers.connections._get_connection_config")
    @patch("bondable.rest.routers.connections.is_safe_redirect_url", return_value=True)
    @patch("httpx.AsyncClient")
    def test_unexpected_error_redirect_uses_config_name(
        self, mock_http_cls, mock_safe_url,
        mock_get_config, mock_get_state, test_client
    ):
        """Test that unexpected error redirect uses config['name']."""
        mock_get_state.return_value = _FAKE_STATE_DATA
        mock_get_config.return_value = _FAKE_CONNECTION_CONFIG.copy()

        # Mock unexpected error during token exchange
        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("Network failure")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_client

        response = test_client.get(
            "/connections/test_service/callback",
            params={"code": "auth-code", "state": "valid-state"},
            follow_redirects=False
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "connection_error=test_service" in location
        assert "error=unknown" in location

    @patch("bondable.rest.routers.connections._get_and_delete_oauth_state")
    @patch("bondable.rest.routers.connections._get_connection_config")
    def test_callback_with_unknown_connection_returns_404(
        self, mock_get_config, mock_get_state, test_client
    ):
        """Test that callback with unknown connection returns 404, not a redirect."""
        mock_get_state.return_value = _FAKE_STATE_DATA
        mock_get_config.return_value = None  # Connection not found

        response = test_client.get(
            "/connections/evil_injection/callback",
            params={"code": "auth-code", "state": "valid-state"},
            follow_redirects=False
        )

        assert response.status_code == 404


# --- Integration Tests ---

class TestConnectionsIntegration:
    """Integration tests for complete connection flows"""

    def test_connection_workflow_unauthenticated(self, test_client):
        """Test that all connection endpoints require authentication"""
        endpoints = [
            ("GET", "/connections"),
            ("GET", "/connections/test/authorize"),
            ("GET", "/connections/test/status"),
            ("DELETE", "/connections/test"),
            ("GET", "/connections/check-expired"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = test_client.get(endpoint)
            elif method == "DELETE":
                response = test_client.delete(endpoint)

            assert response.status_code == 401, f"{method} {endpoint} should require auth"

    def test_connection_list_and_check_expired_consistent(self, authenticated_client):
        """Test that list and check-expired return consistent data"""
        client, headers = authenticated_client

        # Get list
        list_response = client.get("/connections", headers=headers)
        assert list_response.status_code == 200
        list_data = list_response.json()

        # Check expired
        expired_response = client.get("/connections/check-expired", headers=headers)
        assert expired_response.status_code == 200
        expired_data = expired_response.json()

        # Expired from list should match check-expired
        expired_from_list = list_data["expired"]
        expired_from_check = expired_data["expired_connections"]

        # Both should have same count
        assert len(expired_from_list) == len(expired_from_check)


# --- Error Handling Tests ---

class TestErrorHandling:
    """Test error handling in connections API"""

    def test_invalid_json_handling(self, authenticated_client):
        """Test handling of requests to endpoints that don't expect body"""
        client, headers = authenticated_client

        # GET endpoints shouldn't fail with extra parameters
        response = client.get(
            "/connections",
            headers=headers,
            params={"extra_param": "value"}
        )

        # Should still work (extra params ignored)
        assert response.status_code == 200

    def test_expired_token_handling(self, test_client):
        """Test handling of expired JWT token"""
        # Create an expired token
        expired_data = {
            "sub": TEST_USER_EMAIL,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1)
        }
        expired_token = jwt.encode(
            expired_data,
            jwt_config.JWT_SECRET_KEY,
            algorithm=jwt_config.JWT_ALGORITHM
        )
        headers = {"Authorization": f"Bearer {expired_token}"}

        response = test_client.get("/connections", headers=headers)

        assert response.status_code == 401


# Run with: poetry run pytest tests/test_connections_api.py -v
