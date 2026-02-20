"""
Integration tests for the MCP Token Cache with database persistence.
Tests the full lifecycle of connection tokens including storage, retrieval,
expiration, and database operations.
"""

import os
import pytest
import tempfile
import uuid
from datetime import datetime, timezone, timedelta

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_token_cache.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-token-cache-testing-12345')

# Import after setting environment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bondable.bond.providers.metadata import Base, UserConnectionToken, ConnectionOAuthState
from bondable.bond.auth.mcp_token_cache import (
    MCPTokenCache,
    MCPTokenData,
    get_mcp_token_cache,
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
def db_session():
    """Get a database session for testing."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def token_cache():
    """Get a fresh token cache instance with database configured."""
    # Reset the singleton for testing
    MCPTokenCache._instance = None
    cache = MCPTokenCache()
    cache.set_db_session_factory(TestSessionLocal)
    return cache


@pytest.fixture
def test_user_id():
    """Generate a unique test user ID."""
    return f"test-user-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_connection_name():
    """Test connection name."""
    return "test_connection"


# --- MCPTokenData Tests ---

class TestMCPTokenData:
    """Test the MCPTokenData class"""

    def test_create_token_data(self):
        """Test creating token data"""
        token = MCPTokenData(
            access_token="test-access-token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_token="test-refresh-token",
            scopes="read write"
        )

        assert token.access_token == "test-access-token"
        assert token.token_type == "Bearer"
        assert token.refresh_token == "test-refresh-token"
        assert token.scopes == "read write"
        assert not token.is_expired()

    def test_token_not_expired(self):
        """Test token that is not expired"""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = MCPTokenData(
            access_token="test",
            expires_at=future_time
        )

        assert not token.is_expired()

    def test_token_expired(self):
        """Test token that is expired"""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = MCPTokenData(
            access_token="test",
            expires_at=past_time
        )

        assert token.is_expired()

    def test_token_expires_within_buffer(self):
        """Test that token is considered expired within 5 minute buffer"""
        # 3 minutes from now - within the 5 minute buffer
        soon = datetime.now(timezone.utc) + timedelta(minutes=3)
        token = MCPTokenData(
            access_token="test",
            expires_at=soon
        )

        assert token.is_expired()  # Should be expired due to buffer

    def test_token_no_expiration_not_expired(self):
        """Test token without expiration is not considered expired"""
        token = MCPTokenData(
            access_token="test",
            expires_at=None
        )

        assert not token.is_expired()

    def test_to_dict_no_sensitive_data(self):
        """Test that to_dict doesn't include access_token"""
        token = MCPTokenData(
            access_token="super-secret-token",
            refresh_token="secret-refresh",
            scopes="read"
        )

        data = token.to_dict()

        assert "access_token" not in str(data)
        assert "super-secret-token" not in str(data)
        assert "has_refresh_token" in data
        assert data["scopes"] == "read"


# --- Token Cache Database Tests ---

class TestTokenCacheDatabase:
    """Test token cache with database persistence"""

    def test_set_and_get_token(self, token_cache, test_user_id, test_connection_name):
        """Test storing and retrieving a token"""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store token
        stored = token_cache.set_token(
            user_id=test_user_id,
            connection_name=test_connection_name,
            access_token="my-access-token",
            token_type="Bearer",
            expires_at=expires_at,
            refresh_token="my-refresh-token",
            scopes="read write"
        )

        assert stored.access_token == "my-access-token"
        assert stored.refresh_token == "my-refresh-token"

        # Retrieve token
        retrieved = token_cache.get_token(test_user_id, test_connection_name)

        assert retrieved is not None
        assert retrieved.access_token == "my-access-token"
        assert retrieved.refresh_token == "my-refresh-token"
        assert retrieved.token_type == "Bearer"
        assert retrieved.scopes == "read write"

    def test_token_persisted_to_database(self, token_cache, db_session, test_user_id):
        """Test that tokens are actually saved to database"""
        connection = f"persist_test_{uuid.uuid4().hex[:6]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store token through cache
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="db-persisted-token",
            expires_at=expires_at
        )

        # Query database directly
        token_record = db_session.query(UserConnectionToken).filter(
            UserConnectionToken.user_id == test_user_id,
            UserConnectionToken.connection_name == connection
        ).first()

        assert token_record is not None
        assert token_record.user_id == test_user_id
        assert token_record.connection_name == connection
        # Token should be encrypted
        assert token_record.access_token_encrypted != "db-persisted-token"
        # But decryptable
        decrypted = decrypt_token(token_record.access_token_encrypted)
        assert decrypted == "db-persisted-token"

    def test_token_loaded_from_database(self, token_cache, db_session, test_user_id):
        """Test that tokens are loaded directly from database."""
        connection = f"db_load_{uuid.uuid4().hex[:6]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="db-stored-token",
            expires_at=expires_at
        )

        # Create a fresh cache instance to verify database persistence
        # (simulates a new server restart or new request context)
        MCPTokenCache._instance = None
        fresh_cache = MCPTokenCache()
        fresh_cache.set_db_session_factory(lambda: db_session)

        # Token should be retrievable from database via fresh cache
        retrieved = fresh_cache.get_token(test_user_id, connection)

        assert retrieved is not None
        assert retrieved.access_token == "db-stored-token"

    def test_token_update_existing(self, token_cache, test_user_id):
        """Test updating an existing token"""
        connection = f"update_test_{uuid.uuid4().hex[:6]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store initial token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="original-token",
            expires_at=expires_at
        )

        # Update token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="updated-token",
            expires_at=expires_at + timedelta(hours=1)
        )

        # Retrieve and verify
        retrieved = token_cache.get_token(test_user_id, connection)

        assert retrieved is not None
        assert retrieved.access_token == "updated-token"

    def test_clear_token(self, token_cache, db_session, test_user_id):
        """Test clearing a token removes from both cache and database"""
        connection = f"clear_test_{uuid.uuid4().hex[:6]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="to-be-cleared",
            expires_at=expires_at
        )

        # Clear token
        cleared = token_cache.clear_token(test_user_id, connection)
        assert cleared

        # Should not exist in cache or database
        retrieved = token_cache.get_token(test_user_id, connection)
        assert retrieved is None

        # Also verify database directly
        db_session.expire_all()
        token_record = db_session.query(UserConnectionToken).filter(
            UserConnectionToken.user_id == test_user_id,
            UserConnectionToken.connection_name == connection
        ).first()
        assert token_record is None

    def test_expired_token_not_returned(self, token_cache, test_user_id):
        """Test that expired tokens are not returned"""
        connection = f"expired_test_{uuid.uuid4().hex[:6]}"
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Store already-expired token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="expired-token",
            expires_at=past_time
        )

        # Token should not be returned
        retrieved = token_cache.get_token(test_user_id, connection)
        assert retrieved is None

    def test_has_token(self, token_cache, test_user_id):
        """Test has_token helper method"""
        connection = f"has_token_test_{uuid.uuid4().hex[:6]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # No token initially
        assert not token_cache.has_token(test_user_id, connection)

        # Store token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token="exists",
            expires_at=expires_at
        )

        # Now has token
        assert token_cache.has_token(test_user_id, connection)


# --- User Connections Tests ---

class TestUserConnections:
    """Test user connection management"""

    def test_get_user_connections(self, token_cache, test_user_id):
        """Test getting all connections for a user"""
        # Store multiple connections
        for i in range(3):
            connection = f"multi_conn_{i}_{uuid.uuid4().hex[:6]}"
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            token_cache.set_token(
                user_id=test_user_id,
                connection_name=connection,
                access_token=f"token-{i}",
                expires_at=expires_at,
                scopes="read write"
            )

        connections = token_cache.get_user_connections(test_user_id)

        assert len(connections) >= 3  # May have tokens from other tests
        for name, info in connections.items():
            if name.startswith("multi_conn_"):
                assert info["connected"] is True
                assert info["valid"] is True
                assert info["scopes"] == "read write"

    def test_get_expired_connections(self, token_cache, test_user_id):
        """Test getting expired connections"""
        valid_conn = f"valid_{uuid.uuid4().hex[:6]}"
        expired_conn = f"expired_{uuid.uuid4().hex[:6]}"

        # Store valid token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=valid_conn,
            access_token="valid-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        # Store expired token (but don't try to get it, as that would delete it)
        # Instead, write directly to database with encrypted token
        from bondable.bond.auth.token_encryption import encrypt_token
        session = TestSessionLocal()
        expired_record = UserConnectionToken(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            connection_name=expired_conn,
            access_token_encrypted=encrypt_token("expired-token"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        session.add(expired_record)
        session.commit()
        session.close()

        # Get expired connections
        expired = token_cache.get_expired_connections(test_user_id)

        expired_names = [e["name"] for e in expired]
        assert expired_conn in expired_names
        assert valid_conn not in expired_names

    def test_clear_user_tokens(self, token_cache, test_user_id):
        """Test clearing all tokens for a user"""
        # Store multiple tokens
        for i in range(3):
            connection = f"clear_all_{i}_{uuid.uuid4().hex[:6]}"
            token_cache.set_token(
                user_id=test_user_id,
                connection_name=connection,
                access_token=f"token-{i}",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
            )

        # Clear all user tokens
        count = token_cache.clear_user_tokens(test_user_id)
        assert count >= 3

        # Verify no connections remain
        connections = token_cache.get_user_connections(test_user_id)
        cleared_connections = [c for c in connections.keys() if c.startswith("clear_all_")]
        assert len(cleared_connections) == 0


# --- OAuth State Tests ---

class TestOAuthState:
    """Test OAuth state management for authorization flows"""

    def test_oauth_state_model_structure(self):
        """Test OAuth state model has expected fields"""
        # Verify model structure without needing foreign keys
        from bondable.bond.providers.metadata import ConnectionOAuthState

        # Check the model has expected columns
        assert hasattr(ConnectionOAuthState, 'state')
        assert hasattr(ConnectionOAuthState, 'user_id')
        assert hasattr(ConnectionOAuthState, 'connection_name')
        assert hasattr(ConnectionOAuthState, 'code_verifier')
        assert hasattr(ConnectionOAuthState, 'redirect_uri')
        assert hasattr(ConnectionOAuthState, 'created_at')

    def test_oauth_state_data_class(self):
        """Test creating OAuth state data without database constraints"""
        state = str(uuid.uuid4())
        user_id = f"oauth_test_{uuid.uuid4().hex[:8]}"
        connection_name = "test_oauth_connection"
        code_verifier = "test-code-verifier-12345"

        # Create instance (not saved to DB)
        state_record = ConnectionOAuthState(
            state=state,
            user_id=user_id,
            connection_name=connection_name,
            code_verifier=code_verifier
        )

        # Verify attributes
        assert state_record.state == state
        assert state_record.user_id == user_id
        assert state_record.connection_name == connection_name
        assert state_record.code_verifier == code_verifier


# --- Exception Tests ---

class TestExceptions:
    """Test custom exceptions"""

    def test_authorization_required_error(self):
        """Test AuthorizationRequiredError"""
        error = AuthorizationRequiredError("atlassian")

        assert error.connection_name == "atlassian"
        assert "atlassian" in str(error)

        error_dict = error.to_dict()
        assert error_dict["error"] == "authorization_required"
        assert error_dict["connection_name"] == "atlassian"

    def test_token_expired_error(self):
        """Test TokenExpiredError"""
        expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
        error = TokenExpiredError("google_drive", expired_at)

        assert error.connection_name == "google_drive"
        assert error.expired_at == expired_at
        assert "google_drive" in str(error)

        error_dict = error.to_dict()
        assert error_dict["error"] == "token_expired"
        assert error_dict["connection_name"] == "google_drive"


# --- Integration Tests ---

class TestTokenCacheIntegration:
    """Full integration tests simulating real workflows"""

    def test_oauth_token_workflow(self, token_cache, test_user_id):
        """Test complete OAuth token storage workflow"""
        connection = f"oauth_workflow_{uuid.uuid4().hex[:6]}"

        # Simulate OAuth token response
        # Use randomized tokens to avoid any accidental credential patterns in version control
        import secrets
        oauth_response = {
            "access_token": f"test_token_{secrets.token_urlsafe(32)}",
            "token_type": "Bearer",
            "expires_in": 3600,  # 1 hour
            "refresh_token": f"test_refresh_{secrets.token_urlsafe(32)}",
            "scope": "read:me read:jira-work"
        }

        # Store from response
        stored = token_cache.set_token_from_response(
            user_id=test_user_id,
            connection_name=connection,
            token_response=oauth_response,
            provider="atlassian",
            provider_metadata={"cloud_id": "abc123"}
        )

        assert stored.access_token == oauth_response["access_token"]
        assert stored.refresh_token == oauth_response["refresh_token"]
        assert stored.scopes == oauth_response["scope"]

        # Verify retrieval
        retrieved = token_cache.get_token(test_user_id, connection)
        assert retrieved is not None
        assert retrieved.access_token == oauth_response["access_token"]
        assert retrieved.provider_metadata.get("cloud_id") == "abc123"

    def test_multiple_users_same_connection(self, token_cache):
        """Test that tokens are properly isolated per user"""
        connection = "shared_connection"
        user1 = f"user1_{uuid.uuid4().hex[:6]}"
        user2 = f"user2_{uuid.uuid4().hex[:6]}"
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store tokens for both users
        token_cache.set_token(
            user_id=user1,
            connection_name=connection,
            access_token="user1-token",
            expires_at=expires
        )
        token_cache.set_token(
            user_id=user2,
            connection_name=connection,
            access_token="user2-token",
            expires_at=expires
        )

        # Verify isolation
        token1 = token_cache.get_token(user1, connection)
        token2 = token_cache.get_token(user2, connection)

        assert token1.access_token == "user1-token"
        assert token2.access_token == "user2-token"

    def test_token_encryption_roundtrip_in_database(self, token_cache, db_session, test_user_id):
        """Test that tokens are encrypted in database and decrypted on retrieval"""
        connection = f"encryption_test_{uuid.uuid4().hex[:6]}"
        sensitive_token = "super-secret-access-token-with-sensitive-data"
        sensitive_refresh = "equally-secret-refresh-token"
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store token
        token_cache.set_token(
            user_id=test_user_id,
            connection_name=connection,
            access_token=sensitive_token,
            refresh_token=sensitive_refresh,
            expires_at=expires
        )

        # Query database directly
        db_session.expire_all()
        record = db_session.query(UserConnectionToken).filter(
            UserConnectionToken.user_id == test_user_id,
            UserConnectionToken.connection_name == connection
        ).first()

        # Verify encrypted in database
        assert record.access_token_encrypted != sensitive_token
        assert record.refresh_token_encrypted != sensitive_refresh

        # Verify can't accidentally read sensitive data from raw field
        assert "super-secret" not in record.access_token_encrypted
        assert "equally-secret" not in record.refresh_token_encrypted

        # Verify retrieval through cache decrypts properly
        retrieved = token_cache.get_token(test_user_id, connection)
        assert retrieved.access_token == sensitive_token
        assert retrieved.refresh_token == sensitive_refresh


# --- resolve_client_secret Tests ---

class TestResolveClientSecret:
    """Test the resolve_client_secret utility function"""

    def test_direct_client_secret(self):
        """Returns client_secret directly when present in config"""
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        config = {'client_secret': 'my-direct-secret', 'client_id': 'abc'}
        result = resolve_client_secret(config)
        assert result == 'my-direct-secret'

    def test_client_secret_from_arn(self):
        """Resolves client_secret from AWS Secrets Manager when client_secret_arn is present"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': '{"client_secret": "resolved-from-arn"}'
        }

        with patch('boto3.client', return_value=mock_client) as mock_boto:
            config = {
                'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:my-secret'
            }
            result = resolve_client_secret(config)

            assert result == 'resolved-from-arn'
            mock_boto.assert_called_once_with('secretsmanager', region_name='us-east-1')
            mock_client.get_secret_value.assert_called_once_with(
                SecretId='arn:aws:secretsmanager:us-east-1:123456789:secret:my-secret'
            )

    def test_client_secret_from_secret_name(self):
        """Resolves client_secret using a plain secret name (not ARN)"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': '{"client_secret": "resolved-from-name"}'
        }

        with patch('boto3.client', return_value=mock_client) as mock_boto:
            with patch.dict(os.environ, {'AWS_REGION': 'us-west-2'}):
                config = {'client_secret_arn': 'my-secret-name'}
                result = resolve_client_secret(config)

                assert result == 'resolved-from-name'
                mock_boto.assert_called_once_with('secretsmanager', region_name='us-west-2')

    def test_returns_none_when_neither_key_present(self):
        """Returns None when neither client_secret nor client_secret_arn is in config"""
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        result = resolve_client_secret({'client_id': 'abc', 'token_url': 'https://example.com'})
        assert result is None

    def test_returns_none_on_secrets_manager_error(self):
        """Returns None when AWS Secrets Manager call fails"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        with patch('boto3.client') as mock_boto:
            mock_boto.side_effect = Exception("AWS connection error")
            config = {
                'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:my-secret'
            }
            result = resolve_client_secret(config)
            assert result is None

    def test_direct_secret_takes_precedence_over_arn(self):
        """Direct client_secret is returned even when client_secret_arn is also present"""
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        config = {
            'client_secret': 'direct-value',
            'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:my-secret'
        }
        result = resolve_client_secret(config)
        assert result == 'direct-value'

    def test_empty_string_client_secret_falls_through_to_arn(self):
        """Empty string client_secret is treated as absent, falls through to ARN"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': '{"client_secret": "from-arn"}'
        }

        with patch('boto3.client', return_value=mock_client):
            config = {
                'client_secret': '',
                'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:test'
            }
            result = resolve_client_secret(config)
            assert result == 'from-arn'

    def test_empty_string_client_secret_without_arn_returns_none(self):
        """Empty string client_secret with no ARN returns None"""
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        result = resolve_client_secret({'client_secret': ''})
        assert result is None

    def test_secret_json_missing_client_secret_key(self):
        """Returns None when Secrets Manager JSON doesn't contain client_secret key"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.oauth_utils import resolve_client_secret

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': '{"api_key": "something-else"}'
        }

        with patch('boto3.client', return_value=mock_client):
            config = {
                'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:test'
            }
            result = resolve_client_secret(config)
            assert result is None


# --- Token Refresh Tests ---

class TestTokenRefresh:
    """Test token refresh with resolve_client_secret integration"""

    def test_refresh_token_with_client_secret_arn(self, token_cache, test_user_id):
        """_refresh_token resolves client_secret_arn via AWS Secrets Manager"""
        from unittest.mock import patch, MagicMock

        connection = f"refresh_arn_{uuid.uuid4().hex[:6]}"

        # Create an expired token with a refresh token
        expired_token = MCPTokenData(
            access_token="old-access-token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            refresh_token="my-refresh-token",
            scopes="read write",
            provider=connection
        )

        # Mock Config to return oauth_config with client_secret_arn
        mock_mcp_config = {
            'mcpServers': {
                connection: {
                    'oauth_config': {
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'test-client-id',
                        'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:test'
                    }
                }
            }
        }

        # Mock the refresh HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new-access-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'refresh_token': 'new-refresh-token',
            'scope': 'read write'
        }

        # Mock Secrets Manager
        mock_sm_client = MagicMock()
        mock_sm_client.get_secret_value.return_value = {
            'SecretString': '{"client_secret": "resolved-secret"}'
        }

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response) as mock_post, \
             patch('boto3.client', return_value=mock_sm_client):

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache._refresh_token(test_user_id, connection, expired_token)

            assert result is not None
            assert result.access_token == 'new-access-token'
            assert result.refresh_token == 'new-refresh-token'

            # Verify the refresh request included the resolved secret
            call_data = mock_post.call_args[1]['data']
            assert call_data['client_secret'] == 'resolved-secret'

    def test_refresh_token_with_direct_client_secret(self, token_cache, test_user_id):
        """_refresh_token works with direct client_secret (regression test)"""
        from unittest.mock import patch, MagicMock

        connection = f"refresh_direct_{uuid.uuid4().hex[:6]}"

        expired_token = MCPTokenData(
            access_token="old-token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            refresh_token="my-refresh-token",
            provider=connection
        )

        mock_mcp_config = {
            'mcpServers': {
                connection: {
                    'oauth_config': {
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'test-client-id',
                        'client_secret': 'direct-secret-value'
                    }
                }
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'refreshed-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
        }

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response) as mock_post:

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache._refresh_token(test_user_id, connection, expired_token)

            assert result is not None
            assert result.access_token == 'refreshed-token'

            call_data = mock_post.call_args[1]['data']
            assert call_data['client_secret'] == 'direct-secret-value'

    def test_refresh_fails_when_arn_resolution_fails(self, token_cache, test_user_id):
        """_refresh_token returns None when client_secret_arn can't be resolved"""
        from unittest.mock import patch, MagicMock

        connection = f"refresh_fail_{uuid.uuid4().hex[:6]}"

        expired_token = MCPTokenData(
            access_token="old-token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            refresh_token="my-refresh-token",
            provider=connection
        )

        mock_mcp_config = {
            'mcpServers': {
                connection: {
                    'oauth_config': {
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'test-client-id',
                        'client_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789:secret:test'
                    }
                }
            }
        }

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('boto3.client') as mock_boto:

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config
            mock_boto.side_effect = Exception("AWS unavailable")

            result = token_cache._refresh_token(test_user_id, connection, expired_token)

            # Should fail gracefully — no requests.post call made
            assert result is None

    def test_get_token_auto_refreshes_on_expiry(self, token_cache, test_user_id):
        """get_token() with an expired token auto-refreshes and returns the new token"""
        from unittest.mock import patch, MagicMock
        from bondable.bond.auth.token_encryption import encrypt_token

        connection = f"auto_refresh_{uuid.uuid4().hex[:6]}"

        # Write an expired token directly to DB so get_token finds it
        session = TestSessionLocal()
        expired_record = UserConnectionToken(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            connection_name=connection,
            access_token_encrypted=encrypt_token("expired-access"),
            refresh_token_encrypted=encrypt_token("valid-refresh-token"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scopes="read"
        )
        session.add(expired_record)
        session.commit()
        session.close()

        mock_mcp_config = {
            'mcpServers': {
                connection: {
                    'oauth_config': {
                        'token_url': 'https://auth.example.com/token',
                        'client_id': 'test-client-id',
                        'client_secret': 'test-secret'
                    }
                }
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'fresh-access-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'refresh_token': 'new-refresh-token',
        }

        with patch('bondable.bond.config.Config') as mock_config_cls, \
             patch('requests.post', return_value=mock_response):

            mock_config_cls.config.return_value.get_mcp_config.return_value = mock_mcp_config

            result = token_cache.get_token(test_user_id, connection, auto_refresh=True)

            assert result is not None
            assert result.access_token == 'fresh-access-token'
            assert result.refresh_token == 'new-refresh-token'


# Run with: poetry run pytest tests/test_mcp_token_cache.py -v
