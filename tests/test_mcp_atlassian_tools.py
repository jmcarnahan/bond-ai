#!/usr/bin/env python3
"""
List all tools from mcp-atlassian to see their actual names.

Usage:
    poetry run python tests/test_mcp_atlassian_tools.py
"""

import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import StreamableHttpTransport
from mcp import Client
from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache

# Test user
TEST_USER_ID = os.environ.get("TEST_USER_ID", "00uxpu9a9teaAE5rn697")

async def main():
    print(f"\n{'='*60}")
    print(f"Listing Tools from mcp-atlassian")
    print(f"{'='*60}\n")

    # Get token from database
    cache = get_mcp_token_cache()
    token = cache.get_token(TEST_USER_ID, "atlassian")

    if token is None:
        print("❌ No token found in database")
        return

    if token.is_expired():
        print("❌ Token is expired")
        return

    print(f"✅ Token found and valid\n")

    # Connect to mcp-atlassian
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "User-Agent": "Bond-AI-Test/1.0"
    }

    transport = StreamableHttpTransport("http://localhost:9000/mcp", headers=headers)

    async with Client(transport) as client:
        # List all tools
        tools = await client.list_tools()

        print(f"Found {len(tools)} tools:\n")

        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.name}")
            print(f"   Description: {tool.description[:80]}...")
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                schema = tool.inputSchema
                if 'properties' in schema:
                    params = list(schema['properties'].keys())
                    print(f"   Parameters: {', '.join(params[:5])}")
            print()

    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
