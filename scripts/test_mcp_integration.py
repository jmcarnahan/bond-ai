#!/usr/bin/env python3
"""
Simple test script for MCP integration.
Uses configuration from .env file via Config class.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path so we can import bondable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bondable.bond.mcp_client import MCPClient
from bondable.bond.config import Config


async def test_mcp_integration():
    """Test the MCP client integration."""
    print("Testing MCP Integration...")
    print("=" * 50)
    
    try:
        # Test MCPClient initialization
        print("1. Getting MCPClient instance...")
        mcp_client = MCPClient.client()
        print(f"   ✓ MCPClient created")
        
        # Test configuration
        print("\n2. Checking MCP configuration...")
        config = Config.config().get_mcp_config()
        servers = config.get("mcpServers", {})
        print(f"   ✓ Found {len(servers)} configured servers:")
        for name, server_config in servers.items():
            print(f"     - {name}: {server_config}")
        
        if not servers:
            print("   ⚠️  No MCP servers configured in BOND_MCP_CONFIG")
            return
        
        # Test connection and list tools
        print("\n3. Testing connection and listing tools...")
        async with await MCPClient.get_client() as client:
            tools = await client.list_tools()
            print(f"   ✓ Connected successfully")
            print(f"   ✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"     - {tool}")
        
        # # Test listing resources
        # print("\n4. Testing resource listing...")
        # async with await MCPClient.get_client() as client:
        #     resources = await client.list_resources()
        #     print(f"   ✓ Found {len(resources)} resources:")
        #     for resource in resources:
        #         print(f"     - {resource.get('name', 'unnamed')}: {resource.get('uri', 'no uri')}")
        
        print("\n" + "=" * 50)
        print("✅ MCP Integration test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during MCP integration test:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_mcp_integration())
    sys.exit(0 if success else 1)