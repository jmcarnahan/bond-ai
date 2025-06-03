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
    
    # Synchronous wrapper methods for easy use from non-async code
    
    def _run_async(self, coro):
        """Run an async coroutine from sync code."""
        import concurrent.futures
        
        # Use ThreadPoolExecutor to run in separate thread with its own event loop
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    
    def list_tools_sync(self) -> list:
        """
        Synchronous method to list all available MCP tools.
        
        Returns:
            List of available tools
        """
        LOGGER.info("Fetching available MCP tools from server")
        try:
            async def _list_tools():
                async with await self.get_client() as client:
                    tools = await client.list_tools()
                    LOGGER.info(f"MCP server returned {len(tools)} tools")
                    return tools
            
            result = self._run_async(_list_tools())
            LOGGER.info(f"Successfully retrieved {len(result)} MCP tools")
            return result
        except Exception as e:
            LOGGER.error(f"Error listing MCP tools: {e}", exc_info=True)
            return []
    
    def list_resources_sync(self) -> list:
        """
        Synchronous method to list all available MCP resources.
        
        Returns:
            List of available resources
        """
        LOGGER.info("Fetching available MCP resources from server")
        try:
            async def _list_resources():
                async with await self.get_client() as client:
                    resources = await client.list_resources()
                    LOGGER.info(f"MCP server returned {len(resources)} resources")
                    return resources
            
            result = self._run_async(_list_resources())
            LOGGER.info(f"Successfully retrieved {len(result)} MCP resources")
            return result
        except Exception as e:
            LOGGER.error(f"Error listing MCP resources: {e}", exc_info=True)
            return []
    
    def call_tool_sync(self, tool_name: str, arguments: dict = None) -> str:
        """
        Synchronous method to call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            String result from the tool
        """
        try:
            async def _call_tool():
                async with await self.get_client() as client:
                    result = await client.call_tool(tool_name, arguments or {})
                    if result and len(result) > 0:
                        return getattr(result[0], "text", str(result[0]))
                    return f"No result returned from tool '{tool_name}'"
            
            return self._run_async(_call_tool())
        except Exception as e:
            LOGGER.error(f"Error calling MCP tool '{tool_name}': {e}", exc_info=True)
            return f"Error calling tool: {str(e)}"
    
    def read_resource_sync(self, resource_uri: str) -> str:
        """
        Synchronous method to read an MCP resource.
        
        Args:
            resource_uri: URI of the resource to read
            
        Returns:
            String content of the resource
        """
        try:
            async def _read_resource():
                async with await self.get_client() as client:
                    content = await client.read_resource(resource_uri)
                    if content and len(content) > 0:
                        return getattr(content[0], "text", str(content[0]))
                    return f"No content returned from resource"
            
            return self._run_async(_read_resource())
        except Exception as e:
            LOGGER.error(f"Error reading MCP resource '{resource_uri}': {e}", exc_info=True)
            return f"Error reading resource: {str(e)}"


