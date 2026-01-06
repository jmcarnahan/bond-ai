#!/usr/bin/env python3
"""
Test Atlassian MCP connection and available tools.

Usage:
    poetry run python scripts/test_atlassian_mcp.py
"""

import asyncio
import json
from bondable.bond.config import Config
from bondable.bond.providers.bedrock.BedrockMCP import _get_mcp_tool_definitions

print("=" * 70)
print("Atlassian MCP Connection Test")
print("=" * 70)
print()

async def test_atlassian_mcp():
    """Test connection to Atlassian MCP server."""

    # Get MCP config
    config = Config.config()
    mcp_config = config.get_mcp_config()

    print("MCP Configuration:")
    # Print config without showing the full auth token
    safe_config = json.loads(json.dumps(mcp_config))
    if 'atlassian' in safe_config.get('mcpServers', {}):
        if 'headers' in safe_config['mcpServers']['atlassian']:
            if 'Authorization' in safe_config['mcpServers']['atlassian']['headers']:
                auth = safe_config['mcpServers']['atlassian']['headers']['Authorization']
                safe_config['mcpServers']['atlassian']['headers']['Authorization'] = auth[:20] + "..." if len(auth) > 20 else auth

    print(json.dumps(safe_config, indent=2))
    print()

    # Check if Atlassian server is configured
    if 'atlassian' not in mcp_config.get('mcpServers', {}):
        print("❌ ERROR: Atlassian MCP server not found in configuration")
        return

    atlassian_config = mcp_config['mcpServers']['atlassian']
    print(f"Atlassian MCP URL: {atlassian_config.get('url')}")
    print()

    # Try to connect and list tools
    print("=" * 70)
    print("TEST: Connecting to Atlassian MCP")
    print("=" * 70)

    try:
        # Try to list tools (this will test the connection)
        print("Attempting to list available tools...")

        # Simple HTTP connectivity test
        import httpx

        url = atlassian_config.get('url')
        headers = atlassian_config.get('headers', {})

        print(f"Connecting to: {url}")
        print(f"With headers: {list(headers.keys())}")
        print()

        # Try to connect with HTTP client
        try:
            async with httpx.AsyncClient() as http_client:
                print("Making HTTP request to Atlassian MCP endpoint...")

                # Try a simple GET request first
                response = await http_client.get(url, headers=headers, timeout=10.0)

                print(f"Response status: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")
                print()

                if response.status_code == 200:
                    print("✅ Connection successful!")
                    print(f"Response: {response.text[:500]}")
                elif response.status_code == 404:
                    print("⚠️  Endpoint not found (404)")
                    print("   The MCP endpoint URL might be incorrect")
                    print("   Atlassian MCP might not be enabled for your account")
                elif response.status_code == 401 or response.status_code == 403:
                    print("⚠️  Authentication failed")
                    print("   Check your API token permissions")
                else:
                    print(f"⚠️  Unexpected response: {response.status_code}")
                    print(f"Response: {response.text[:500]}")

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print()
            print("Possible issues:")
            print("  1. Atlassian MCP endpoint URL might be incorrect")
            print("  2. API token might not have proper permissions")
            print("  3. Atlassian Rovo/MCP might not be enabled for your account")
            print("  4. Your Atlassian plan might not include MCP access")
            print()
            print("Try checking:")
            print("  - https://support.atlassian.com/atlassian-rovo-mcp-server/")
            print("  - Your Atlassian admin console for MCP/Rovo settings")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_atlassian_mcp())
