"""
MCP (Model Context Protocol) integration for Bedrock Provider.
Handles MCP tool definitions and execution for Bedrock agents using native action groups.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastmcp import Client
import asyncio

LOGGER = logging.getLogger(__name__)


async def get_mcp_tool_definitions(mcp_config: Dict[str, Any], tool_names: List[str]) -> List[Dict[str, Any]]:
    """
    Get tool definitions from MCP server.
    
    Args:
        mcp_config: MCP configuration dict
        tool_names: List of tool names to get definitions for
        
    Returns:
        List of tool definition dicts with name, description, and parameters
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        LOGGER.warning("No MCP servers configured")
        return []
    
    # For now, use the first server
    server_name = list(servers.keys())[0]
    server_url = servers[server_name].get('url')
    
    if not server_url:
        LOGGER.warning(f"No URL configured for MCP server {server_name}")
        return []
    
    tool_definitions = []
    
    try:
        async with Client(server_url) as client:
            # Fetch all available tools
            all_tools = await client.list_tools()
            tool_dict = {tool.name: tool for tool in all_tools}
            
            for tool_name in tool_names:
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
                            tool_def['parameters'] = schema['properties']
                    else:
                        tool_def['parameters'] = {}
                    
                    tool_definitions.append(tool_def)
                else:
                    LOGGER.warning(f"MCP tool '{tool_name}' not found on server")
    
    except Exception as e:
        LOGGER.error(f"Error getting MCP tool definitions: {e}")
    
    return tool_definitions


def get_mcp_tool_definitions_sync(mcp_config: Dict[str, Any], tool_names: List[str]) -> List[Dict[str, Any]]:
    """Synchronous wrapper for getting MCP tool definitions."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, get_mcp_tool_definitions(mcp_config, tool_names))
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(get_mcp_tool_definitions(mcp_config, tool_names))


async def execute_mcp_tool(mcp_config: Dict[str, Any], tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute an MCP tool call.
    
    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        
    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        return {"success": False, "error": "No MCP servers configured"}
    
    # For now, use the first server
    server_name = list(servers.keys())[0]
    server_url = servers[server_name].get('url')
    
    if not server_url:
        return {"success": False, "error": f"No URL configured for MCP server {server_name}"}
    
    try:
        async with Client(server_url) as client:
            LOGGER.info(f"Executing MCP tool: {tool_name} with parameters: {parameters}")
            result = await client.call_tool(tool_name, parameters or {})
            
            # Handle different result types
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
    
    except Exception as e:
        LOGGER.error(f"Error executing MCP tool: {e}")
        return {"success": False, "error": str(e)}


def execute_mcp_tool_sync(mcp_config: Dict[str, Any], tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Synchronous wrapper for executing MCP tool."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, execute_mcp_tool(mcp_config, tool_name, parameters))
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(execute_mcp_tool(mcp_config, tool_name, parameters))