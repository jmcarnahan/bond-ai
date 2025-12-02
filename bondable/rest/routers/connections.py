"""
Connections Router - API endpoints for managing external service connections.

This router handles OAuth authentication with external services like Atlassian,
storing tokens encrypted in the database for use with MCP tools.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated, List, Dict, Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from bondable.bond.config import Config
from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache, TokenExpiredError
from bondable.bond.auth.oauth_utils import generate_pkce_pair, generate_oauth_state
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user

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


# Token cache initialization no longer needed - it gets DB session automatically from Config


# =============================================================================
# Connection Config Helpers
# =============================================================================

def _get_connection_configs() -> List[Dict[str, Any]]:
    """
    Get all OAuth2 connection configurations from BOND_MCP_CONFIG environment variable.

    Connection configs are now stored exclusively in the BOND_MCP_CONFIG environment
    variable (JSON format). The ConnectionConfig database table has been removed.
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
                if 'client_secret' in oauth_config:
                    extra_config['client_secret'] = oauth_config['client_secret']

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
                    "extra_config": extra_config
                })

        LOGGER.debug(f"Loaded {len(configs)} OAuth2 connection configs from BOND_MCP_CONFIG")

    except Exception as e:
        LOGGER.error(f"Error loading connection configs: {e}")

    return configs


def _get_connection_config(connection_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific connection configuration by name."""
    configs = _get_connection_configs()
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

    # Initialize token cache with database

    # Get all connection configs
    configs = _get_connection_configs()

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

        connection_status = ConnectionStatusResponse(
            name=name,
            display_name=config.get("display_name", name.title()),
            description=config.get("description"),
            connected=connected,
            valid=valid,
            auth_type=config.get("auth_type", "oauth2"),
            icon_url=config.get("icon_url"),
            scopes=user_conn.get("scopes"),
            expires_at=user_conn.get("expires_at"),
            requires_authorization=not connected
        )
        connections.append(connection_status)

        # Track expired connections
        if connected and not valid:
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
    LOGGER.info(f"[Connections] ========== AUTHORIZE START ==========")
    LOGGER.info(f"[Connections] User: {current_user.email} (ID: {current_user.user_id})")
    LOGGER.info(f"[Connections] Connection: {connection_name}")

    config = _get_connection_config(connection_name)
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
    LOGGER.info(f"[Connections] Saving OAuth state to database:")
    LOGGER.info(f"[Connections]   state: {state[:20]}...")
    LOGGER.info(f"[Connections]   user_id: {current_user.user_id}")
    LOGGER.info(f"[Connections]   connection_name: {connection_name}")
    LOGGER.info(f"[Connections]   code_verifier: {code_verifier[:20]}...")
    LOGGER.info(f"[Connections]   redirect_uri: {redirect_uri}")

    if not _save_oauth_state(state, current_user.user_id, connection_name, code_verifier, redirect_uri):
        LOGGER.error(f"[Connections] Failed to save OAuth state!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save OAuth state"
        )
    LOGGER.info(f"[Connections] OAuth state saved successfully")

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

    LOGGER.info(f"[Connections] Authorization URL params:")
    LOGGER.info(f"[Connections]   authorize_url: {authorize_url}")
    LOGGER.info(f"[Connections]   client_id: {config.get('oauth_client_id', '')}")
    LOGGER.info(f"[Connections]   redirect_uri: {redirect_uri}")
    LOGGER.info(f"[Connections]   scopes: {scopes}")
    LOGGER.info(f"[Connections] ========== AUTHORIZE END ==========")

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
    LOGGER.info(f"[Connections] ========== CALLBACK START ==========")
    LOGGER.info(f"[Connections] Connection: {connection_name}")
    LOGGER.info(f"[Connections] Received code: {code[:30]}..." if len(code) > 30 else f"[Connections] Received code: {code}")
    LOGGER.info(f"[Connections] Received state (raw from callback): {state}")

    # Validate and retrieve state
    LOGGER.info(f"[Connections] Looking up OAuth state in database...")
    state_data = _get_and_delete_oauth_state(state)
    if state_data is None:
        LOGGER.warning(f"[Connections] Invalid state parameter for {connection_name} - state not found in database!")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter - possible CSRF attack or expired state"
        )

    user_id = state_data["user_id"]
    code_verifier = state_data["code_verifier"]
    redirect_uri = state_data["redirect_uri"]

    LOGGER.info(f"[Connections] State data retrieved successfully:")
    LOGGER.info(f"[Connections]   user_id: {user_id}")
    LOGGER.info(f"[Connections]   connection_name from state: {state_data.get('connection_name', 'N/A')}")
    LOGGER.info(f"[Connections]   code_verifier: {code_verifier[:20]}..." if code_verifier else "[Connections]   code_verifier: None")
    LOGGER.info(f"[Connections]   redirect_uri: {redirect_uri}")

    # Get connection configuration
    config = _get_connection_config(connection_name)
    if config is None:
        LOGGER.error(f"[Connections] Connection config not found for: {connection_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection '{connection_name}' not found"
        )

    token_url = config.get("oauth_token_url")
    if not token_url:
        LOGGER.error(f"[Connections] No token URL configured for: {connection_name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No token URL configured for '{connection_name}'"
        )

    LOGGER.info(f"[Connections] Token URL: {token_url}")

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
        LOGGER.info(f"[Connections] Using client_secret from extra_config (redacted)")

    LOGGER.info(f"[Connections] Token exchange request:")
    LOGGER.info(f"[Connections]   token_url: {token_url}")
    LOGGER.info(f"[Connections]   grant_type: authorization_code")
    LOGGER.info(f"[Connections]   client_id: {client_id}")
    LOGGER.info(f"[Connections]   redirect_uri: {redirect_uri}")
    LOGGER.info(f"[Connections]   code_verifier present: {bool(code_verifier)}")

    jwt_config = Config.config().get_jwt_config()
    frontend_url = jwt_config.JWT_REDIRECT_URI.rstrip('/')

    try:
        LOGGER.info(f"[Connections] Sending token exchange request to {token_url}...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            LOGGER.info(f"[Connections] Token exchange response status: {response.status_code}")
            response.raise_for_status()
            token_response = response.json()

        LOGGER.info(f"[Connections] Token response received:")
        LOGGER.info(f"[Connections]   token_type: {token_response.get('token_type', 'N/A')}")
        LOGGER.info(f"[Connections]   expires_in: {token_response.get('expires_in', 'N/A')}")
        LOGGER.info(f"[Connections]   scope: {token_response.get('scope', 'N/A')}")
        LOGGER.info(f"[Connections]   access_token present: {bool(token_response.get('access_token'))}")
        LOGGER.info(f"[Connections]   refresh_token present: {bool(token_response.get('refresh_token'))}")

        # Store token in cache (which persists to database)
        token_cache = get_mcp_token_cache()
        token_cache.set_token_from_response(
            user_id=user_id,
            connection_name=connection_name,
            token_response=token_response,
            provider=connection_name,
            provider_metadata=config.get("extra_config", {})
        )

        LOGGER.info(f"[Connections] Token stored successfully for connection {connection_name}")
        LOGGER.info(f"[Connections] Redirecting to: {frontend_url}/connections?connection_success={connection_name}")
        LOGGER.info(f"[Connections] ========== CALLBACK SUCCESS ==========")

        # Redirect to frontend with success
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_success={connection_name}",
            status_code=status.HTTP_302_FOUND
        )

    except httpx.HTTPStatusError as e:
        LOGGER.error(f"[Connections] Token exchange failed!")
        LOGGER.error(f"[Connections]   Status code: {e.response.status_code}")
        LOGGER.error(f"[Connections]   Response: {e.response.text}")
        LOGGER.info(f"[Connections] ========== CALLBACK FAILED ==========")
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_error={connection_name}&error=token_exchange_failed",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        LOGGER.error(f"[Connections] Unexpected error: {type(e).__name__}: {e}")
        LOGGER.info(f"[Connections] ========== CALLBACK FAILED ==========")
        return RedirectResponse(
            url=f"{frontend_url}/connections?connection_error={connection_name}&error=unknown",
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

    # Initialize token cache with database

    config = _get_connection_config(connection_name)
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

    return ConnectionStatusResponse(
        name=connection_name,
        display_name=config.get("display_name", connection_name.title()),
        description=config.get("description"),
        connected=connected,
        valid=valid,
        auth_type=config.get("auth_type", "oauth2"),
        icon_url=config.get("icon_url"),
        scopes=user_conn.get("scopes"),
        expires_at=user_conn.get("expires_at"),
        requires_authorization=not connected
    )


@router.delete("/{connection_name}")
async def disconnect(
    connection_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Disconnect from a connection by removing the stored token.
    """
    LOGGER.info(f"[Connections] User {current_user.email} disconnecting from {connection_name}")

    # Initialize token cache with database

    token_cache = get_mcp_token_cache()
    removed = token_cache.clear_token(current_user.user_id, connection_name)

    if removed:
        LOGGER.info(f"[Connections] Successfully disconnected from {connection_name}")
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

    # Initialize token cache with database

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
