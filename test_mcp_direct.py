#!/usr/bin/env python3
"""
Standalone test script to connect to MCP Atlassian endpoint and list tools.
This helps debug MCP connection issues without needing to deploy.

Usage:
    poetry run python test_mcp_direct.py
"""

import asyncio
import logging
import sys
import os
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)

# Enable httpx debug logging to see actual HTTP requests
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("mcp").setLevel(logging.DEBUG)

# MCP Atlassian configuration
# IMPORTANT: URL must have trailing slash to avoid redirect!
MCP_URL = "https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/"
CLOUD_ID = "55de5903-f98d-499f-967a-32673b683dc8"

# OAuth token - you'll need to provide a valid token
# Get this from the database or by authorizing via the web app
OAUTH_TOKEN = os.environ.get("ATLASSIAN_OAUTH_TOKEN")
if not OAUTH_TOKEN:
    LOGGER.error("Environment variable ATLASSIAN_OAUTH_TOKEN is not set; cannot authenticate to MCP.")
    sys.exit(1)

async def test_with_explicit_transport():
    """Test using explicit StreamableHttpTransport with headers."""
    LOGGER.info("=" * 80)
    LOGGER.info("TEST 1: Using explicit StreamableHttpTransport")
    LOGGER.info("=" * 80)

    headers = {
        'Authorization': f'Bearer {OAUTH_TOKEN}',
        'X-Atlassian-Cloud-Id': CLOUD_ID,
        'User-Agent': 'Bond-AI-MCP-Test/1.0'
    }

    try:
        transport = StreamableHttpTransport(MCP_URL, headers=headers)
        LOGGER.info(f"Transport created: {transport}")

        async with Client(transport) as client:
            LOGGER.info("Client connected successfully!")

            # List tools
            LOGGER.info("Fetching tools...")
            tools = await client.list_tools()

            LOGGER.info(f"SUCCESS! Found {len(tools)} tools:")
            for tool in tools:
                LOGGER.info(f"  - {tool.name}: {tool.description}")

            return True

    except Exception as e:
        LOGGER.error(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_config():
    """Test using config-based Client initialization."""
    LOGGER.info("=" * 80)
    LOGGER.info("TEST 2: Using config-based Client")
    LOGGER.info("=" * 80)

    config = {
        "mcpServers": {
            "atlassian": {
                "url": MCP_URL,
                "transport": "streamable-http",
                "headers": {
                    'Authorization': f'Bearer {OAUTH_TOKEN}',
                    'X-Atlassian-Cloud-Id': CLOUD_ID,
                    'User-Agent': 'Bond-AI-MCP-Test/1.0'
                }
            }
        }
    }

    try:
        async with Client(config) as client:
            LOGGER.info("Client connected successfully!")

            # List tools
            LOGGER.info("Fetching tools...")
            tools = await client.list_tools()

            LOGGER.info(f"SUCCESS! Found {len(tools)} tools:")
            for tool in tools:
                LOGGER.info(f"  - {tool.name}: {tool.description}")

            return True

    except Exception as e:
        LOGGER.error(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_explicit_headers():
    """Test adding explicit accept/content-type headers."""
    LOGGER.info("=" * 80)
    LOGGER.info("TEST 3: With explicit accept/content-type headers")
    LOGGER.info("=" * 80)

    headers = {
        'Authorization': f'Bearer {OAUTH_TOKEN}',
        'X-Atlassian-Cloud-Id': CLOUD_ID,
        'User-Agent': 'Bond-AI-MCP-Test/1.0',
        'accept': 'application/json, text/event-stream',
        'content-type': 'application/json'
    }

    try:
        transport = StreamableHttpTransport(MCP_URL, headers=headers)
        LOGGER.info(f"Transport created: {transport}")

        async with Client(transport) as client:
            LOGGER.info("Client connected successfully!")

            # List tools
            LOGGER.info("Fetching tools...")
            tools = await client.list_tools()

            LOGGER.info(f"SUCCESS! Found {len(tools)} tools:")
            for tool in tools:
                LOGGER.info(f"  - {tool.name}: {tool.description}")

            return True

    except Exception as e:
        LOGGER.error(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    LOGGER.info("Starting MCP Atlassian connection tests...")
    LOGGER.info(f"Token expires at: Check logs above for expiry")

    results = {}

    # Test 1: Explicit transport without explicit accept/content-type
    results['explicit_transport'] = await test_with_explicit_transport()

    print("\n" + "=" * 80 + "\n")

    # Test 2: Config-based
    results['config_based'] = await test_with_config()

    print("\n" + "=" * 80 + "\n")

    # Test 3: With explicit headers
    results['explicit_headers'] = await test_with_explicit_headers()

    # Summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:30s}: {status}")
    print("=" * 80)

    # Exit code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
