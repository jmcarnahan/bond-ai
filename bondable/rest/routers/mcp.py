import logging
from typing import Annotated, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bondable.bond.mcp_client import MCPClient
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user

router = APIRouter(prefix="/mcp", tags=["MCP"])
logger = logging.getLogger(__name__)


class MCPToolResponse(BaseModel):
    """Response model for MCP tool information."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPResourceResponse(BaseModel):
    """Response model for MCP resource information."""
    uri: str
    name: str
    description: str
    mime_type: str


@router.get("/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    current_user: Annotated[User, Depends(get_current_user)]
) -> List[MCPToolResponse]:
    """
    List all available MCP tools from configured servers.
    
    Returns:
        List of available MCP tools with their schemas
    """
    try:
        async with await MCPClient.get_client() as client:
            tools = await client.list_tools()
        
        return [
            MCPToolResponse(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {})
            )
            for tool in tools
        ]
    except Exception as e:
        logger.error(f"Failed to list MCP tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP tools: {str(e)}"
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
    try:
        async with await MCPClient.get_client() as client:
            resources = await client.list_resources()
        
        return [
            MCPResourceResponse(
                uri=resource.get("uri", ""),
                name=resource.get("name", ""),
                description=resource.get("description", ""),
                mime_type=resource.get("mimeType", "")
            )
            for resource in resources
        ]
    except Exception as e:
        logger.error(f"Failed to list MCP resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP resources: {str(e)}"
        )


@router.get("/status")
async def get_mcp_status(
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Get the status of the MCP client and configured servers.
    
    Returns:
        MCP client status information
    """
    try:
        mcp_client = MCPClient.client()
        mcp_config = mcp_client.config.get_mcp_config()
        
        return {
            "servers_configured": len(mcp_config.get("mcpServers", {})),
            "client_initialized": mcp_client.client is not None
        }
    except Exception as e:
        logger.error(f"Failed to get MCP status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP status: {str(e)}"
        )