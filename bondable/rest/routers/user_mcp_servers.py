"""
User MCP Servers Router - API endpoints for managing user-defined MCP server configurations.

Users can add their own MCP server configs (with none, header, or oauth2 auth).
These servers appear alongside global servers in tool discovery and agent creation.
"""

import json
import logging
import re
import uuid
from typing import Annotated, Any, List, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from bondable.bond.config import Config
from bondable.bond.auth.token_encryption import encrypt_token, decrypt_token
from bondable.bond.providers.metadata import UserMcpServer
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.utils.logging_utils import safe_id

router = APIRouter(prefix="/user-mcp-servers", tags=["User MCP Servers"])
LOGGER = logging.getLogger(__name__)

# Server name pattern: lowercase letters, digits, underscores; must start with letter
SERVER_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,63}$')

# SSRF blocked hostnames for user-defined MCP servers.
# Unlike the web browsing SSRF list, we do NOT block localhost here because
# users legitimately run MCP servers locally. We only block cloud metadata endpoints.
_MCP_SSRF_BLOCKED = frozenset({
    "metadata.google.internal",
    "169.254.169.254",
    "169.254.170.2",  # AWS ECS task metadata
    "fd00:ec2::254",  # AWS IMDSv2 IPv6
})


# =============================================================================
# Request/Response Models
# =============================================================================

class OAuthConfigInput(BaseModel):
    """OAuth2 configuration provided by the user."""
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: Optional[str] = None
    redirect_uri: str
    provider: Optional[str] = None  # e.g., "atlassian", "microsoft"

    @field_validator('authorize_url', 'token_url')
    @classmethod
    def validate_https_urls(cls, v, info):
        parsed = urlparse(v)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"{info.field_name} must use http or https scheme")
        if not parsed.hostname:
            raise ValueError(f"{info.field_name} must have a valid hostname")
        return v


class UserMcpServerCreate(BaseModel):
    """Request model for creating a user MCP server."""
    server_name: str
    display_name: str
    description: Optional[str] = None
    url: str
    transport: str = "streamable-http"
    auth_type: str = "none"  # none | header | oauth2
    headers: Optional[Dict[str, str]] = None
    oauth_config: Optional[OAuthConfigInput] = None
    extra_config: Optional[Dict[str, Any]] = None  # cloud_id, site_url, etc.

    @field_validator('server_name')
    @classmethod
    def validate_server_name(cls, v):
        if not SERVER_NAME_PATTERN.match(v):
            raise ValueError(
                "server_name must start with a lowercase letter and contain only "
                "lowercase letters, digits, and underscores (max 64 chars)"
            )
        return v

    @field_validator('transport')
    @classmethod
    def validate_transport(cls, v):
        if v not in ('streamable-http', 'sse'):
            raise ValueError("transport must be 'streamable-http' or 'sse'")
        return v

    @field_validator('auth_type')
    @classmethod
    def validate_auth_type(cls, v):
        if v not in ('none', 'header', 'oauth2'):
            raise ValueError("auth_type must be 'none', 'header', or 'oauth2'")
        return v

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        parsed = urlparse(v)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError("url must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("url must have a valid hostname")
        return v


class UserMcpServerUpdate(BaseModel):
    """Request model for updating a user MCP server."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    oauth_config: Optional[OAuthConfigInput] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator('transport')
    @classmethod
    def validate_transport(cls, v):
        if v is not None and v not in ('streamable-http', 'sse'):
            raise ValueError("transport must be 'streamable-http' or 'sse'")
        return v

    @field_validator('auth_type')
    @classmethod
    def validate_auth_type(cls, v):
        if v is not None and v not in ('none', 'header', 'oauth2'):
            raise ValueError("auth_type must be 'none', 'header', or 'oauth2'")
        return v

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if v is not None:
            parsed = urlparse(v)
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("url must use http or https scheme")
            if not parsed.hostname:
                raise ValueError("url must have a valid hostname")
        return v


class OAuthConfigDisplay(BaseModel):
    """OAuth config with client_secret redacted."""
    client_id: str
    authorize_url: str
    token_url: str
    scopes: Optional[str] = None
    redirect_uri: str
    provider: Optional[str] = None


class UserMcpServerResponse(BaseModel):
    """Response model for a user MCP server."""
    id: str
    server_name: str
    display_name: str
    description: Optional[str] = None
    url: str
    transport: str
    auth_type: str
    has_headers: bool = False
    has_oauth_config: bool = False
    oauth_config: Optional[OAuthConfigDisplay] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserMcpServerListResponse(BaseModel):
    """Response model for listing user MCP servers."""
    servers: List[UserMcpServerResponse]
    total: int


class TestConnectionResponse(BaseModel):
    """Response model for testing connectivity."""
    success: bool
    tool_count: int = 0
    tools: List[str] = []
    error: Optional[str] = None


# =============================================================================
# Helpers
# =============================================================================

def _get_db_session():
    """Get database session from the provider."""
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'metadata'):
        return provider.metadata.get_db_session()
    return None


def _validate_url_ssrf(url: str):
    """Validate URL is not targeting cloud metadata endpoints (SSRF protection)."""
    import ipaddress
    parsed = urlparse(url)
    hostname = (parsed.hostname or '').lower()

    # Check exact hostname blocklist
    if hostname in _MCP_SSRF_BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL hostname '{hostname}' is blocked for security reasons"
        )

    # Check if the hostname resolves to a link-local IP (169.254.0.0/16)
    # This catches alternate representations like hex, octal, or mapped IPv6
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_link_local:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL hostname '{hostname}' is blocked for security reasons"
            )
    except ValueError:
        pass  # Not an IP literal — hostname check above is sufficient


def _validate_no_global_collision(server_name: str):
    """Ensure server_name doesn't collide with a global MCP server name."""
    try:
        mcp_config = Config.config().get_mcp_config()
        global_servers = mcp_config.get('mcpServers', {})
        if server_name in global_servers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Server name '{server_name}' conflicts with a global MCP server"
            )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.debug("Could not check global MCP config for collision: %s", e)


def _validate_auth_fields(auth_type: str, headers: Optional[Dict], oauth_config: Optional[OAuthConfigInput]):
    """Validate that auth-related fields match the auth_type."""
    if auth_type == 'header' and not headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="headers are required when auth_type is 'header'"
        )
    if auth_type == 'oauth2' and not oauth_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="oauth_config is required when auth_type is 'oauth2'"
        )
    if auth_type == 'none':
        if headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="headers should not be provided when auth_type is 'none'"
            )
        if oauth_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="oauth_config should not be provided when auth_type is 'none'"
            )
    if auth_type == 'header' and oauth_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="oauth_config should not be provided when auth_type is 'header'"
        )
    if auth_type == 'oauth2' and headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="headers should not be provided when auth_type is 'oauth2'"
        )


def _encrypt_headers(headers: Optional[Dict[str, str]]) -> Optional[str]:
    """Encrypt headers dict as JSON string."""
    if not headers:
        return None
    return encrypt_token(json.dumps(headers))


def _decrypt_headers(encrypted: Optional[str]) -> Optional[Dict[str, str]]:
    """Decrypt encrypted headers JSON string."""
    if not encrypted:
        return None
    return json.loads(decrypt_token(encrypted))


def _encrypt_oauth_config(oauth_config: Optional[OAuthConfigInput]) -> Optional[str]:
    """Encrypt OAuth config as JSON string."""
    if not oauth_config:
        return None
    return encrypt_token(json.dumps(oauth_config.model_dump()))


def _decrypt_oauth_config(encrypted: Optional[str]) -> Optional[Dict]:
    """Decrypt encrypted OAuth config JSON string."""
    if not encrypted:
        return None
    return json.loads(decrypt_token(encrypted))


def _server_to_response(server: UserMcpServer) -> UserMcpServerResponse:
    """Convert a UserMcpServer DB record to a response model (secrets redacted)."""
    oauth_display = None
    if server.oauth_config_encrypted:
        try:
            oauth_data = _decrypt_oauth_config(server.oauth_config_encrypted)
            if oauth_data:
                oauth_display = OAuthConfigDisplay(
                    client_id=oauth_data.get('client_id', ''),
                    authorize_url=oauth_data.get('authorize_url', ''),
                    token_url=oauth_data.get('token_url', ''),
                    scopes=oauth_data.get('scopes'),
                    redirect_uri=oauth_data.get('redirect_uri', ''),
                    provider=oauth_data.get('provider'),
                )
        except Exception as e:
            LOGGER.warning("Failed to decrypt oauth_config for server %s: %s", safe_id(server.id), e)

    return UserMcpServerResponse(
        id=server.id,
        server_name=server.server_name,
        display_name=server.display_name,
        description=server.description,
        url=server.url,
        transport=server.transport,
        auth_type=server.auth_type,
        has_headers=server.headers_encrypted is not None,
        has_oauth_config=server.oauth_config_encrypted is not None,
        oauth_config=oauth_display,
        extra_config=server.extra_config if server.extra_config else None,
        is_active=server.is_active,
        created_at=server.created_at.isoformat() if server.created_at else None,
        updated_at=server.updated_at.isoformat() if server.updated_at else None,
    )


def _check_agent_references(server: UserMcpServer, db_session) -> List[str]:
    """Check if any agents reference tools from this server. Returns list of agent names."""
    from bondable.bond.providers.bedrock.BedrockMCP import _hash_server_name
    from bondable.bond.providers.metadata import AgentRecord
    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockAgentOptions

    internal_name = get_user_server_internal_name(server.owner_user_id, server.server_name)
    server_hash = _hash_server_name(internal_name)
    tool_prefix = f"{internal_name}:"

    referencing_agents = []
    try:
        options_list = db_session.query(BedrockAgentOptions).filter(
            BedrockAgentOptions.mcp_tools.isnot(None)
        ).all()

        for opts in options_list:
            mcp_tools = opts.mcp_tools or []
            if isinstance(mcp_tools, str):
                mcp_tools = json.loads(mcp_tools)
            for tool in mcp_tools:
                if tool.startswith(tool_prefix) or f".{server_hash}." in tool:
                    agent = db_session.query(AgentRecord).filter(
                        AgentRecord.agent_id == opts.agent_id
                    ).first()
                    if agent:
                        referencing_agents.append(agent.name)
                    break
    except Exception as e:
        LOGGER.warning("Error checking agent references: %s", e)

    return referencing_agents


def get_user_server_internal_name(owner_user_id: str, server_name: str) -> str:
    """Get the internal name used for hashing. Exported for use by other modules."""
    return f"user_{owner_user_id[:8]}_{server_name}"


# =============================================================================
# Endpoints
# =============================================================================

@router.post("", response_model=UserMcpServerResponse, status_code=status.HTTP_201_CREATED)
async def create_user_mcp_server(
    request: UserMcpServerCreate,
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserMcpServerResponse:
    """Create a new user-defined MCP server configuration."""
    LOGGER.info("[UserMCP] Create request from user %s: server_name=%s",
                safe_id(current_user.user_id), safe_id(request.server_name))

    # Validate
    _validate_url_ssrf(request.url)
    _validate_no_global_collision(request.server_name)
    _validate_auth_fields(request.auth_type, request.headers, request.oauth_config)

    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        # Check uniqueness within user's servers
        existing = db_session.query(UserMcpServer).filter(
            UserMcpServer.owner_user_id == current_user.user_id,
            UserMcpServer.server_name == request.server_name
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a server named '{request.server_name}'"
            )

        server = UserMcpServer(
            id=str(uuid.uuid4()),
            owner_user_id=current_user.user_id,
            server_name=request.server_name,
            display_name=request.display_name,
            description=request.description,
            url=request.url,
            transport=request.transport,
            auth_type=request.auth_type,
            headers_encrypted=_encrypt_headers(request.headers),
            oauth_config_encrypted=_encrypt_oauth_config(request.oauth_config),
            extra_config=request.extra_config or {},
            is_active=True,
        )
        db_session.add(server)
        db_session.commit()
        db_session.refresh(server)

        LOGGER.info("[UserMCP] Created server %s for user %s", safe_id(server.id), safe_id(current_user.user_id))
        return _server_to_response(server)

    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        LOGGER.error("[UserMCP] Error creating server: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create server")


@router.get("", response_model=UserMcpServerListResponse)
async def list_user_mcp_servers(
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserMcpServerListResponse:
    """List the current user's MCP server configurations."""
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        servers = db_session.query(UserMcpServer).filter(
            UserMcpServer.owner_user_id == current_user.user_id
        ).order_by(UserMcpServer.created_at).all()

        return UserMcpServerListResponse(
            servers=[_server_to_response(s) for s in servers],
            total=len(servers)
        )
    except Exception as e:
        LOGGER.error("[UserMCP] Error listing servers: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list servers")


# =============================================================================
# Import endpoint — MUST be before /{server_id} routes to avoid path collision
# =============================================================================

class ImportJsonRequest(BaseModel):
    """Import a server config from JSON (same format as BOND_MCP_CONFIG entries)."""
    server_name: str
    config: Dict[str, Any]  # Raw JSON config matching BOND_MCP_CONFIG format


@router.post("/import", response_model=UserMcpServerResponse, status_code=status.HTTP_201_CREATED)
async def import_user_mcp_server(
    request: ImportJsonRequest,
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserMcpServerResponse:
    """Import a server config from JSON (same format as BOND_MCP_CONFIG entries).

    Example JSON config:
    {
        "server_name": "microsoft",
        "config": {
            "url": "http://localhost:5557/mcp",
            "auth_type": "oauth2",
            "transport": "streamable-http",
            "display_name": "Microsoft",
            "description": "Connect to Microsoft email",
            "oauth_config": { ... },
            "cloud_id": "...",
            "site_url": "..."
        }
    }
    """
    config = request.config
    server_name = request.server_name

    # Validate server_name
    if not SERVER_NAME_PATTERN.match(server_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="server_name must start with a lowercase letter and contain only lowercase letters, digits, and underscores"
        )

    # Extract known fields from config
    url = config.get('url', '')
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config must include 'url'")

    transport = config.get('transport', 'streamable-http')
    auth_type = config.get('auth_type', 'none')
    display_name = config.get('display_name', server_name.replace('_', ' ').title())
    description = config.get('description')
    headers = config.get('headers')
    oauth_config_data = config.get('oauth_config')

    # Validate
    _validate_url_ssrf(url)
    _validate_no_global_collision(server_name)

    if auth_type not in ('none', 'header', 'oauth2', 'bond_jwt'):
        auth_type = 'none'
    # Treat bond_jwt as none for user-defined servers
    if auth_type == 'bond_jwt':
        auth_type = 'none'

    # Build encrypted fields
    headers_encrypted = None
    if headers and auth_type == 'header':
        headers_encrypted = _encrypt_headers(headers)

    oauth_config_encrypted = None
    if oauth_config_data and auth_type == 'oauth2':
        # Validate required OAuth fields
        for field in ('client_id', 'authorize_url', 'token_url', 'redirect_uri'):
            if not oauth_config_data.get(field):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"oauth_config must include '{field}'"
                )
        # client_secret may be missing (for PKCE-only flows) — allow it
        oauth_config_encrypted = encrypt_token(json.dumps(oauth_config_data))

    # Collect extra config (everything not in the known fields)
    known_keys = {'url', 'transport', 'auth_type', 'display_name', 'description',
                  'headers', 'oauth_config', 'icon_url'}
    extra_config = {k: v for k, v in config.items() if k not in known_keys and v is not None}

    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        existing = db_session.query(UserMcpServer).filter(
            UserMcpServer.owner_user_id == current_user.user_id,
            UserMcpServer.server_name == server_name
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a server named '{server_name}'"
            )

        server = UserMcpServer(
            id=str(uuid.uuid4()),
            owner_user_id=current_user.user_id,
            server_name=server_name,
            display_name=display_name,
            description=description,
            url=url,
            transport=transport,
            auth_type=auth_type,
            headers_encrypted=headers_encrypted,
            oauth_config_encrypted=oauth_config_encrypted,
            extra_config=extra_config,
            is_active=True,
        )
        db_session.add(server)
        db_session.commit()
        db_session.refresh(server)

        LOGGER.info("[UserMCP] Imported server %s for user %s", safe_id(server.id), safe_id(current_user.user_id))
        return _server_to_response(server)

    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        LOGGER.error("[UserMCP] Error importing server: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to import server")


# =============================================================================
# Per-server endpoints (/{server_id}/...)
# =============================================================================

@router.get("/{server_id}", response_model=UserMcpServerResponse)
async def get_user_mcp_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserMcpServerResponse:
    """Get a specific user MCP server configuration (secrets redacted)."""
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    server = db_session.query(UserMcpServer).filter(
        UserMcpServer.id == server_id,
        UserMcpServer.owner_user_id == current_user.user_id
    ).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    return _server_to_response(server)


@router.put("/{server_id}", response_model=UserMcpServerResponse)
async def update_user_mcp_server(
    server_id: str,
    request: UserMcpServerUpdate,
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserMcpServerResponse:
    """Update a user MCP server configuration."""
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        server = db_session.query(UserMcpServer).filter(
            UserMcpServer.id == server_id,
            UserMcpServer.owner_user_id == current_user.user_id
        ).first()
        if not server:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

        # Determine effective auth_type for validation
        effective_auth_type = request.auth_type if request.auth_type is not None else server.auth_type

        # If auth_type is changing, validate the new combination
        if request.auth_type is not None:
            effective_headers = request.headers
            effective_oauth = request.oauth_config
            # When changing auth_type, require the matching fields
            _validate_auth_fields(effective_auth_type, effective_headers, effective_oauth)

        if request.url is not None:
            _validate_url_ssrf(request.url)
            server.url = request.url
        if request.display_name is not None:
            server.display_name = request.display_name
        if request.description is not None:
            server.description = request.description
        if request.transport is not None:
            server.transport = request.transport
        if request.auth_type is not None:
            server.auth_type = request.auth_type
            # Clear the old auth data when switching types
            if request.auth_type == 'none':
                server.headers_encrypted = None
                server.oauth_config_encrypted = None
            elif request.auth_type == 'header':
                server.oauth_config_encrypted = None
                if request.headers is not None:
                    server.headers_encrypted = _encrypt_headers(request.headers)
            elif request.auth_type == 'oauth2':
                server.headers_encrypted = None
                if request.oauth_config is not None:
                    server.oauth_config_encrypted = _encrypt_oauth_config(request.oauth_config)
        else:
            # Auth type not changing, just update the provided fields
            if request.headers is not None:
                if effective_auth_type != 'header':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="headers can only be set when auth_type is 'header'"
                    )
                server.headers_encrypted = _encrypt_headers(request.headers)
            if request.oauth_config is not None:
                if effective_auth_type != 'oauth2':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="oauth_config can only be set when auth_type is 'oauth2'"
                    )
                server.oauth_config_encrypted = _encrypt_oauth_config(request.oauth_config)

        if request.extra_config is not None:
            server.extra_config = request.extra_config
        if request.is_active is not None:
            server.is_active = request.is_active

        db_session.commit()
        db_session.refresh(server)

        LOGGER.info("[UserMCP] Updated server %s", safe_id(server.id))
        return _server_to_response(server)

    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        LOGGER.error("[UserMCP] Error updating server: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update server")


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_mcp_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Delete a user MCP server configuration. Blocked if any agents reference its tools."""
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        server = db_session.query(UserMcpServer).filter(
            UserMcpServer.id == server_id,
            UserMcpServer.owner_user_id == current_user.user_id
        ).first()
        if not server:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

        # Check for agent references
        referencing_agents = _check_agent_references(server, db_session)
        if referencing_agents:
            agent_names = ", ".join(referencing_agents[:5])
            detail = f"Cannot delete: server is referenced by agent(s): {agent_names}"
            if len(referencing_agents) > 5:
                detail += f" and {len(referencing_agents) - 5} more"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

        db_session.delete(server)
        db_session.commit()
        LOGGER.info("[UserMCP] Deleted server %s", safe_id(server.id))

    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        LOGGER.error("[UserMCP] Error deleting server: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete server")


@router.post("/{server_id}/test", response_model=TestConnectionResponse)
async def test_user_mcp_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> TestConnectionResponse:
    """Test connectivity to a user MCP server by listing its tools."""
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    server = db_session.query(UserMcpServer).filter(
        UserMcpServer.id == server_id,
        UserMcpServer.owner_user_id == current_user.user_id
    ).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    try:
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport, SSETransport

        # Build headers
        headers = {'User-Agent': 'Bond-AI-MCP-Client/1.0'}
        if server.auth_type == 'header' and server.headers_encrypted:
            decrypted = _decrypt_headers(server.headers_encrypted)
            if decrypted:
                headers.update(decrypted)

        # Create transport
        if server.transport == 'sse':
            transport = SSETransport(server.url, headers=headers)
        else:
            transport = StreamableHttpTransport(server.url, headers=headers)

        import asyncio
        async with Client(transport) as client:
            tools = await asyncio.wait_for(client.list_tools(), timeout=30)
            tool_names = [getattr(t, 'name', str(t)) for t in tools]

        return TestConnectionResponse(
            success=True,
            tool_count=len(tool_names),
            tools=tool_names[:50]  # Limit response size
        )

    except Exception as e:
        LOGGER.warning("[UserMCP] Test connection failed for server %s: %s", safe_id(server.id), e)
        return TestConnectionResponse(
            success=False,
            error=str(e)[:500]
        )


# =============================================================================
# Export endpoint
# =============================================================================

class ExportJsonResponse(BaseModel):
    """Export a server config as JSON."""
    server_name: str
    config: Dict[str, Any]


@router.get("/{server_id}/export", response_model=ExportJsonResponse)
async def export_user_mcp_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> ExportJsonResponse:
    """Export a user MCP server config as JSON (matching BOND_MCP_CONFIG format).

    Note: client_secret is included in the export so users can back up their config.
    """
    db_session = _get_db_session()
    if not db_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    server = db_session.query(UserMcpServer).filter(
        UserMcpServer.id == server_id,
        UserMcpServer.owner_user_id == current_user.user_id
    ).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    config: Dict[str, Any] = {
        "url": server.url,
        "transport": server.transport,
        "display_name": server.display_name,
    }
    if server.description:
        config["description"] = server.description
    if server.auth_type and server.auth_type != 'none':
        config["auth_type"] = server.auth_type

    # Include decrypted headers
    if server.headers_encrypted:
        try:
            config["headers"] = _decrypt_headers(server.headers_encrypted)
        except Exception as e:
            LOGGER.warning("Failed to decrypt headers for export of server %s: %s", safe_id(server.id), e)

    # Include decrypted OAuth config (with client_secret for backup)
    if server.oauth_config_encrypted:
        try:
            config["oauth_config"] = _decrypt_oauth_config(server.oauth_config_encrypted)
        except Exception as e:
            LOGGER.warning("Failed to decrypt oauth_config for export of server %s: %s", safe_id(server.id), e)

    # Include extra config fields at the top level
    if server.extra_config:
        for key, value in server.extra_config.items():
            if key not in config:
                config[key] = value

    return ExportJsonResponse(server_name=server.server_name, config=config)
