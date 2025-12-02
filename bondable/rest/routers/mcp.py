import logging
from typing import Annotated, List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, AnyUrl
from fastmcp import Client

from bondable.bond.mcp_client import MCPClient
from bondable.bond.config import Config
from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
from bondable.bond.providers.bedrock.BedrockMCP import _get_auth_headers_for_server as get_mcp_auth_headers, AuthorizationRequiredError, TokenExpiredError
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user

router = APIRouter(prefix="/mcp", tags=["MCP"])
LOGGER = logging.getLogger(__name__)


class MCPToolResponse(BaseModel):
    """Response model for MCP tool information."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPResourceResponse(BaseModel):
    """Response model for MCP resource information."""
    uri: AnyUrl
    name: Optional[str]
    description: Optional[str]
    mime_type: Optional[str]


# =============================================================================
# Grouped Response Models for Phase 2 UI
# =============================================================================

class ConnectionStatusInfo(BaseModel):
    """Connection status information for an MCP server."""
    connected: bool
    valid: bool = True
    requires_authorization: bool = False
    expires_at: Optional[str] = None


class MCPServerWithTools(BaseModel):
    """MCP server with its tools and connection status."""
    server_name: str
    display_name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    auth_type: str = "bond_jwt"
    connection_status: ConnectionStatusInfo
    tools: List[MCPToolResponse]
    tool_count: int


class MCPToolsGroupedResponse(BaseModel):
    """Grouped response containing all MCP servers with their tools."""
    servers: List[MCPServerWithTools]
    total_servers: int
    total_tools: int


@router.get("/tools")
async def list_mcp_tools(
    current_user: Annotated[User, Depends(get_current_user)],
    grouped: bool = Query(False, description="Return tools grouped by server with connection status")
) -> Union[List[MCPToolResponse], MCPToolsGroupedResponse]:
    """
    List all available MCP tools from configured servers.

    Args:
        grouped: If True, returns tools grouped by server with connection status.
                 If False (default), returns flat list for backward compatibility.

    Returns:
        List of available MCP tools with their schemas, or grouped response if grouped=True
    """
    from fastmcp.client.transports import SSETransport
    from fastmcp.client import StreamableHttpTransport

    LOGGER.info(f"[MCP Tools] Request received from user: {current_user.user_id} ({current_user.email}), grouped={grouped}")

    try:
        # Get MCP client and check if it's configured
        mcp_client = MCPClient.client()
        LOGGER.info(f"[MCP Tools] MCP client instance created: {mcp_client is not None}")

        if not hasattr(mcp_client, 'mcp_config') or mcp_client.mcp_config is None:
            LOGGER.warning("[MCP Tools] No MCP configuration found")
            if grouped:
                return MCPToolsGroupedResponse(servers=[], total_servers=0, total_tools=0)
            return []

        base_config = mcp_client.mcp_config
        servers = base_config.get("mcpServers", {})
        server_count = len(servers)
        LOGGER.info(f"[MCP Tools] MCP config found with {server_count} servers")

        if server_count == 0:
            LOGGER.warning("[MCP Tools] No MCP servers configured in config")
            if grouped:
                return MCPToolsGroupedResponse(servers=[], total_servers=0, total_tools=0)
            return []

        # Get token cache for checking connection status
        token_cache = get_mcp_token_cache()

        # Collect tools from all servers (grouped by server)
        all_tools = []
        server_tools_list: List[MCPServerWithTools] = []

        for server_name, server_config in servers.items():
            auth_type = server_config.get('auth_type', 'bond_jwt')
            display_name = server_config.get('display_name', server_name.replace('_', ' ').title())
            description = server_config.get('description')
            icon_url = server_config.get('icon_url')

            # Determine connection status
            connection_status = _get_connection_status_for_server(
                server_name, server_config, current_user.user_id, token_cache
            )

            server_tools: List[MCPToolResponse] = []

            try:
                # Get authentication headers (handles oauth2, bond_jwt, static)
                auth_headers = get_mcp_auth_headers(server_name, server_config, current_user)
                LOGGER.info(f"[MCP Tools] Server '{server_name}' authenticated, headers: {list(auth_headers.keys())}")

                # Get server URL and transport type
                server_url = server_config.get('url', '')
                transport_type = server_config.get('transport', 'sse')

                if not server_url:
                    LOGGER.warning(f"[MCP Tools] Server '{server_name}' has no URL configured")
                else:
                    # Create transport based on type
                    if transport_type in ('sse', 'streamable-http'):
                        # Add User-Agent header - some servers (like Atlassian MCP) require it
                        headers_with_ua = {
                            'User-Agent': 'Bond-AI-MCP-Client/1.0',
                            **auth_headers
                        }
                        LOGGER.info(f"[MCP Tools] Creating {transport_type} transport for '{server_name}' at {server_url}")

                        # Use correct transport class based on type
                        if transport_type == 'streamable-http':
                            transport = StreamableHttpTransport(server_url, headers=headers_with_ua)
                        else:
                            transport = SSETransport(server_url, headers=headers_with_ua)

                        try:
                            async with Client(transport) as client:
                                tools = await client.list_tools()
                                LOGGER.info(f"[MCP Tools] Server '{server_name}': {len(tools)} tools")
                                server_tools = [
                                    MCPToolResponse(
                                        name=getattr(tool, "name", ""),
                                        description=getattr(tool, "description", ""),
                                        input_schema=getattr(tool, "inputSchema", {})
                                    )
                                    for tool in tools
                                ]
                                all_tools.extend(server_tools)
                        except Exception as e:
                            LOGGER.warning(f"[MCP Tools] Error listing tools from '{server_name}': {e}")
                    else:
                        # For other transports, try the config approach
                        LOGGER.debug(f"[MCP Tools] Using config approach for '{server_name}' (transport: {transport_type})")
                        server_with_auth = server_config.copy()
                        existing_headers = server_with_auth.get('headers', {})
                        server_with_auth['headers'] = {**existing_headers, **auth_headers}

                        try:
                            async with Client({"mcpServers": {server_name: server_with_auth}}) as client:
                                tools = await client.list_tools()
                                LOGGER.debug(f"[MCP Tools] Server '{server_name}': {len(tools)} tools")
                                server_tools = [
                                    MCPToolResponse(
                                        name=getattr(tool, "name", ""),
                                        description=getattr(tool, "description", ""),
                                        input_schema=getattr(tool, "inputSchema", {})
                                    )
                                    for tool in tools
                                ]
                                all_tools.extend(server_tools)
                        except Exception as e:
                            LOGGER.warning(f"[MCP Tools] Error listing tools from '{server_name}': {e}")

            except AuthorizationRequiredError as e:
                LOGGER.info(f"[MCP Tools] Server '{server_name}' requires authorization: {e.message}")
                # Update connection status to reflect auth required
                connection_status = ConnectionStatusInfo(
                    connected=False,
                    valid=False,
                    requires_authorization=True,
                    expires_at=None
                )
            except TokenExpiredError as e:
                LOGGER.info(f"[MCP Tools] Server '{server_name}' token expired: {e.message}")
                # Update connection status to reflect expired token
                connection_status = ConnectionStatusInfo(
                    connected=True,
                    valid=False,
                    requires_authorization=True,
                    expires_at=None
                )
            except Exception as e:
                LOGGER.warning(f"[MCP Tools] Error getting auth for server '{server_name}': {e}")

            # Add server to grouped list (even if no tools, for status display)
            server_tools_list.append(MCPServerWithTools(
                server_name=server_name,
                display_name=display_name,
                description=description,
                icon_url=icon_url,
                auth_type=auth_type,
                connection_status=connection_status,
                tools=server_tools,
                tool_count=len(server_tools)
            ))

        LOGGER.info(f"[MCP Tools] Total tools collected: {len(all_tools)}")

        if grouped:
            response = MCPToolsGroupedResponse(
                servers=server_tools_list,
                total_servers=len(server_tools_list),
                total_tools=len(all_tools)
            )
            LOGGER.info(f"[MCP Tools] Returning grouped response with {response.total_servers} servers and {response.total_tools} tools")
            return response

        LOGGER.info(f"[MCP Tools] Successfully parsed {len(all_tools)} tools for user {current_user.user_id} ({current_user.email})")
        return all_tools

    except Exception as e:
        LOGGER.error(f"[MCP Tools] Unexpected error for user {current_user.user_id} ({current_user.email}): {type(e).__name__}: {e}", exc_info=True)
        if grouped:
            return MCPToolsGroupedResponse(servers=[], total_servers=0, total_tools=0)
        return []


def _get_connection_status_for_server(
    server_name: str,
    server_config: Dict[str, Any],
    user_id: str,
    token_cache
) -> ConnectionStatusInfo:
    """
    Get connection status for a specific MCP server.

    Args:
        server_name: Name of the server
        server_config: Server configuration
        user_id: User ID
        token_cache: Token cache instance

    Returns:
        ConnectionStatusInfo with current connection status
    """
    auth_type = server_config.get('auth_type', 'bond_jwt')

    # Non-OAuth servers are always connected
    if auth_type != 'oauth2':
        return ConnectionStatusInfo(
            connected=True,
            valid=True,
            requires_authorization=False,
            expires_at=None
        )

    # Check OAuth token status
    try:
        token_data = token_cache.get_token(user_id, server_name, auto_refresh=False)

        if token_data is None:
            return ConnectionStatusInfo(
                connected=False,
                valid=False,
                requires_authorization=True,
                expires_at=None
            )

        # Check if token is expired
        is_expired = token_data.is_expired()

        return ConnectionStatusInfo(
            connected=True,
            valid=not is_expired,
            requires_authorization=is_expired,
            expires_at=token_data.get_expires_at_iso()
        )
    except Exception as e:
        LOGGER.warning(f"[MCP Tools] Error checking token for {server_name}: {e}")
        return ConnectionStatusInfo(
            connected=False,
            valid=False,
            requires_authorization=True,
            expires_at=None
        )


@router.get("/resources", response_model=List[MCPResourceResponse])
async def list_mcp_resources(
    current_user: Annotated[User, Depends(get_current_user)]
) -> List[MCPResourceResponse]:
    """
    List all available MCP resources from configured servers.

    Returns:
        List of available MCP resources
    """
    LOGGER.debug(f"[MCP Resources] Request received from user: {current_user.user_id} ({current_user.email})")

    try:
        # Get MCP client and check if it's configured
        mcp_client = MCPClient.client()
        LOGGER.debug(f"[MCP Resources] MCP client instance created: {mcp_client is not None}")

        if not hasattr(mcp_client, 'mcp_config') or mcp_client.mcp_config is None:
            LOGGER.warning("[MCP Resources] No MCP configuration found")
            return []

        base_config = mcp_client.mcp_config
        servers = base_config.get("mcpServers", {})
        server_count = len(servers)
        LOGGER.debug(f"[MCP Resources] MCP config found with {server_count} servers")

        if server_count == 0:
            LOGGER.warning("[MCP Resources] No MCP servers configured in config")
            return []

        # Build config with user-specific OAuth headers for each server
        authenticated_servers = {}

        for server_name, server_config in servers.items():
            try:
                auth_headers = get_mcp_auth_headers(server_name, server_config, current_user)
                server_with_auth = server_config.copy()
                existing_headers = server_with_auth.get('headers', {})
                server_with_auth['headers'] = {**existing_headers, **auth_headers}
                authenticated_servers[server_name] = server_with_auth
            except (AuthorizationRequiredError, TokenExpiredError):
                pass  # Skip servers without valid auth
            except Exception as e:
                LOGGER.warning(f"[MCP Resources] Error getting auth for server '{server_name}': {e}")

        if not authenticated_servers:
            LOGGER.warning("[MCP Resources] No servers available after auth check")
            return []

        authenticated_config = {"mcpServers": authenticated_servers}

        try:
            LOGGER.debug(f"[MCP Resources] Creating client with {len(authenticated_servers)} authenticated servers...")
            async with Client(authenticated_config) as client:
                LOGGER.debug("[MCP Resources] Client connection established, listing resources...")
                resources = await client.list_resources()
                LOGGER.info(f"[MCP Resources] Raw resources response: {len(resources)} resources received")

                for i, resource in enumerate(resources):
                    LOGGER.debug(f"[MCP Resources] Resource {i+1}: uri='{getattr(resource, 'uri', 'NO_URI')}', name='{getattr(resource, 'name', 'NO_NAME')}'")

            parsed_resources = [
                MCPResourceResponse(
                    uri=getattr(resource, "uri", ""),
                    name=getattr(resource, "name", ""),
                    description=getattr(resource, "description", ""),
                    mime_type=getattr(resource, "mimeType", "")
                )
                for resource in resources
            ]

            LOGGER.debug(f"[MCP Resources] Successfully parsed {len(parsed_resources)} resources for user {current_user.user_id} ({current_user.email})")
            return parsed_resources

        except (RuntimeError, OSError, ConnectionError) as e:
            LOGGER.warning(f"[MCP Resources] Connection error: {type(e).__name__}: {e}")
            return []

    except Exception as e:
        LOGGER.error(f"[MCP Resources] Unexpected error for user {current_user.user_id} ({current_user.email}): {type(e).__name__}: {e}", exc_info=True)
        return []


@router.get("/status")
async def get_mcp_status(
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Get the status of the MCP client and configured servers.
    
    Returns:
        MCP client status information
    """
    LOGGER.debug(f"[MCP Status] Request received from user: {current_user.user_id} ({current_user.email})")
    
    try:
        mcp_client = MCPClient.client()
        LOGGER.debug(f"[MCP Status] MCP client instance created: {mcp_client is not None}")
        
        # Check if client has configuration
        if not hasattr(mcp_client, 'config') or mcp_client.config is None:
            LOGGER.warning("[MCP Status] MCP client has no config attribute")
            return {
                "servers_configured": 0,
                "client_initialized": False,
                "error": "MCP client config not found"
            }
        
        if not hasattr(mcp_client, 'mcp_config') or mcp_client.mcp_config is None:
            LOGGER.warning("[MCP Status] MCP client has no mcp_config attribute")
            return {
                "servers_configured": 0,
                "client_initialized": False,
                "error": "MCP configuration not loaded"
            }
        
        # Get the MCP configuration
        mcp_config = mcp_client.mcp_config
        servers = mcp_config.get("mcpServers", {})
        server_count = len(servers)
        
        LOGGER.debug(f"[MCP Status] Found {server_count} configured servers")
        
        # Log server details
        for server_name, server_config in servers.items():
            LOGGER.debug(f"[MCP Status] Server '{server_name}': {server_config}")
        
        # Check initialization status
        is_initialized = mcp_client._initialized
        LOGGER.debug(f"[MCP Status] Client initialized: {is_initialized}")
        
        status = {
            "servers_configured": server_count,
            "client_initialized": is_initialized,
            "server_details": list(servers.keys()) if servers else []
        }
        
        LOGGER.info(f"[MCP Status] Status response: {status}")
        return status
        
    except Exception as e:
        LOGGER.error(f"[MCP Status] Error checking status for user {current_user.user_id} ({current_user.email}): {type(e).__name__}: {e}", exc_info=True)
        return {
            "servers_configured": 0,
            "client_initialized": False,
            "error": "Failed to check MCP status"
        }


# =============================================================================
# MCP Connections Endpoint (OAuth handled by /connections/ router)
# =============================================================================
# NOTE: OAuth2 authentication for MCP servers is handled by the /connections/
# router in connections.py. The duplicate OAuth endpoints that were here have
# been removed to avoid confusion. Use:
#   - GET /connections/{name}/authorize - to initiate OAuth
#   - GET /connections/{name}/callback - OAuth callback
#   - GET /connections/{name}/status - check connection status
#   - DELETE /connections/{name} - disconnect
# =============================================================================

class MCPConnectionsResponse(BaseModel):
    """Response model for all user MCP connections."""
    connections: Dict[str, Dict[str, Any]]


@router.get("/connections", response_model=MCPConnectionsResponse)
async def get_user_mcp_connections(
    current_user: Annotated[User, Depends(get_current_user)]
) -> MCPConnectionsResponse:
    """
    Get all MCP server connections for the current user.

    Returns:
        Dictionary of server names to connection info
    """
    LOGGER.debug(f"[MCP Connections] Listing connections for user {current_user.email}")

    token_cache = get_mcp_token_cache()
    connections = token_cache.get_user_connections(current_user.user_id)

    # Also include configured OAuth servers that aren't connected
    config = Config.config()
    mcp_config = config.get_mcp_config()
    servers = mcp_config.get('mcpServers', {})

    for server_name, server_config in servers.items():
        auth_type = server_config.get('auth_type', 'bond_jwt')
        if auth_type == 'oauth2' and server_name not in connections:
            connections[server_name] = {
                "connected": False,
                "auth_type": auth_type,
                "requires_authorization": True
            }

    return MCPConnectionsResponse(connections=connections)