"""
Integration tests for OAuth token auto-refresh across the full stack.

Tests the interaction between mcp_token_cache, BedrockMCP auth headers,
and the MCP router status check — using a real SQLite DB but mocked HTTP
calls to the OAuth provider.

Run with: poetry run pytest tests/test_oauth_token_refresh.py -v
"""

import os
import pytest
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_oauth_refresh.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-oauth-refresh-testing-12345')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bondable.bond.providers.metadata import Base, UserConnectionToken
from bondable.bond.auth.mcp_token_cache import (
    MCPTokenCache,
    MCPTokenData,
    AuthorizationRequiredError,
    TokenExpiredError
)
from bondable.bond.auth.token_encryption import encrypt_token, decrypt_token

# --- Test Database Engine ---
_test_engine = create_engine(TEST_METADATA_DB_URL)
Base.metadata.create_all(_test_engine)
TestSessionLocal = sessionmaker(bind=_test_engine)


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
def token_cache():
    """Get a fresh token cache instance with database configured."""
    MCPTokenCache._instance = None
    cache = MCPTokenCache()
    cache.set_db_session_factory(TestSessionLocal)
    return cache


@pytest.fixture
def test_user_id():
    return f"test-user-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_user(test_user_id):
    """Create a mock user object."""
    user = MagicMock()
    user.user_id = test_user_id
    user.email = "test@example.com"
    return user


@pytest.fixture
def server_name():
    return f"test_oauth_server_{uuid.uuid4().hex[:6]}"


@pytest.fixture
def server_config():
    return {
        'auth_type': 'oauth2',
        'url': 'https://mcp.example.com/sse',
        'transport': 'sse',
        'cloud_id': 'test-cloud-123',
        'oauth_config': {
            'token_url': 'https://auth.example.com/oauth/token',
            'client_id': 'test-client-id',
            'client_secret': 'test-client-secret',
            'authorize_url': 'https://auth.example.com/authorize',
            'scopes': ['read', 'write'],
        }
    }


@pytest.fixture
def mock_mcp_config(server_name, server_config):
    return {'mcpServers': {server_name: server_config}}


def _store_token_in_db(user_id, connection_name, access_token, refresh_token=None,
                       expired=False, expires_in=3600):
    """Helper to store a token directly in the test database."""
    if expired:
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    session = TestSessionLocal()
    record = UserConnectionToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        connection_name=connection_name,
        access_token_encrypted=encrypt_token(access_token),
        refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
        token_type="Bearer",
        expires_at=expires_at,
        scopes="read write"
    )
    session.add(record)
    session.commit()
    session.close()
    return record


def _get_token_from_db(user_id, connection_name):
    """Helper to read a token directly from the test database."""
    session = TestSessionLocal()
    record = session.query(UserConnectionToken).filter(
        UserConnectionToken.user_id == user_id,
        UserConnectionToken.connection_name == connection_name
    ).first()
    session.close()
    return record


def _mock_refresh_response(access_token='refreshed-access-token',
                           refresh_token='new-refresh-token',
                           expires_in=3600, status_code=200):
    """Create a mock HTTP response for token refresh."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    if status_code == 200:
        mock_response.json.return_value = {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': expires_in,
            'refresh_token': refresh_token,
            'scope': 'read write'
        }
    else:
        mock_response.json.return_value = {'error': 'invalid_grant'}
    return mock_response


# =============================================================================
# Test: Auth Headers Refresh
# =============================================================================

class TestAuthHeadersRefresh:
    """Verify _get_auth_headers_for_server triggers refresh for expired tokens."""

    def test_valid_token_returns_headers_without_refresh(
        self, token_cache, test_user_id, mock_user, server_name, server_config
    ):
        """A valid (non-expired) token should return headers without any refresh attempt."""
        _store_token_in_db(test_user_id, server_name, 'valid-access-token',
                           refresh_token='my-refresh', expired=False)

        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache', return_value=token_cache):
            headers = _get_auth_headers_for_server(server_name, server_config, mock_user)

        assert 'Authorization' in headers
        assert headers['Authorization'] == 'Bearer valid-access-token'

    def test_expired_token_triggers_refresh_and_returns_new_headers(
        self, token_cache, test_user_id, mock_user, server_name, server_config, mock_mcp_config
    ):
        """An expired token with refresh_token should be auto-refreshed."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token='valid-refresh', expired=True)

        mock_response = _mock_refresh_response(access_token='fresh-access-token')

        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache', return_value=token_cache), \
             patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response) as mock_post:

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            headers = _get_auth_headers_for_server(server_name, server_config, mock_user)

        assert headers['Authorization'] == 'Bearer fresh-access-token'
        mock_post.assert_called_once()

    def test_expired_token_no_refresh_token_raises_token_expired(
        self, token_cache, test_user_id, mock_user, server_name, server_config
    ):
        """An expired token without refresh_token should raise TokenExpiredError."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token=None, expired=True)

        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache', return_value=token_cache):
            with pytest.raises(TokenExpiredError) as exc_info:
                _get_auth_headers_for_server(server_name, server_config, mock_user)

        assert exc_info.value.connection_name == server_name

    def test_expired_token_refresh_fails_raises_token_expired(
        self, token_cache, test_user_id, mock_user, server_name, server_config, mock_mcp_config
    ):
        """An expired token where refresh fails should raise TokenExpiredError."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token='bad-refresh', expired=True)

        mock_response = _mock_refresh_response(status_code=400)

        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache', return_value=token_cache), \
             patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response):

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            with pytest.raises(TokenExpiredError):
                _get_auth_headers_for_server(server_name, server_config, mock_user)

    def test_no_connection_raises_authorization_required(
        self, token_cache, test_user_id, mock_user, server_name, server_config
    ):
        """A user with no connection at all should get AuthorizationRequiredError."""
        from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server

        with patch('bondable.bond.providers.bedrock.BedrockMCP.get_mcp_token_cache', return_value=token_cache):
            with pytest.raises(AuthorizationRequiredError) as exc_info:
                _get_auth_headers_for_server(server_name, server_config, mock_user)

        assert exc_info.value.connection_name == server_name


# =============================================================================
# Test: Status Check Safety
# =============================================================================

class TestStatusCheckSafety:
    """Verify that status checks (read-only) do not destroy tokens."""

    def test_status_check_preserves_expired_token(
        self, token_cache, test_user_id, server_name, server_config
    ):
        """Status check should not delete expired tokens from the database."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token='precious-refresh', expired=True)

        from bondable.rest.routers.mcp import _get_connection_status_for_server

        status = _get_connection_status_for_server(
            server_name, server_config, test_user_id, token_cache
        )

        # Status should show connected but not valid
        assert status.connected is True
        assert status.valid is False
        assert status.requires_authorization is True

        # Token should still exist in database
        record = _get_token_from_db(test_user_id, server_name)
        assert record is not None, "Status check should NOT delete the token"
        assert decrypt_token(record.refresh_token_encrypted) == "precious-refresh"

    def test_refresh_works_after_status_check(
        self, token_cache, test_user_id, server_name, server_config, mock_mcp_config
    ):
        """After a status check, auto-refresh should still work because token is preserved."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token='valid-refresh', expired=True)

        from bondable.rest.routers.mcp import _get_connection_status_for_server

        # Step 1: Status check (read-only)
        status = _get_connection_status_for_server(
            server_name, server_config, test_user_id, token_cache
        )
        assert status.valid is False

        # Step 2: Now do a refresh via get_token
        mock_response = _mock_refresh_response(access_token='fresh-after-status')

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response):

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache.get_token(test_user_id, server_name, auto_refresh=True)

        assert result is not None
        assert result.access_token == 'fresh-after-status'

    def test_valid_token_status_shows_connected(
        self, token_cache, test_user_id, server_name, server_config
    ):
        """A valid token should show as connected and valid."""
        _store_token_in_db(test_user_id, server_name, 'valid-access',
                           refresh_token='my-refresh', expired=False)

        from bondable.rest.routers.mcp import _get_connection_status_for_server

        status = _get_connection_status_for_server(
            server_name, server_config, test_user_id, token_cache
        )

        assert status.connected is True
        assert status.valid is True
        assert status.requires_authorization is False

    def test_no_token_status_shows_not_connected(
        self, token_cache, test_user_id, server_name, server_config
    ):
        """No token at all should show as not connected."""
        from bondable.rest.routers.mcp import _get_connection_status_for_server

        status = _get_connection_status_for_server(
            server_name, server_config, test_user_id, token_cache
        )

        assert status.connected is False
        assert status.valid is False
        assert status.requires_authorization is True


# =============================================================================
# Test: End-to-End Refresh Flow
# =============================================================================

class TestEndToEndRefreshFlow:
    """Full lifecycle: store → expire → refresh → verify new token."""

    def test_full_lifecycle_with_rotating_refresh_token(
        self, token_cache, test_user_id, server_name, mock_mcp_config
    ):
        """Complete lifecycle: store, let expire, refresh, verify new tokens in DB."""
        # Step 1: Store initial token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=server_name,
            access_token="initial-access",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
            refresh_token="initial-refresh",
            scopes="read write"
        )

        # Step 2: Verify it's stored
        record = _get_token_from_db(test_user_id, server_name)
        assert record is not None

        # Step 3: Refresh (simulates what _get_auth_headers_for_server does)
        mock_response = _mock_refresh_response(
            access_token='rotated-access',
            refresh_token='rotated-refresh'
        )

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response) as mock_post:

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache.get_token(test_user_id, server_name, auto_refresh=True)

        assert result is not None
        assert result.access_token == 'rotated-access'
        assert result.refresh_token == 'rotated-refresh'

        # Step 4: Verify new tokens are persisted in DB
        record = _get_token_from_db(test_user_id, server_name)
        assert record is not None
        assert decrypt_token(record.access_token_encrypted) == 'rotated-access'
        assert decrypt_token(record.refresh_token_encrypted) == 'rotated-refresh'

        # Step 5: Verify the refresh request used the initial refresh token
        call_data = mock_post.call_args[1]['data']
        assert call_data['refresh_token'] == 'initial-refresh'
        assert call_data['grant_type'] == 'refresh_token'

    def test_multiple_status_checks_dont_corrupt_token(
        self, token_cache, test_user_id, server_name, server_config, mock_mcp_config
    ):
        """Multiple status checks in a row should not destroy the token."""
        _store_token_in_db(test_user_id, server_name, 'expired-access',
                           refresh_token='stable-refresh', expired=True)

        from bondable.rest.routers.mcp import _get_connection_status_for_server

        # Simulate multiple UI polls
        for _ in range(5):
            status = _get_connection_status_for_server(
                server_name, server_config, test_user_id, token_cache
            )
            assert status.connected is True
            assert status.valid is False

        # Token should still be intact after all those checks
        record = _get_token_from_db(test_user_id, server_name)
        assert record is not None
        assert decrypt_token(record.refresh_token_encrypted) == "stable-refresh"

        # And refresh should still work
        mock_response = _mock_refresh_response(access_token='finally-refreshed')

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response):

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache.get_token(test_user_id, server_name, auto_refresh=True)

        assert result is not None
        assert result.access_token == 'finally-refreshed'

    def test_non_oauth_server_unaffected(self, token_cache, test_user_id):
        """Non-OAuth (bond_jwt) servers should not be affected by any of these changes."""
        from bondable.rest.routers.mcp import _get_connection_status_for_server

        bond_jwt_config = {
            'auth_type': 'bond_jwt',
            'url': 'https://mcp.internal.com/sse',
        }

        status = _get_connection_status_for_server(
            "internal_server", bond_jwt_config, test_user_id, token_cache
        )

        assert status.connected is True
        assert status.valid is True
        assert status.requires_authorization is False
