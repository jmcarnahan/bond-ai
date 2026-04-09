"""
Connections Router - API endpoints for managing external service connections.

This router handles OAuth authentication with external services like Atlassian,
storing tokens encrypted in the database for use with MCP tools.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Annotated, List, Dict, Any, Optional
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from bondable.bond.config import Config
from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
from bondable.bond.auth.oauth_utils import generate_pkce_pair, generate_oauth_state, resolve_client_secret
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.utils.url_validation import is_safe_redirect_url
from bondable.utils.logging_utils import safe_id

router = APIRouter(prefix="/connections", tags=["Connections"])
LOGGER = logging.getLogger(__name__)


# =============================================================================
# Response Models
# =============================================================================

class ConnectionConfigResponse(BaseModel):
    """Response model for a connection configuration."""
    name: str
    display_name: str
    description: Optional[str] = None
    auth_type: str
    icon_url: Optional[str] = None
    enabled: bool = True


class ConnectionStatusResponse(BaseModel):
    """Response model for a user's connection status."""
    name: str
    display_name: str
    description: Optional[str] = None
    connected: bool
    valid: bool = True  # False if token is expired
    auth_type: str
    icon_url: Optional[str] = None
    scopes: Optional[str] = None
    expires_at: Optional[str] = None
    requires_authorization: bool = False
    has_refresh_token: bool = False
    is_user_defined: bool = False
    user_server_id: Optional[str] = None


class ConnectionsListResponse(BaseModel):
    """Response model for listing all connections."""
    connections: List[ConnectionStatusResponse]
    expired: List[Dict[str, Any]]  # Connections with expired tokens


class AuthorizeResponse(BaseModel):
    """Response model for authorization URL."""
    authorization_url: str
    connection_name: str
    message: str


# =============================================================================
# Database Session Helper
# =============================================================================

def _get_db_session():
    """Get database session from provider."""
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'metadata'):
        return provider.metadata.get_db_session()
    return None



# =============================================================================
# Connection Config Helpers
# =============================================================================

def _get_connection_configs(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all OAuth2 connection configurations.

    Combines global configs from BOND_MCP_CONFIG with user-defined OAuth servers
    from the database when user_id is provided.
    """
    configs = []

    try:
        config = Config.config()
        mcp_config = config.get_mcp_config()
        servers = mcp_config.get('mcpServers', {})

        for name, server_config in servers.items():
            auth_type = server_config.get('auth_type', 'bond_jwt')
            if auth_type == 'oauth2':
                oauth_config = server_config.get('oauth_config', {})

                # Build extra_config with client_secret from oauth_config
                extra_config = server_config.get('extra_config', {}).copy()

                client_secret = resolve_client_secret(oauth_config)
                if client_secret:
                    extra_config['client_secret'] = client_secret
                elif 'client_secret' in oauth_config or 'client_secret_arn' in oauth_config:
                    # Only warn if a secret was explicitly configured but failed to resolve
                    LOGGER.warning("Could not resolve client_secret for connection '%s'", safe_id(name))

                configs.append({
                    "name": name,
                    "display_name": server_config.get('display_name', name.title()),
                    "description": server_config.get('description', f"Connect to {name}"),
                    "url": server_config.get('url', ''),
                    "transport": server_config.get('transport', 'sse'),
                    "auth_type": auth_type,
                    "oauth_client_id": oauth_config.get('client_id'),
                    "oauth_authorize_url": oauth_config.get('authorize_url'),
                    "oauth_token_url": oauth_config.get('token_url'),
                    "oauth_scopes": oauth_config.get('scopes'),
                    "oauth_redirect_uri": oauth_config.get('redirect_uri'),
                    "icon_url": server_config.get('icon_url'),
                    "extra_config": extra_config,
                    "is_user_defined": False
                })

        LOGGER.debug(f"Loaded {len(configs)} OAuth2 connection configs from BOND_MCP_CONFIG")

    except Exception as e:
        LOGGER.error(f"Error loading connection configs: {e}")

    # Load user-defined OAuth servers from database
    if user_id:
        try:
            user_oauth_configs = _get_user_oauth_connection_configs(user_id)
            configs.extend(user_oauth_configs)
            if user_oauth_configs:
                LOGGER.debug(f"Loaded {len(user_oauth_configs)} user-defined OAuth2 connections for user")
        except Exception as e:
            LOGGER.error(f"Error loading user OAuth connection configs: {e}")

    return configs


def _get_user_oauth_connection_configs(user_id: str) -> List[Dict[str, Any]]:
    """
    Get OAuth2 connection configurations from user-defined MCP servers.
    Returns configs in the same format as global configs.
    """
    import json
    from bondable.bond.providers.metadata import UserMcpServer
    from bondable.bond.auth.token_encryption import decrypt_token

    session = _get_db_session()
    if not session:
        return []

    try:
        user_servers = session.query(UserMcpServer).filter(
            UserMcpServer.owner_user_id == user_id,
            UserMcpServer.auth_type == 'oauth2',
            UserMcpServer.is_active == True,  # noqa: E712
            UserMcpServer.oauth_config_encrypted.isnot(None)
        ).all()

        configs = []
        for server in user_servers:
            try:
                oauth_data = json.loads(decrypt_token(server.oauth_config_encrypted))
                internal_name = f"user_{server.id}"

                configs.append({
                    "name": internal_name,
                    "display_name": server.display_name,
                    "description": server.description or f"Connect to {server.display_name}",
                    "url": server.url,
                    "transport": server.transport,
                    "auth_type": "oauth2",
                    "oauth_client_id": oauth_data.get("client_id"),
                    "oauth_authorize_url": oauth_data.get("authorize_url"),
                    "oauth_token_url": oauth_data.get("token_url"),
                    "oauth_scopes": oauth_data.get("scopes"),
                    "oauth_redirect_uri": oauth_data.get("redirect_uri"),
                    "icon_url": None,
                    "extra_config": {"client_secret": oauth_data.get("client_secret")},
                    "is_user_defined": True,
                    "user_server_id": server.id,
                })
            except Exception as e:
                LOGGER.warning(f"Error decrypting OAuth config for user server {safe_id(server.id)}: {e}")

        return configs
    except Exception as e:
        LOGGER.error(f"Error querying user OAuth servers: {e}")
        return []


def _get_connection_config(connection_name: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a specific connection configuration by name."""
    configs = _get_connection_configs(user_id=user_id)
    for config in configs:
        if config["name"] == connection_name:
            return config
    return None


# =============================================================================
# OAuth State Management (Database-backed)
# =============================================================================

def _save_oauth_state(
    state: str,
    user_id: str,
    connection_name: str,
    code_verifier: str,
    redirect_uri: str
) -> bool:
    """Save OAuth state to database."""
    session = _get_db_session()
    if session is None:
        LOGGER.error("No database session available for OAuth state")
        return False

    try:
        from bondable.bond.providers.metadata import ConnectionOAuthState

        # Clean up old states (older than 10 minutes)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.query(ConnectionOAuthState).filter(
            ConnectionOAuthState.created_at < cutoff
        ).delete()

        # Save new state
        oauth_state = ConnectionOAuthState(
            state=state,
            user_id=user_id,
            connection_name=connection_name,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri
        )
        session.add(oauth_state)
        session.commit()
        return True

    except Exception as e:
        LOGGER.error(f"Error saving OAuth state: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def _get_and_delete_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Get and delete OAuth state from database."""
    session = _get_db_session()
    if session is None:
        return None

    try:
        from bondable.bond.providers.metadata import ConnectionOAuthState

        oauth_state = session.query(ConnectionOAuthState).filter(
            ConnectionOAuthState.state == state
        ).first()

        if oauth_state is None:
            return None

        result = {
            "user_id": oauth_state.user_id,
            "connection_name": oauth_state.connection_name,
            "code_verifier": oauth_state.code_verifier,
            "redirect_uri": oauth_state.redirect_uri
        }

        # Delete the state
        session.delete(oauth_state)
        session.commit()

        return result

    except Exception as e:
        LOGGER.error(f"Error getting OAuth state: {e}")
        session.rollback()
        return None
    finally:
        session.close()


# PKCE generation moved to bondable.bond.auth.oauth_utils.generate_pkce_pair


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=ConnectionsListResponse)
async def list_connections(
    current_user: Annotated[User, Depends(get_current_user)]
) -> ConnectionsListResponse:
    """
    List all available connections with user's status.

    Returns both the connection configurations and whether the user
    has connected to each one, including whether tokens are expired.
    """
    LOGGER.debug(f"[Connections] Listing connections for user {current_user.email}")


    # Get all connection configs (including user-defined OAuth servers)
    configs = _get_connection_configs(user_id=current_user.user_id)

    # Get user's connection tokens
    token_cache = get_mcp_token_cache()
    user_connections = token_cache.get_user_connections(current_user.user_id)

    connections = []
    expired = []

    for config in configs:
        name = config["name"]
        user_conn = user_connections.get(name, {})

        connected = user_conn.get("connected", False)
        valid = user_conn.get("valid", True) if connected else True
        has_refresh_token = user_conn.get("has_refresh_token", False)

        # Treat connections with refresh tokens as valid for display purposes
        # since they will auto-refresh on next use
        display_valid = valid or (connected and has_refresh_token)

        connection_status = ConnectionStatusResponse(
            name=name,
            display_name=config.get("display_name", name.title()),
            description=config.get("description"),
            connected=connected,
            valid=display_valid,
            auth_type=config.get("auth_type", "oauth2"),
            icon_url=config.get("icon_url"),
            scopes=user_conn.get("scopes"),
            expires_at=user_conn.get("expires_at"),
            requires_authorization=not connected,
            has_refresh_token=has_refresh_token,
            is_user_defined=config.get("is_user_defined", False),
            user_server_id=config.get("user_server_id")
        )
        connections.append(connection_status)

        # Track expired connections (only if no refresh token available)
        if connected and not valid and not has_refresh_token:
            expired.append({
                "name": name,
                "display_name": config.get("display_name", name.title()),
                "expires_at": user_conn.get("expires_at")
            })

    return ConnectionsListResponse(connections=connections, expired=expired)


@router.get("/{connection_name}/authorize", response_model=AuthorizeResponse)
async def authorize_connection(
    connection_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> AuthorizeResponse:
    """
    Initiate OAuth2 authorization for a connection.

    Returns an authorization URL that the client should open in a browser/popup.

    Args:
        connection_name: Name of the connection to authorize

    Returns:
        Authorization URL to redirect user to
    """
    config = _get_connection_config(connection_name, user_id=current_user.user_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection '{connection_name}' not found"
        )

    if config.get("auth_type") != "oauth2":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection '{connection_name}' does not use OAuth2"
        )

    authorize_url = config.get("oauth_authorize_url")
    if not authorize_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No authorize URL configured for '{connection_name}'"
        )

    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()

    # Generate state for CSRF protection
    state = generate_oauth_state()

    # Build redirect URI - use configured one if available, otherwise generate
    configured_redirect = config.get("oauth_redirect_uri")
    if configured_redirect:
        redirect_uri = configured_redirect
        LOGGER.debug(f"[Connections] Using configured redirect_uri")
    else:
        jwt_config = Config.config().get_jwt_config()
        base_url = jwt_config.JWT_REDIRECT_URI.rstrip('/')
        redirect_uri = f"{base_url}/connections/{connection_name}/callback"
        LOGGER.debug(f"[Connections] Using generated redirect_uri")

    # Store state in database
    if not _save_oauth_state(state, current_user.user_id, connection_name, code_verifier, redirect_uri):
        LOGGER.error(f"Failed to save OAuth state for connection: {connection_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save OAuth state"
        )

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": config.get("oauth_client_id", ""),
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }

    # Add scopes if specified
    scopes = config.get("oauth_scopes")
    if scopes:
        params["scope"] = scopes

    authorization_url = f"{authorize_url}?{urlencode(params)}"

    return AuthorizeResponse(
        authorization_url=authorization_url,
        connection_name=connection_name,
        message="Open authorization_url in browser to authorize"
    )


@router.get("/{connection_name}/callback")
async def oauth_callback(
    connection_name: str,
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter for CSRF validation")
) -> RedirectResponse:
    """
    Handle OAuth2 callback from external service.

    Exchanges authorization code for access token and stores encrypted in database.
    Redirects to frontend with success/error status.
    """
    # Validate and retrieve state
    state_data = _get_and_delete_oauth_state(state)
    if state_data is None:
        LOGGER.warning("Invalid OAuth state - possible CSRF attack or expired state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter - possible CSRF attack or expired state"
        )

    user_id = state_data["user_id"]
    code_verifier = state_data["code_verifier"]
    redirect_uri = state_data["redirect_uri"]

    # Get connection configuration (include user-defined servers via user_id from state)
    config = _get_connection_config(connection_name, user_id=user_id)
    if config is None:
        LOGGER.error("Connection config not found during OAuth callback")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection '{connection_name}' not found"
        )

    # Sanitize the config name for use in redirects only (not logging).
    # re.sub breaks CodeQL's taint chain from config (which also holds secrets).
    safe_name: str = re.sub(r"[^A-Za-z0-9_.-]", "_", config.get("name", ""))

    token_url = config.get("oauth_token_url")
    if not token_url:
        LOGGER.error("No token URL configured for connection")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No token URL configured for this connection"
        )

    # Exchange code for token
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier
    }

    # Add client credentials
    client_id = config.get("oauth_client_id")
    if client_id:
        token_data["client_id"] = client_id

    # Note: Most OAuth providers don't require client_secret with PKCE,
    # but some might. Check extra_config for client_secret if needed.
    client_secret = config.get("extra_config", {}).get("client_secret")
    if client_secret:
        token_data["client_secret"] = client_secret

    jwt_config = Config.config().get_jwt_config()
    frontend_url = jwt_config.JWT_REDIRECT_URI.rstrip('/')

    # Validate redirect URL against allowed domains
    if not is_safe_redirect_url(frontend_url):
        LOGGER.error("JWT_REDIRECT_URI is not on allowed domain list")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: invalid redirect URL"
        )

    # Note: Connection name is intentionally omitted from log messages below
    # to satisfy CodeQL's clear-text-logging rule. The connection name is
    # visible in HTTP access logs via the request path.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                token_url,
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }
            )
            response.raise_for_status()
            LOGGER.info("OAuth token exchange successful")
            token_response = response.json()

        # Store token in cache (which persists to database).
        # Use config["name"] directly (trusted server config) for storage,
        # not safe_name which is sanitized for URL use only.
        config_name = config["name"]
        token_cache = get_mcp_token_cache()
        token_cache.set_token_from_response(
            user_id=user_id,
            connection_name=config_name,
            token_response=token_response,
            provider=config_name,
            provider_metadata=config.get("extra_config", {})
        )

        LOGGER.info("OAuth token stored successfully")

        # Redirect to frontend with success
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_success={quote(safe_name, safe='')}",
            status_code=status.HTTP_302_FOUND
        )

    except httpx.HTTPStatusError as e:
        LOGGER.error("OAuth token exchange failed: HTTP %s", e.response.status_code)
        # Don't log full response as it may contain sensitive error details
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_error={quote(safe_name, safe='')}&error=token_exchange_failed",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        LOGGER.error("Unexpected error during OAuth callback: %s", type(e).__name__)
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_error={quote(safe_name, safe='')}&error=unknown",
            status_code=status.HTTP_302_FOUND
        )


@router.get("/{connection_name}/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    connection_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> ConnectionStatusResponse:
    """
    Get the status of a specific connection for the current user.
    """
    LOGGER.debug(f"[Connections] Checking status of {connection_name} for user {current_user.email}")


    config = _get_connection_config(connection_name, user_id=current_user.user_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection '{connection_name}' not found"
        )

    token_cache = get_mcp_token_cache()
    user_connections = token_cache.get_user_connections(current_user.user_id)
    user_conn = user_connections.get(connection_name, {})

    connected = user_conn.get("connected", False)
    valid = user_conn.get("valid", True) if connected else True
    has_refresh_token = user_conn.get("has_refresh_token", False)

    # Treat connections with refresh tokens as valid for display purposes
    # since they will auto-refresh on next use
    display_valid = valid or (connected and has_refresh_token)

    return ConnectionStatusResponse(
        name=connection_name,
        display_name=config.get("display_name", connection_name.title()),
        description=config.get("description"),
        connected=connected,
        valid=display_valid,
        auth_type=config.get("auth_type", "oauth2"),
        icon_url=config.get("icon_url"),
        scopes=user_conn.get("scopes"),
        expires_at=user_conn.get("expires_at"),
        requires_authorization=not connected,
        has_refresh_token=has_refresh_token
    )


@router.delete("/{connection_name}")
async def disconnect(
    connection_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Disconnect from a connection by removing the stored token.
    """
    LOGGER.info(f"User {current_user.email} disconnecting from {connection_name}")


    token_cache = get_mcp_token_cache()
    removed = token_cache.clear_token(current_user.user_id, connection_name)

    if removed:
        LOGGER.info(f"Successfully disconnected from {connection_name}")
        return {
            "message": f"Successfully disconnected from '{connection_name}'",
            "connection_name": connection_name,
            "disconnected": True
        }
    else:
        return {
            "message": f"No connection found for '{connection_name}'",
            "connection_name": connection_name,
            "disconnected": False
        }


@router.get("/check-expired")
async def check_expired_connections(
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Check for expired connection tokens.

    Called after login to determine if user needs to re-authenticate any connections.
    """
    LOGGER.debug(f"[Connections] Checking expired connections for user {current_user.email}")


    token_cache = get_mcp_token_cache()
    expired = token_cache.get_expired_connections(current_user.user_id)

    # Get display names for expired connections
    configs = _get_connection_configs()
    config_map = {c["name"]: c for c in configs}

    expired_with_names = []
    for exp in expired:
        config = config_map.get(exp["name"], {})
        expired_with_names.append({
            "name": exp["name"],
            "display_name": config.get("display_name", exp["name"].title()),
            "expires_at": exp.get("expires_at")
        })

    return {
        "has_expired": len(expired_with_names) > 0,
        "expired_connections": expired_with_names
    }
