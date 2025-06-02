import logging
import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager
from fastmcp import Client
from bondable.bond.config import Config
from bondable.bond.cache import bond_cache

LOGGER = logging.getLogger(__name__)


class MCPClient:
    """
    MCP (Model Context Protocol) client pool for Bond SDK.
    
    This class provides a connection pool of fastmcp clients
    to handle concurrent requests safely.
    """
    
    def __init__(self, pool_size: int = 5):
        """Initialize the MCP client pool with configuration."""
        self.config = None
        self.mcp_config = None
        self.pool_size = pool_size
        self._clients: List[Client] = []
        self._available: Optional[asyncio.Queue] = None
        self._initialized = False
        
        try:
            self.config = Config.config()
            self.mcp_config = self.config.get_mcp_config()
            
            if not self.mcp_config.get("mcpServers"):
                LOGGER.warning("No MCP servers configured")
                return
            
            server_count = len(self.mcp_config["mcpServers"])
            LOGGER.info(f"MCP client configured with {server_count} servers, pool size: {pool_size}")
                
        except Exception as e:
            LOGGER.warning(f"Failed to configure MCP client: {e}")
            # Don't raise - allow graceful degradation
    
    async def _initialize_pool(self):
        """Initialize the connection pool."""
        if self._initialized or self.mcp_config is None:
            return
            
        try:
            self._available = asyncio.Queue()
            
            for i in range(self.pool_size):
                client = Client(self.mcp_config)
                self._clients.append(client)
                await self._available.put(client)
                LOGGER.debug(f"Created MCP client {i+1}/{self.pool_size}")
            
            self._initialized = True
            LOGGER.info(f"Initialized MCP client pool with {self.pool_size} clients")
            
        except Exception as e:
            LOGGER.error(f"Failed to initialize MCP client pool: {e}")
            self._initialized = False
    
    @classmethod
    @bond_cache
    def client(cls) -> "MCPClient":
        return cls()
    
    @asynccontextmanager
    async def get_pooled_client(self):
        """
        Get a client from the pool for async operations.
        
        Usage:
            mcp_client = MCPClient.client()
            async with mcp_client.get_pooled_client() as client:
                tools = await client.list_tools()
        """
        if not self._initialized:
            await self._initialize_pool()
        
        if not self._initialized or self._available is None:
            raise Exception("MCP client pool not initialized - no servers configured or initialization failed")
        
        # Get a client from the pool
        client = await self._available.get()
        try:
            # Use the client's own async context manager to ensure proper connection
            async with client:
                yield client
        finally:
            # Return client to pool
            await self._available.put(client)
    
    async def get_client(self):
        """
        Get a client from the pool for async operations.
        
        Usage:
            mcp_client = MCPClient.client()
            async with await mcp_client.get_client() as client:
                tools = await client.list_tools()
        """
        return self.get_pooled_client()


