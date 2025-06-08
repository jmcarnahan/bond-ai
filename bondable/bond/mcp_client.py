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
    
    def __init__(self):
        """Initialize the MCP client with configuration."""
        LOGGER.debug("[MCPClient] Initializing MCP client (fresh client strategy)")
        
        self.config = None
        self.mcp_config = None
        
        # Circuit breaker state
        self._failure_count = 0
        self._last_failure_time = None
        self._circuit_breaker_timeout = 60  # seconds
        self._max_failures = 5
        
        try:
            LOGGER.debug("[MCPClient] Loading configuration...")
            self.config = Config.config()
            LOGGER.debug(f"[MCPClient] Config loaded: {self.config is not None}")
            
            self.mcp_config = self.config.get_mcp_config()
            LOGGER.debug(f"[MCPClient] MCP config loaded: {self.mcp_config is not None}")
            
            if not self.mcp_config:
                LOGGER.warning("[MCPClient] MCP config is None or empty")
                return
                
            if not self.mcp_config.get("mcpServers"):
                LOGGER.warning("[MCPClient] No MCP servers configured in config")
                LOGGER.info(f"[MCPClient] Full MCP config: {self.mcp_config}")
                return
            
            server_count = len(self.mcp_config["mcpServers"])
            LOGGER.info(f"[MCPClient] MCP client configured with {server_count} servers")
            
            # Log server details
            for server_name, server_config in self.mcp_config["mcpServers"].items():
                LOGGER.info(f"[MCPClient] Server '{server_name}': {server_config}")
                
        except Exception as e:
            LOGGER.error(f"[MCPClient] Failed to configure MCP client: {type(e).__name__}: {e}", exc_info=True)
            # Don't raise - allow graceful degradation
    
    
    @classmethod
    @bond_cache
    def client(cls) -> "MCPClient":
        return cls()
    
    def _is_circuit_breaker_open(self):
        """Check if circuit breaker should prevent requests."""
        if self._failure_count < self._max_failures:
            return False
            
        if self._last_failure_time is None:
            return False
            
        import time
        time_since_failure = time.time() - self._last_failure_time
        if time_since_failure > self._circuit_breaker_timeout:
            LOGGER.warning(f"[MCPClient] Circuit breaker timeout expired, resetting failure count")
            self._failure_count = 0
            self._last_failure_time = None
            return False
            
        LOGGER.warning(f"[MCPClient] Circuit breaker OPEN - {self._failure_count} failures, {time_since_failure:.1f}s ago")
        return True
    
    def _record_success(self):
        """Record a successful operation."""
        if self._failure_count > 0:
            LOGGER.debug(f"[MCPClient] Success recorded, resetting failure count from {self._failure_count}")
            self._failure_count = 0
            self._last_failure_time = None
    
    def _record_failure(self):
        """Record a failed operation."""
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()
        LOGGER.warning(f"[MCPClient] Failure recorded, count now: {self._failure_count}/{self._max_failures}")

    @asynccontextmanager
    async def get_pooled_client(self):
        """
        Get a fresh client for async operations with retry logic and circuit breaker.
        
        Note: Due to MCP session issues, we create fresh clients and retry on failures.
        
        Usage:
            mcp_client = MCPClient.client()
            async with mcp_client.get_pooled_client() as client:
                tools = await client.list_tools()
        """
        LOGGER.debug(f"[MCPClient] get_pooled_client called. Config available: {self.mcp_config is not None}")
        
        if self.mcp_config is None:
            error_msg = "MCP client config not available - no servers configured"
            LOGGER.error(f"[MCPClient] {error_msg}")
            raise Exception(error_msg)
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            error_msg = f"MCP circuit breaker is OPEN - too many recent failures ({self._failure_count})"
            LOGGER.warning(f"[MCPClient] {error_msg}")
            raise Exception(error_msg)
        
        max_retries = 3
        retry_delay = 1.0  # seconds
        
        for attempt in range(max_retries):
            LOGGER.debug(f"[MCPClient] Attempt {attempt + 1}/{max_retries}: Creating fresh client...")
            
            # Create a fresh client for this request
            client = Client(self.mcp_config)
            LOGGER.debug(f"[MCPClient] Fresh client created: {client is not None}")
            
            try:
                LOGGER.debug(f"[MCPClient] Attempt {attempt + 1}: Entering client context manager...")
                # Use the client's own async context manager to ensure proper connection
                async with client:
                    LOGGER.info(f"[MCPClient] Attempt {attempt + 1}: Client context established, yielding client")
                    yield client
                    # Record success and exit
                    self._record_success()
                    return
                    
            except Exception as e:
                LOGGER.error(f"[MCPClient] Attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                
                if attempt < max_retries - 1:
                    LOGGER.warning(f"[MCPClient] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    LOGGER.error(f"[MCPClient] All {max_retries} attempts failed, giving up")
                    self._record_failure()
                    raise
            finally:
                LOGGER.debug(f"[MCPClient] Attempt {attempt + 1}: Client context completed")
    
    async def get_client(self):
        """
        Get a fresh client for async operations.
        
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
        LOGGER.debug("Fetching available MCP tools from server")
        try:
            async def _list_tools():
                async with await self.get_client() as client:
                    tools = await client.list_tools()
                    LOGGER.debug(f"MCP server returned {len(tools)} tools")
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
        LOGGER.debug("Fetching available MCP resources from server")
        try:
            async def _list_resources():
                async with await self.get_client() as client:
                    resources = await client.list_resources()
                    LOGGER.debug(f"MCP server returned {len(resources)} resources")
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


