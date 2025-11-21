"""
MCP (Model Context Protocol) integration for Bedrock Provider.
Handles MCP tool definitions and execution for Bedrock agents using native action groups.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
import asyncio
from bondable.bond.config import Config

LOGGER = logging.getLogger(__name__)

def _get_bedrock_agent_client() -> Any:
    from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
    bond_provider: BedrockProvider = Config.config().get_provider()
    return bond_provider.bedrock_agent_client

def create_mcp_action_groups(bedrock_agent_id: str, mcp_tools: List[str], mcp_resources: List[str]):
    """
    Create action groups for MCP tools.
    
    Args:
        bedrock_agent_id: The Bedrock agent ID
        mcp_tools: List of MCP tool names to create action groups for
        mcp_resources: List of MCP resource names (for future use)
    """
    if not mcp_tools:
        return
        
    bedrock_agent_client = _get_bedrock_agent_client()

    try:
        # Get MCP config
        mcp_config = Config.config().get_mcp_config()
        
        if not mcp_config:
            LOGGER.error("MCP tools specified but no MCP config available")
            return
        
        # Get tool definitions from MCP
        mcp_tool_definitions = _get_mcp_tool_definitions_sync(mcp_config, mcp_tools)
        
        if not mcp_tool_definitions:
            LOGGER.warning("No MCP tool definitions found")
            return
        
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
        action_group_spec = {
            "actionGroupName": "MCPTools",
            "description": "MCP (Model Context Protocol) tools for external integrations",
            "actionGroupExecutor": {
                "customControl": "RETURN_CONTROL"  # Return control to client for execution
            },
            "apiSchema": {
                "payload": json.dumps({
                    "openapi": "3.0.0",
                    "info": {
                        "title": "MCP Tools API",
                        "version": "1.0.0",
                        "description": "MCP tools for external integrations"
                    },
                    "paths": paths
                })
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


async def _get_mcp_tool_definitions(mcp_config: Dict[str, Any], tool_names: List[str]) -> List[Dict[str, Any]]:
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
    server_config = servers[server_name]
    server_url = server_config.get('url')

    if not server_url:
        LOGGER.warning(f"No URL configured for MCP server {server_name}")
        return []

    tool_definitions = []

    try:
        # Use headers from config if available (e.g., for Atlassian MCP with API token)
        headers = server_config.get('headers', {})
        transport = StreamableHttpTransport(server_url, headers=headers)

        async with Client(transport) as client:
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


def _get_mcp_tool_definitions_sync(mcp_config: Dict[str, Any], tool_names: List[str]) -> List[Dict[str, Any]]:
    """Synchronous wrapper for getting MCP tool definitions."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _get_mcp_tool_definitions(mcp_config, tool_names))
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(_get_mcp_tool_definitions(mcp_config, tool_names))


async def execute_mcp_tool(
    mcp_config: Dict[str, Any],
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute an MCP tool call with authentication.

    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        current_user: User object with authentication context
        jwt_token: Raw JWT token for authentication

    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        return {"success": False, "error": "No MCP servers configured"}

    # For now, use the first server
    server_name = list(servers.keys())[0]
    server_config = servers[server_name]
    server_url = server_config.get('url')

    if not server_url:
        return {"success": False, "error": f"No URL configured for MCP server {server_name}"}

    # Prepare parameters (no auth info in parameters - use headers instead)
    tool_parameters = parameters.copy() if parameters else {}

    try:
        # Start with headers from config (e.g., Atlassian API token)
        headers = server_config.get('headers', {}).copy()

        # Add JWT Bearer token if available (for user authentication)
        # Note: This will override any Authorization header from config
        if jwt_token:
            headers['Authorization'] = f'Bearer {jwt_token}'
            user_email = getattr(current_user, 'email', 'unknown') if current_user else 'unknown'
            LOGGER.info(f"Adding JWT Bearer token to MCP tool call for {tool_name} (user: {user_email})")

        # Use StreamableHttpTransport with headers (standard approach)
        transport = StreamableHttpTransport(server_url, headers=headers)
        async with Client(transport) as client:
            LOGGER.info(f"Executing MCP tool: {tool_name} with parameters: {list(tool_parameters.keys())}")
            result = await client.call_tool(tool_name, tool_parameters)

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