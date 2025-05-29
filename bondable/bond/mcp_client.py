import logging
from typing import Optional
from contextlib import asynccontextmanager
from fastmcp import Client
from bondable.bond.config import Config
from bondable.bond.cache import bond_cache

LOGGER = logging.getLogger(__name__)


class MCPClient:
    """
    MCP (Model Context Protocol) client for Bond SDK.
    
    This class provides a thin wrapper around the fastmcp Client
    and gives direct access to the underlying client object.
    """
    
    def __init__(self):
        """Initialize the MCP client with configuration."""
        try:
            mcp_config = Config.config().get_mcp_config()
            if not mcp_config.get("mcpServers"):
                LOGGER.warning("No MCP servers configured")
                return
            
            self.client = Client(mcp_config)
            server_count = len(mcp_config["mcpServers"])
            LOGGER.info(f"Initialized MCP client with {server_count} servers")
                
        except Exception as e:
            LOGGER.error(f"Failed to initialize MCP client: {e}")
            raise
    
    @classmethod
    @bond_cache
    def client(cls) -> "MCPClient":
        return cls()
    
    @classmethod
    async def get_client(cls):
        """
        Get the fastmcp client instance for async operations.
        
        Usage:
            async with await MCPClient.get_client() as client:
                tools = await client.list_tools()
        """
        instance = cls.client()
        return instance.client


