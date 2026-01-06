"""
MCP (Model Context Protocol) integration for Bedrock Provider.
Handles MCP tool definitions and execution for Bedrock agents using native action groups.

Authentication Types (auth_type in server config):
- "bond_jwt" (default): Use Bond's JWT token passed via Authorization header
- "oauth2": Use user-specific OAuth tokens from external providers (e.g., Atlassian)
- "static": Use static headers from config only (API keys, etc.)

For oauth2 auth_type, tokens are stored in the session-only MCPTokenCache.
Users must authorize external MCP servers each session.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport  # Use fastmcp's transport wrapper
from fastmcp.client.transports import SSETransport
import asyncio
from bondable.bond.config import Config
from bondable.bond.auth.mcp_token_cache import (
    get_mcp_token_cache,
    AuthorizationRequiredError,
    TokenExpiredError
)
from bondable.bond.auth.oauth_utils import safe_isoformat

LOGGER = logging.getLogger(__name__)

# Auth type constants
AUTH_TYPE_BOND_JWT = "bond_jwt"
AUTH_TYPE_OAUTH2 = "oauth2"
AUTH_TYPE_STATIC = "static"

# Token cache initialization no longer needed - it gets DB session automatically from Config


def _get_bedrock_agent_client() -> Any:
    from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
    bond_provider: BedrockProvider = Config.config().get_provider()
    return bond_provider.bedrock_agent_client

def create_mcp_action_groups(bedrock_agent_id: str, mcp_tools: List[str], mcp_resources: List[str], user_id: Optional[str] = None):
    """
    Create action groups for MCP tools.

    Args:
        bedrock_agent_id: The Bedrock agent ID
        mcp_tools: List of MCP tool names to create action groups for
        mcp_resources: List of MCP resource names (for future use)
        user_id: User ID for OAuth token lookup (required for oauth2 servers)
    """
    LOGGER.debug(f"[MCP Action Groups] Creating action groups for agent {bedrock_agent_id}, tools={mcp_tools}, user_id={user_id}")

    if not mcp_tools:
        LOGGER.debug("[MCP Action Groups] No MCP tools specified, skipping action group creation")
        return

    bedrock_agent_client = _get_bedrock_agent_client()

    try:
        # Get MCP config
        mcp_config = Config.config().get_mcp_config()

        if not mcp_config:
            LOGGER.error("[MCP Action Groups] MCP tools specified but no MCP config available")
            return

        # Get tool definitions from MCP (with OAuth support)
        LOGGER.debug(f"[MCP Action Groups] Fetching tool definitions for {len(mcp_tools)} tools with user_id={user_id}")
        mcp_tool_definitions = _get_mcp_tool_definitions_sync(mcp_config, mcp_tools, user_id=user_id)

        if not mcp_tool_definitions:
            LOGGER.warning("[MCP Action Groups] No MCP tool definitions found - action group will NOT be created")
            return

        LOGGER.debug(f"[MCP Action Groups] Got {len(mcp_tool_definitions)} tool definitions")

        # Build OpenAPI paths for MCP tools
        paths = {}
        for tool in mcp_tool_definitions:
            # Prefix with _bond_mcp_tool_
            tool_path = f"/_bond_mcp_tool_{tool['name']}"
            operation_id = f"_bond_mcp_tool_{tool['name']}"

            paths[tool_path] = {
                "post": {
                    "operationId": operation_id,
                    "summary": tool.get('description', f"MCP tool {tool['name']}"),
                    "description": tool.get('description', f"MCP tool {tool['name']}"),
                    "responses": {
                        "200": {
                            "description": "Tool execution result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "result": {
                                                "type": "string",
                                                "description": "Tool execution result"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            # Add parameters if any
            if tool.get('parameters'):
                paths[tool_path]["post"]["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": tool['parameters']
                            }
                        }
                    }
                }

        # Create action group
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "MCP Tools API",
                "version": "1.0.0",
                "description": "MCP tools for external integrations"
            },
            "paths": paths
        }

        # Log the OpenAPI spec for debugging
        LOGGER.info(f"[MCP Action Groups] Creating action group with {len(paths)} tools: {list(paths.keys())}")
        LOGGER.debug(f"[MCP Action Groups] OpenAPI spec: {json.dumps(openapi_spec, indent=2)}")

        action_group_spec = {
            "actionGroupName": "MCPTools",
            "description": "MCP (Model Context Protocol) tools for external integrations",
            "actionGroupExecutor": {
                "customControl": "RETURN_CONTROL"  # Return control to client for execution
            },
            "apiSchema": {
                "payload": json.dumps(openapi_spec)
            }
        }

        LOGGER.info(f"Creating MCP action group with {len(paths)} tools")
        action_response = bedrock_agent_client.create_agent_action_group(
            agentId=bedrock_agent_id,
            agentVersion="DRAFT",
            **action_group_spec
        )

        LOGGER.info(f"Created MCP action group: {action_response['agentActionGroup']['actionGroupId']}")

    except Exception as e:
        LOGGER.error(f"Error creating MCP action groups: {e}")
        # Continue without MCP tools rather than failing agent creation


async def _get_mcp_tool_definitions(mcp_config: Dict[str, Any], tool_names: List[str], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get tool definitions from MCP servers.

    Searches ALL configured MCP servers for the requested tools.

    Args:
        mcp_config: MCP configuration dict
        tool_names: List of tool names to get definitions for
        user_id: User ID for OAuth token lookup (required for oauth2 servers)

    Returns:
        List of tool definition dicts with name, description, and parameters
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        LOGGER.warning("[MCP Tool Defs] No MCP servers configured")
        return []

    LOGGER.debug(f"[MCP Tool Defs] Searching {len(servers)} servers for {len(tool_names)} tools: {tool_names}")

    # Create user context for OAuth lookup if user_id is provided
    current_user = None
    if user_id:
        class UserContext:
            def __init__(self, uid):
                self.user_id = uid
                self.email = 'unknown'
        current_user = UserContext(user_id)

    tool_definitions = []
    remaining_tools = set(tool_names)  # Track which tools we still need to find

    # Search each server for the requested tools
    for server_name, server_config in servers.items():
        if not remaining_tools:
            break  # Found all tools

        server_url = server_config.get('url')
        if not server_url:
            LOGGER.warning(f"[MCP Tool Defs] No URL configured for MCP server {server_name}")
            continue

        try:
            # Get authentication headers (handles oauth2, bond_jwt, static)
            try:
                headers = _get_auth_headers_for_server(server_name, server_config, current_user)
                headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'
                LOGGER.debug(f"[MCP Tool Defs] Server '{server_name}': authenticated successfully")
            except (AuthorizationRequiredError, TokenExpiredError) as e:
                LOGGER.warning(f"[MCP Tool Defs] Server '{server_name}': OAuth not available - {e}")
                # Fall back to static headers only
                headers = server_config.get('headers', {})
                headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'

            # Use appropriate transport based on config
            transport_type = server_config.get('transport', 'streamable-http')

            # Note: Don't override Accept/Content-Type headers for streamable-http
            # The MCP SDK sets these by default with lowercase keys

            if transport_type == 'sse':
                transport = SSETransport(server_url, headers=headers)
            else:
                transport = StreamableHttpTransport(server_url, headers=headers)

            async with Client(transport) as client:
                # Fetch all available tools from this server
                all_tools = await client.list_tools()
                tool_dict = {tool.name: tool for tool in all_tools}
                server_tool_names = list(tool_dict.keys())
                LOGGER.debug(f"[MCP Tool Defs] Server '{server_name}': {len(all_tools)} tools available")

                # Check which requested tools are on this server
                for tool_name in list(remaining_tools):
                    if tool_name in tool_dict:
                        tool = tool_dict[tool_name]
                        tool_def = {
                            'name': tool_name,
                            'description': tool.description or f"MCP tool {tool_name}"
                        }

                        # Add parameter schema if available
                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                            schema = tool.inputSchema
                            if 'properties' in schema:
                                # Copy properties
                                parameters = dict(schema['properties'])
                                tool_def['parameters'] = parameters
                        else:
                            tool_def['parameters'] = {}

                        tool_definitions.append(tool_def)
                        remaining_tools.remove(tool_name)
                        LOGGER.debug(f"[MCP Tool Defs] Found tool '{tool_name}' on server '{server_name}'")

        except Exception as e:
            LOGGER.error(f"[MCP Tool Defs] Error fetching tools from server '{server_name}': {e}")
            continue

    if remaining_tools:
        LOGGER.warning(f"[MCP Tool Defs] Tools not found on any server: {remaining_tools}")

    LOGGER.debug(f"[MCP Tool Defs] Total tool definitions found: {len(tool_definitions)}")
    return tool_definitions


def _get_mcp_tool_definitions_sync(mcp_config: Dict[str, Any], tool_names: List[str], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Synchronous wrapper for getting MCP tool definitions."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _get_mcp_tool_definitions(mcp_config, tool_names, user_id))
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(_get_mcp_tool_definitions(mcp_config, tool_names, user_id))


def _get_auth_headers_for_server(
    server_name: str,
    server_config: Dict[str, Any],
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None
) -> Dict[str, str]:
    """
    Get authentication headers for an MCP server based on its auth_type.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict
        current_user: User object with authentication context
        jwt_token: Bond JWT token for bond_jwt auth type

    Returns:
        Headers dict with appropriate Authorization header

    Raises:
        AuthorizationRequiredError: If oauth2 auth is required but user hasn't authorized
        TokenExpiredError: If oauth2 token exists but is expired
    """
    # Start with any static headers from config
    headers = server_config.get('headers', {}).copy()

    # Get auth type (default to bond_jwt for backwards compatibility)
    auth_type = server_config.get('auth_type', AUTH_TYPE_BOND_JWT)

    user_id = getattr(current_user, 'user_id', None) if current_user else None
    user_email = getattr(current_user, 'email', 'unknown') if current_user else 'unknown'

    if auth_type == AUTH_TYPE_OAUTH2:
        # OAuth2: Use user-specific token from cache (backed by database)
        if not user_id:
            raise AuthorizationRequiredError(
                server_name,
                f"User authentication required to access MCP server '{server_name}'"
            )

        token_cache = get_mcp_token_cache()

        # First check if token exists (including expired tokens for better error message)
        user_connections = token_cache.get_user_connections(user_id)
        connection_info = user_connections.get(server_name)

        if connection_info is None:
            LOGGER.debug(f"[MCP Auth] No OAuth token found for user={user_email}, server={server_name}")
            raise AuthorizationRequiredError(
                server_name,
                f"Please authorize access to '{server_name}' before using its tools"
            )

        # Check if token is expired (connection exists but not valid)
        LOGGER.debug(f"[MCP Auth] Connection info for {server_name}: connected={connection_info.get('connected')}, valid={connection_info.get('valid')}, expires_at={connection_info.get('expires_at')}")
        if connection_info.get('connected') and not connection_info.get('valid'):
            LOGGER.debug(f"[MCP Auth] OAuth token expired for user={user_email}, server={server_name}")
            expires_at = connection_info.get('expires_at')
            raise TokenExpiredError(server_name, expires_at)

        # Get the actual token (will return None if expired due to 5-min buffer)
        token_data = token_cache.get_token(user_id, server_name)

        if token_data is None:
            LOGGER.debug(f"No valid OAuth token for user={user_email}, server={server_name}")
            raise AuthorizationRequiredError(
                server_name,
                f"Please authorize access to '{server_name}' before using its tools"
            )

        # Use "Bearer" (capitalized) as per RFC 6750 - some servers (like Atlassian) require this
        headers['Authorization'] = f'Bearer {token_data.access_token}'

        # TODO: Make cloud_id header configurable via oauth_config.cloud_id_header_name
        # to support different MCP servers that may use different header names
        # For now, hardcode X-Atlassian-Cloud-Id for Atlassian MCP compatibility
        cloud_id = server_config.get('cloud_id')
        if cloud_id:
            headers['X-Atlassian-Cloud-Id'] = cloud_id
            LOGGER.debug(f"[MCP Auth] Added X-Atlassian-Cloud-Id header: {cloud_id}")
        else:
            LOGGER.warning(f"[MCP Auth] No cloud_id found in config for OAuth2 server '{server_name}'. Some MCP servers (like Atlassian) may require this.")

        LOGGER.debug(f"Using OAuth2 token for MCP server {server_name} (user: {user_email})")

    elif auth_type == AUTH_TYPE_BOND_JWT:
        # Bond JWT: Use the passed JWT token
        if jwt_token:
            headers['Authorization'] = f'Bearer {jwt_token}'
            LOGGER.debug(f"Using Bond JWT for MCP server {server_name} (user: {user_email})")
        else:
            LOGGER.debug(f"No JWT token provided for bond_jwt auth on server {server_name}")

    elif auth_type == AUTH_TYPE_STATIC:
        # Static: Only use headers from config (already set above)
        LOGGER.debug(f"Using static headers for MCP server {server_name}")

    else:
        LOGGER.warning(f"Unknown auth_type '{auth_type}' for server {server_name}, using static headers")

    return headers


async def execute_mcp_tool(
    mcp_config: Dict[str, Any],
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute an MCP tool call with authentication.

    Searches ALL configured MCP servers to find which one has the requested tool.

    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        current_user: User object with authentication context
        jwt_token: Raw JWT token for authentication (used for bond_jwt auth_type)

    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields

    Note:
        For oauth2 auth_type servers, the user must have authorized the server
        via the /mcp/{server}/connect endpoint first. If not authorized,
        this will return an error with authorization_required flag.
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        return {"success": False, "error": "No MCP servers configured"}

    LOGGER.debug(f"[MCP Execute] Searching {len(servers)} servers for tool '{tool_name}'")

    # Search each server for the tool
    for server_name, server_config in servers.items():
        server_url = server_config.get('url')
        if not server_url:
            LOGGER.warning(f"[MCP Execute] No URL configured for MCP server {server_name}")
            continue

        try:
            # Get authentication headers based on auth_type
            headers = _get_auth_headers_for_server(
                server_name=server_name,
                server_config=server_config,
                current_user=current_user,
                jwt_token=jwt_token
            )
            headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'

            # Use appropriate transport based on config
            transport_type = server_config.get('transport', 'streamable-http')

            # Note: Don't override Accept/Content-Type headers for streamable-http
            # The MCP SDK sets these by default with lowercase keys

            if transport_type == 'sse':
                transport = SSETransport(server_url, headers=headers)
            else:
                transport = StreamableHttpTransport(server_url, headers=headers)

            async with Client(transport) as client:
                # Check if this server has the tool
                all_tools = await client.list_tools()
                tool_names_on_server = [t.name for t in all_tools]

                if tool_name not in tool_names_on_server:
                    LOGGER.debug(f"[MCP Execute] Tool '{tool_name}' not found on server '{server_name}'")
                    continue

                LOGGER.debug(f"[MCP Execute] Found tool '{tool_name}' on server '{server_name}'")

                # Prepare parameters
                tool_parameters = parameters.copy() if parameters else {}

                LOGGER.debug(f"[MCP Execute] Executing tool '{tool_name}' with parameters: {list(tool_parameters.keys())}")
                result = await client.call_tool(tool_name, tool_parameters)

                # Handle different result types (inside the async with block)
                if hasattr(result, 'content') and isinstance(result.content, list):
                    # Extract text from content list
                    text_parts = []
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            text_parts.append(content_item.text)
                        elif hasattr(content_item, 'type') and content_item.type == 'text':
                            text_parts.append(str(content_item))
                    return {"success": True, "result": " ".join(text_parts)}
                elif hasattr(result, 'text'):
                    return {"success": True, "result": result.text}
                else:
                    # Fallback to string representation
                    return {"success": True, "result": str(result)}

        except AuthorizationRequiredError as e:
            LOGGER.debug(f"[MCP Execute] Authorization required for server '{server_name}': {e.server_name}")
            return {
                "success": False,
                "error": e.message,
                "authorization_required": True,
                "server_name": e.server_name
            }
        except TokenExpiredError as e:
            LOGGER.debug(f"[MCP Execute] Token expired for server '{server_name}': {e.connection_name}")
            return {
                "success": False,
                "error": e.message,
                "token_expired": True,
                "connection_name": e.connection_name,
                "expired_at": safe_isoformat(e.expired_at)
            }
        except Exception as e:
            # Log full exception details including traceback for debugging
            LOGGER.exception(f"[MCP Execute] Error on server '{server_name}' when executing tool '{tool_name}' with parameters {list(parameters.keys()) if parameters else []}: {e}")
            continue  # Try next server

    # Tool not found on any server
    LOGGER.error(f"[MCP Execute] Tool '{tool_name}' not found on any configured MCP server")
    return {"success": False, "error": f"Tool '{tool_name}' not found on any configured MCP server"}


def execute_mcp_tool_sync(
    mcp_config: Dict[str, Any],
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for executing MCP tool with authentication.

    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        current_user: User object with authentication context
        jwt_token: Raw JWT token for authentication

    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                execute_mcp_tool(mcp_config, tool_name, parameters, current_user, jwt_token)
            )
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(execute_mcp_tool(mcp_config, tool_name, parameters, current_user, jwt_token))
