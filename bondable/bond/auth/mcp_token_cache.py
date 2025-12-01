"""
Token cache for external MCP/Connection OAuth tokens.

This module provides persistent storage for OAuth tokens used to authenticate
with external services (like Atlassian). Tokens are:
- Encrypted at rest using the JWT secret key
- Stored in the database for persistence across restarts
- Cached in memory for performance

The cache acts as a read-through layer:
- On get: Check memory first, then load from database if not found
- On set: Write to both memory and database
- On clear: Remove from both memory and database
"""

import logging
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from bondable.bond.auth.token_encryption import (
    encrypt_token,
    decrypt_token,
    encrypt_token_safe,
    decrypt_token_safe,
    TokenEncryptionError
)
from bondable.bond.auth.oauth_utils import safe_isoformat

LOGGER = logging.getLogger(__name__)


def _is_valid_connection(connection_name: str) -> bool:
    """
    Check if a connection name exists in the MCP config.

    Used to filter orphaned tokens when listing connections. Tokens for
    connections that have been removed from BOND_MCP_CONFIG will be filtered.

    If no MCP config is available, returns True to allow the operation.

    Args:
        connection_name: The connection name to validate

    Returns:
        True if the connection exists in MCP config or no config is available,
        False only if config exists and connection is not in it
    """
    import os

    # Skip validation if running in pytest (detected by pytest env var)
    if 'PYTEST_CURRENT_TEST' in os.environ:
        return True

    try:
        from bondable.bond.config import Config
        mcp_config = Config.config().get_mcp_config()
        servers = mcp_config.get('mcpServers', {})
        # If no servers configured, skip validation
        if not servers:
            return True
        return connection_name in servers
    except Exception as e:
        # If we can't load config, allow the operation
        LOGGER.debug(f"Could not validate connection, allowing: {e}")
        return True


class MCPTokenData:
    """Data class for storing MCP OAuth token information."""

    def __init__(
        self,
        access_token: str,
        token_type: str = "Bearer",
        expires_at: Optional[datetime] = None,
        refresh_token: Optional[str] = None,
        scopes: Optional[str] = None,
        provider: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None
    ):
        self.access_token = access_token
        self.token_type = token_type
        self.expires_at = expires_at
        self.refresh_token = refresh_token
        self.scopes = scopes
        self.provider = provider
        self.raw_response = raw_response or {}
        self.provider_metadata = provider_metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)

    def _ensure_datetime(self, value) -> Optional[datetime]:
        """Convert string to datetime if needed."""
        if value is None:
            return None
        if isinstance(value, str):
            from dateutil import parser
            return parser.isoparse(value)
        return value

    def is_expired(self) -> bool:
        """Check if the token is expired."""
        expires = self._ensure_datetime(self.expires_at)
        if expires is None:
            return False
        # Consider expired 5 minutes before actual expiration for safety
        buffer = timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        # Handle timezone-naive expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= (expires - buffer)

    def get_expires_at_iso(self) -> Optional[str]:
        """Get expires_at as ISO string, handling both string and datetime."""
        expires = self._ensure_datetime(self.expires_at)
        return expires.isoformat() if expires else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging (no sensitive data)."""
        created = self._ensure_datetime(self.created_at)
        return {
            "token_type": self.token_type,
            "expires_at": self.get_expires_at_iso(),
            "scopes": self.scopes,
            "provider": self.provider,
            "is_expired": self.is_expired(),
            "created_at": safe_isoformat(created),
            "has_refresh_token": self.refresh_token is not None
        }


class MCPTokenCache:
    """
    Simple token storage with database persistence.

    Tokens are stored directly in the database with no in-memory caching.
    All tokens are encrypted at rest using the JWT secret key.

    Simplified from the previous write-through cache design to reduce
    complexity and eliminate initialization issues.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure one cache instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the token cache."""
        if self._initialized:
            return
        self._initialized = True
        self._db_session_factory = None
        LOGGER.debug("MCPTokenCache initialized")

    def set_db_session_factory(self, factory):
        """Set a custom database session factory (primarily for testing).

        Args:
            factory: Callable that returns a database session
        """
        self._db_session_factory = factory

    def _get_db_session(self):
        """Get a database session from the configured provider or custom factory."""
        # Use custom factory if set (primarily for testing)
        if self._db_session_factory:
            return self._db_session_factory()

        try:
            from bondable.bond.config import Config
            provider = Config.config().get_provider()
            if provider and hasattr(provider, 'metadata'):
                return provider.metadata.get_db_session()
        except Exception as e:
            LOGGER.error(f"Error getting database session: {e}")
        return None

    def _load_from_database(self, user_id: str, connection_name: str) -> Optional[MCPTokenData]:
        """
        Load a token from the database.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config

        Returns:
            MCPTokenData if found, None otherwise
        """
        session = self._get_db_session()
        if session is None:
            return None

        try:
            from bondable.bond.providers.metadata import UserConnectionToken

            token_record = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == user_id,
                UserConnectionToken.connection_name == connection_name
            ).first()

            if token_record is None:
                return None

            # Decrypt tokens
            try:
                access_token = decrypt_token(token_record.access_token_encrypted)
                refresh_token = decrypt_token_safe(token_record.refresh_token_encrypted)
            except TokenEncryptionError as e:
                LOGGER.error(f"Failed to decrypt token for user={user_id}, connection={connection_name}: {e}")
                return None

            # Handle datetime fields that might be strings (SQLite returns strings)
            expires_at = token_record.expires_at
            if isinstance(expires_at, str):
                from dateutil import parser
                expires_at = parser.isoparse(expires_at)

            created_at = token_record.created_at
            if isinstance(created_at, str):
                from dateutil import parser
                created_at = parser.isoparse(created_at)

            token_data = MCPTokenData(
                access_token=access_token,
                token_type=token_record.token_type,
                expires_at=expires_at,
                refresh_token=refresh_token,
                scopes=token_record.scopes,
                provider=connection_name,
                provider_metadata=token_record.provider_metadata or {},
                created_at=created_at
            )

            LOGGER.debug(f"Loaded token from database for user={user_id}, connection={connection_name}")
            return token_data

        except Exception as e:
            LOGGER.error(f"Error loading token from database: {e}")
            return None
        finally:
            session.close()

    def _save_to_database(
        self,
        user_id: str,
        connection_name: str,
        token_data: MCPTokenData
    ) -> bool:
        """
        Save a token to the database.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config
            token_data: The token data to save

        Returns:
            True if saved successfully, False otherwise
        """
        session = self._get_db_session()
        if session is None:
            LOGGER.warning("No database session available, token not persisted")
            return False

        try:
            from bondable.bond.providers.metadata import UserConnectionToken

            # Encrypt tokens
            access_token_encrypted = encrypt_token(token_data.access_token)
            refresh_token_encrypted = encrypt_token_safe(token_data.refresh_token)

            # Check if token already exists
            existing = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == user_id,
                UserConnectionToken.connection_name == connection_name
            ).first()

            if existing:
                # Update existing token
                existing.access_token_encrypted = access_token_encrypted
                existing.refresh_token_encrypted = refresh_token_encrypted
                existing.token_type = token_data.token_type
                existing.expires_at = token_data.expires_at
                existing.scopes = token_data.scopes
                existing.provider_metadata = token_data.provider_metadata
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new token record
                new_token = UserConnectionToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    connection_name=connection_name,
                    access_token_encrypted=access_token_encrypted,
                    refresh_token_encrypted=refresh_token_encrypted,
                    token_type=token_data.token_type,
                    expires_at=token_data.expires_at,
                    scopes=token_data.scopes,
                    provider_metadata=token_data.provider_metadata
                )
                session.add(new_token)

            session.commit()
            LOGGER.debug(f"Token saved to database for connection={connection_name}")
            return True

        except Exception as e:
            LOGGER.error(f"Error saving token to database: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _delete_from_database(self, user_id: str, connection_name: str) -> bool:
        """
        Delete a token from the database.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config

        Returns:
            True if deleted, False otherwise
        """
        session = self._get_db_session()
        if session is None:
            return False

        try:
            from bondable.bond.providers.metadata import UserConnectionToken

            deleted = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == user_id,
                UserConnectionToken.connection_name == connection_name
            ).delete()

            session.commit()
            if deleted:
                LOGGER.debug(f"Token deleted from database for user={user_id}, connection={connection_name}")
            return deleted > 0

        except Exception as e:
            LOGGER.error(f"Error deleting token from database: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _refresh_token(
        self,
        user_id: str,
        connection_name: str,
        token_data: MCPTokenData
    ) -> Optional[MCPTokenData]:
        """
        Refresh an expired token using the refresh token.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config
            token_data: Current (expired) token data with refresh_token

        Returns:
            New MCPTokenData if refresh successful, None otherwise
        """
        if not token_data.refresh_token:
            LOGGER.warning(f"[REFRESH_TOKEN] No refresh token available for user={user_id}, connection={connection_name}")
            return None

        # Get OAuth config for this connection
        try:
            from bondable.bond.config import Config
            mcp_config = Config.config().get_mcp_config()
            if not mcp_config:
                LOGGER.error("[REFRESH_TOKEN] No MCP config available")
                return None

            servers = mcp_config.get('mcpServers', {})
            server_config = servers.get(connection_name)
            if not server_config:
                LOGGER.error(f"[REFRESH_TOKEN] No server config found for connection={connection_name}")
                return None

            oauth_config = server_config.get('oauth_config', {})
            if not oauth_config:
                LOGGER.error(f"[REFRESH_TOKEN] No OAuth config found for connection={connection_name}")
                return None

            token_url = oauth_config.get('token_url')
            client_id = oauth_config.get('client_id')
            client_secret = oauth_config.get('client_secret')

            if not all([token_url, client_id, client_secret]):
                LOGGER.error(
                    f"[REFRESH_TOKEN] Missing OAuth credentials for connection={connection_name}: "
                    f"token_url={bool(token_url)}, client_id={bool(client_id)}, client_secret={bool(client_secret)}"
                )
                return None

            # Make refresh request
            import requests
            refresh_data = {
                'grant_type': 'refresh_token',
                'refresh_token': token_data.refresh_token,
                'client_id': client_id,
                'client_secret': client_secret
            }

            LOGGER.info(f"[REFRESH_TOKEN] Requesting new token")
            response = requests.post(token_url, data=refresh_data, timeout=10)

            if response.status_code != 200:
                LOGGER.error(
                    f"[REFRESH_TOKEN] Token refresh failed with status {response.status_code}"
                )
                return None

            token_response = response.json()

            # Extract new token info
            access_token = token_response.get('access_token')
            if not access_token:
                LOGGER.error(f"[REFRESH_TOKEN] No access_token in refresh response")
                return None

            # Calculate expiration
            expires_in = token_response.get('expires_in', 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Create new token data
            new_token_data = MCPTokenData(
                access_token=access_token,
                token_type=token_response.get('token_type', 'Bearer'),
                expires_at=expires_at,
                refresh_token=token_response.get('refresh_token', token_data.refresh_token),  # Use new or keep old
                scopes=token_response.get('scope', token_data.scopes),
                provider=token_data.provider,
                provider_metadata=token_data.provider_metadata,
                raw_response=token_response
            )

            # Save to database
            if self._save_to_database(user_id, connection_name, new_token_data):
                LOGGER.info(
                    f"[REFRESH_TOKEN] Successfully refreshed token for user={user_id}, connection={connection_name}, "
                    f"new_expires_at={expires_at}"
                )
                return new_token_data
            else:
                LOGGER.error(f"[REFRESH_TOKEN] Failed to save refreshed token to database")
                return None

        except Exception as e:
            LOGGER.error(f"[REFRESH_TOKEN] Error refreshing token: {e}", exc_info=True)
            return None

    def get_token(self, user_id: str, connection_name: str, auto_refresh: bool = True) -> Optional[MCPTokenData]:
        """
        Get a token from the database, automatically refreshing if expired.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config
            auto_refresh: If True, automatically refresh expired tokens that have refresh_token

        Returns:
            MCPTokenData if found and valid, None otherwise
        """
        # Load directly from database
        token_data = self._load_from_database(user_id, connection_name)

        if token_data is not None:
            if token_data.is_expired():
                # Try to refresh if we have a refresh token and auto_refresh is enabled
                if auto_refresh and token_data.refresh_token:
                    LOGGER.info(
                        f"[GET_TOKEN] Token expired for user={user_id}, connection={connection_name}, "
                        f"attempting automatic refresh"
                    )
                    refreshed_token = self._refresh_token(user_id, connection_name, token_data)
                    if refreshed_token:
                        LOGGER.info(f"[GET_TOKEN] Token successfully refreshed for user={user_id}, connection={connection_name}")
                        return refreshed_token
                    else:
                        LOGGER.warning(f"[GET_TOKEN] Token refresh failed for user={user_id}, connection={connection_name}")
                else:
                    LOGGER.debug(
                        f"[GET_TOKEN] Token EXPIRED for user={user_id}, connection={connection_name}, "
                        f"expires_at={token_data.expires_at}, has_refresh_token={token_data.refresh_token is not None}, "
                        f"auto_refresh={auto_refresh}"
                    )

                # Delete expired token if refresh failed or not attempted
                self._delete_from_database(user_id, connection_name)
                return None

            LOGGER.debug(
                f"[GET_TOKEN] Retrieved token for user={user_id}, connection={connection_name}, "
                f"expires_at={token_data.expires_at}"
            )
            return token_data

        LOGGER.debug(f"[GET_TOKEN] No token found for user={user_id}, connection={connection_name}")
        return None

    def set_token(
        self,
        user_id: str,
        connection_name: str,
        access_token: str,
        token_type: str = "Bearer",
        expires_in: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        refresh_token: Optional[str] = None,
        scopes: Optional[str] = None,
        provider: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        provider_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MCPTokenData]:
        """
        Store a token in the database.

        Validates that the connection exists in MCP config before storing.
        This prevents storing tokens for connections that don't exist.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config
            access_token: The OAuth access token
            token_type: Token type (usually "Bearer")
            expires_in: Token lifetime in seconds (alternative to expires_at)
            expires_at: Token expiration datetime (alternative to expires_in)
            refresh_token: Optional refresh token
            scopes: Granted scopes
            provider: OAuth provider name
            raw_response: Raw token response for debugging
            provider_metadata: Provider-specific metadata (cloud_id, etc.)

        Returns:
            The stored MCPTokenData, or None if connection is invalid
        """
        # Validate connection exists in MCP config before storing
        if not _is_valid_connection(connection_name):
            LOGGER.warning(
                f"[SET_TOKEN] Connection '{connection_name}' not found in MCP config, "
                f"refusing to store token for user={user_id}"
            )
            return None

        # Calculate expiration time
        if expires_at is None and expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        token_data = MCPTokenData(
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
            refresh_token=refresh_token,
            scopes=scopes,
            provider=provider or connection_name,
            raw_response=raw_response,
            provider_metadata=provider_metadata or {}
        )

        # Save directly to database
        self._save_to_database(user_id, connection_name, token_data)

        LOGGER.debug(f"Token stored for connection={connection_name}, expires_at={expires_at}")
        return token_data

    def set_token_from_response(
        self,
        user_id: str,
        connection_name: str,
        token_response: Dict[str, Any],
        provider: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None
    ) -> MCPTokenData:
        """
        Store a token from a standard OAuth token response.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config
            token_response: OAuth token response dict with access_token, etc.
            provider: OAuth provider name
            provider_metadata: Provider-specific metadata

        Returns:
            The stored MCPTokenData
        """
        return self.set_token(
            user_id=user_id,
            connection_name=connection_name,
            access_token=token_response.get("access_token"),
            token_type=token_response.get("token_type", "Bearer"),
            expires_in=token_response.get("expires_in"),
            refresh_token=token_response.get("refresh_token"),
            scopes=token_response.get("scope"),
            provider=provider,
            raw_response=token_response,
            provider_metadata=provider_metadata
        )

    def clear_token(self, user_id: str, connection_name: str) -> bool:
        """
        Remove a token from the database.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config

        Returns:
            True if token was removed, False if not found
        """
        # Delete directly from database
        return self._delete_from_database(user_id, connection_name)

    def clear_user_tokens(self, user_id: str) -> int:
        """
        Remove all tokens for a user from the database.

        Args:
            user_id: Bond user ID

        Returns:
            Number of tokens removed
        """
        session = self._get_db_session()
        if session is None:
            return 0

        try:
            from bondable.bond.providers.metadata import UserConnectionToken
            count = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == user_id
            ).delete()
            session.commit()
            if count:
                LOGGER.info(f"Cleared {count} tokens for user={user_id}")
            return count
        except Exception as e:
            LOGGER.error(f"Error clearing user tokens from database: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    def has_token(self, user_id: str, connection_name: str) -> bool:
        """
        Check if a valid (non-expired) token exists.

        Args:
            user_id: Bond user ID
            connection_name: Connection name from config

        Returns:
            True if valid token exists
        """
        return self.get_token(user_id, connection_name) is not None

    def get_user_connections(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all connection statuses for a user.

        Args:
            user_id: Bond user ID

        Returns:
            Dict mapping connection_name to status info (without sensitive data)
        """
        connections = {}

        # Check database for all user tokens
        session = self._get_db_session()
        if session:
            try:
                from bondable.bond.providers.metadata import UserConnectionToken

                tokens = session.query(UserConnectionToken).filter(
                    UserConnectionToken.user_id == user_id
                ).all()

                for token_record in tokens:
                    # Skip tokens for connections no longer in MCP config (orphaned)
                    if not _is_valid_connection(token_record.connection_name):
                        LOGGER.debug(
                            f"Skipping orphaned token for connection={token_record.connection_name}"
                        )
                        continue

                    # Handle datetime fields that might be strings (SQLite)
                    expires_at = token_record.expires_at
                    if isinstance(expires_at, str):
                        from dateutil import parser
                        expires_at = parser.isoparse(expires_at)

                    created_at = token_record.created_at
                    if isinstance(created_at, str):
                        from dateutil import parser
                        created_at = parser.isoparse(created_at)

                    # Check if expired
                    is_expired = False
                    if expires_at:
                        expires = expires_at
                        if expires.tzinfo is None:
                            expires = expires.replace(tzinfo=timezone.utc)
                        is_expired = datetime.now(timezone.utc) >= expires - timedelta(minutes=5)

                    connections[token_record.connection_name] = {
                        "connected": True,
                        "valid": not is_expired,
                        "scopes": token_record.scopes,
                        "expires_at": safe_isoformat(expires_at),
                        "created_at": safe_isoformat(created_at),
                        "provider_metadata": token_record.provider_metadata or {}
                    }
            except Exception as e:
                LOGGER.error(f"Error getting user connections from database: {e}")
            finally:
                session.close()

        return connections

    def get_expired_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of expired connections for a user.

        Args:
            user_id: Bond user ID

        Returns:
            List of expired connection info dicts
        """
        expired = []
        connections = self.get_user_connections(user_id)

        for connection_name, info in connections.items():
            if info.get("connected") and not info.get("valid"):
                expired.append({
                    "name": connection_name,
                    "expires_at": info.get("expires_at")
                })

        return expired

# Singleton instance
_token_cache: Optional[MCPTokenCache] = None


def get_mcp_token_cache() -> MCPTokenCache:
    """Get the singleton MCPTokenCache instance."""
    global _token_cache
    if _token_cache is None:
        _token_cache = MCPTokenCache()
    return _token_cache


class AuthorizationRequiredError(Exception):
    """
    Exception raised when a user needs to authorize a connection.

    This exception should be caught by the API layer and returned
    to the client as an indication that OAuth authorization is needed.
    """

    def __init__(self, connection_name: str, message: str = None):
        self.connection_name = connection_name
        self.message = message or f"Authorization required for connection '{connection_name}'"
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "error": "authorization_required",
            "connection_name": self.connection_name,
            "message": self.message
        }


class TokenExpiredError(Exception):
    """
    Exception raised when a connection token has expired.

    This should prompt the user to re-authenticate via settings.
    """

    def __init__(self, connection_name: str, expired_at: Optional[datetime] = None):
        self.connection_name = connection_name
        self.expired_at = expired_at
        self.message = f"Token expired for connection '{connection_name}'"
        if expired_at:
            self.message += f" (expired at {safe_isoformat(expired_at)})"
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "error": "token_expired",
            "connection_name": self.connection_name,
            "expired_at": safe_isoformat(self.expired_at),
            "message": self.message
        }
