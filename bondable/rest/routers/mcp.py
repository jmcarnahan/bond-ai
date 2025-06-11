import logging
from typing import Annotated, List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, AnyUrl

from bondable.bond.mcp_client import MCPClient
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


@router.get("/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    current_user: Annotated[User, Depends(get_current_user)]
) -> List[MCPToolResponse]:
    """
    List all available MCP tools from configured servers.
    
    Returns:
        List of available MCP tools with their schemas
    """
    LOGGER.debug(f"[MCP Tools] Request received from user: {current_user.user_id} ({current_user.email})")
    
    try:
        # Get MCP client and check if it's configured
        mcp_client = MCPClient.client()
        LOGGER.debug(f"[MCP Tools] MCP client instance created: {mcp_client is not None}")
        
        if not hasattr(mcp_client, 'mcp_config') or mcp_client.mcp_config is None:
            LOGGER.warning("[MCP Tools] No MCP configuration found")
            return []
        
        server_count = len(mcp_client.mcp_config.get("mcpServers", {}))
        LOGGER.debug(f"[MCP Tools] MCP config found with {server_count} servers")
        
        if server_count == 0:
            LOGGER.warning("[MCP Tools] No MCP servers configured in config")
            return []
        
        try:
            LOGGER.debug("[MCP Tools] Attempting to get client connection...")
            async with await mcp_client.get_client() as client:
                LOGGER.debug("[MCP Tools] Client connection established, listing tools...")
                tools = await client.list_tools()
                LOGGER.info(f"[MCP Tools] Raw tools response: {len(tools)} tools received")
                
                # Log details about each tool
                for i, tool in enumerate(tools):
                    LOGGER.debug(f"[MCP Tools] Tool {i+1}: name='{getattr(tool, 'name', 'NO_NAME')}', description='{getattr(tool, 'description', 'NO_DESC')[:50]}...'")
            
            parsed_tools = [
                MCPToolResponse(
                    name=getattr(tool, "name", ""),
                    description=getattr(tool, "description", ""),
                    input_schema=getattr(tool, "inputSchema", {})
                )
                for tool in tools
            ]
            
            LOGGER.debug(f"[MCP Tools] Successfully parsed {len(parsed_tools)} tools for user {current_user.user_id} ({current_user.email})")
            return parsed_tools
            
        except (RuntimeError, OSError, ConnectionError) as e:
            LOGGER.warning(f"[MCP Tools] Connection error: {type(e).__name__}: {e}")
            return []
            
    except Exception as e:
        LOGGER.error(f"[MCP Tools] Unexpected error for user {current_user.user_id} ({current_user.email}): {type(e).__name__}: {e}", exc_info=True)
        # Return empty list instead of error to allow graceful degradation
        return []


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
        
        server_count = len(mcp_client.mcp_config.get("mcpServers", {}))
        LOGGER.debug(f"[MCP Resources] MCP config found with {server_count} servers")
        
        if server_count == 0:
            LOGGER.warning("[MCP Resources] No MCP servers configured in config")
            return []
        
        try:
            LOGGER.debug("[MCP Resources] Attempting to get client connection...")
            async with await mcp_client.get_client() as client:
                LOGGER.debug("[MCP Resources] Client connection established, listing resources...")
                resources = await client.list_resources()
                LOGGER.info(f"[MCP Resources] Raw resources response: {len(resources)} resources received")
                
                # Log details about each resource
                for i, resource in enumerate(resources):
                    LOGGER.debug(f"[MCP Resources] Resource {i+1}: uri='{getattr(resource, 'uri', 'NO_URI')}', name='{getattr(resource, 'name', 'NO_NAME')}', mime_type='{getattr(resource, 'mimeType', 'NO_MIME')}'")
            
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
        # Return empty list instead of error to allow graceful degradation
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
            "error": str(e)
        }