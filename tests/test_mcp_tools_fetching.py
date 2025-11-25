#!/usr/bin/env python3
"""
Test MCP tools fetching from multiple servers with different auth types.

This test suite validates:
1. MCP servers are properly configured in .env
2. Tools can be fetched from JWT-authenticated servers (my_client)
3. Tools can be fetched from OAuth2-authenticated servers (atlassian)
4. Both servers work simultaneously
5. Tools are properly exposed via /mcp/tools API endpoint

Prerequisites:
- Backend running: poetry run uvicorn bondable.rest.main:app --reload --port 8000
- my_client MCP server running: fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5555
- mcp-atlassian Docker container running: docker run -p 9000:8000 ghcr.io/sooperset/mcp-atlassian:latest
- Atlassian OAuth token already stored in database (run OAuth flow once via UI)

Usage:
    poetry run pytest tests/test_mcp_tools_fetching.py -v -s

Test Organization:
- TestMcpConfiguration: Verify .env configuration is correct
- TestMcpServersRunning: Check that MCP servers are accessible
- TestMcpToolsEndpoint: Test /mcp/tools API endpoint
- TestJwtAuthServer: Test JWT-authenticated server (my_client)
- TestOAuth2Server: Test OAuth2-authenticated server (atlassian)
- TestMultiServerDiscovery: Test both servers together
"""

import pytest
import requests
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

# Test configuration
BACKEND_URL = "http://localhost:8000"
MY_CLIENT_URL = "http://127.0.0.1:5555/mcp"
ATLASSIAN_URL = "http://localhost:9000/mcp"

# Test user - must match your Okta user
# You can override these with environment variables:
# export TEST_USER_EMAIL="your@email.com"
# export TEST_USER_ID="your_okta_user_id"
import os
TEST_USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "johncarnahan@bondableai.com")
TEST_USER_ID = os.environ.get("TEST_USER_ID", "00uxpu9a9teaAE5rn697")


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_jwt() -> str:
    """Create a test JWT token for authentication."""
    from jose import jwt
    from bondable.bond.config import Config

    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "John Carnahan",
        "user_id": TEST_USER_ID,
        "provider": "okta",
        "email": TEST_USER_EMAIL,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }

    return jwt.encode(
        token_data,
        jwt_config.JWT_SECRET_KEY,
        algorithm=jwt_config.JWT_ALGORITHM
    )


def check_server_health(url: str, timeout: int = 5) -> bool:
    """Check if a server is responding."""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False


def check_mcp_server_reachable(url: str, timeout: int = 5) -> bool:
    """Check if an MCP server endpoint is reachable."""
    try:
        # Try a simple GET - MCP servers should respond even if they reject the method
        response = requests.get(url, timeout=timeout)
        # Even a 405 Method Not Allowed means the server is there
        return True
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def backend_running():
    """Verify backend is running."""
    if not check_server_health(f"{BACKEND_URL}/health"):
        pytest.skip(
            "Backend not running. Start with: "
            "poetry run uvicorn bondable.rest.main:app --reload --port 8000"
        )
    return True


@pytest.fixture
def auth_token():
    """Get an authentication token for API calls."""
    return create_test_jwt()


@pytest.fixture
def auth_headers(auth_token):
    """Get authentication headers."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


# =============================================================================
# Test: MCP Configuration
# =============================================================================

class TestMcpConfiguration:
    """Verify MCP configuration in .env is correct."""

    def test_mcp_config_loaded(self):
        """Verify MCP config is loaded from .env."""
        from bondable.bond.config import Config

        config = Config.config()
        mcp_config = config.get_mcp_config()

        assert mcp_config is not None, "MCP config should be loaded"
        assert "mcpServers" in mcp_config, "Should have mcpServers key"

        servers = mcp_config["mcpServers"]
        print(f"\n  Found {len(servers)} MCP server(s) configured:")
        for name, cfg in servers.items():
            print(f"    - {name}: {cfg.get('url', 'NO URL')}")

        assert len(servers) > 0, "Should have at least one MCP server"

    def test_my_client_configured(self):
        """Verify my_client server is configured."""
        from bondable.bond.config import Config

        mcp_config = Config.config().get_mcp_config()
        servers = mcp_config.get("mcpServers", {})

        assert "my_client" in servers, "Should have my_client configured"

        my_client = servers["my_client"]
        print(f"\n  my_client configuration:")
        print(f"    URL: {my_client.get('url')}")
        print(f"    Transport: {my_client.get('transport')}")

        assert my_client.get("url") == MY_CLIENT_URL
        assert my_client.get("transport") == "streamable-http"

    def test_atlassian_configured(self):
        """Verify atlassian server is configured with OAuth."""
        from bondable.bond.config import Config

        mcp_config = Config.config().get_mcp_config()
        servers = mcp_config.get("mcpServers", {})

        assert "atlassian" in servers, "Should have atlassian configured"

        atlassian = servers["atlassian"]
        print(f"\n  atlassian configuration:")
        print(f"    URL: {atlassian.get('url')}")
        print(f"    Transport: {atlassian.get('transport')}")
        print(f"    Auth type: {atlassian.get('auth_type')}")

        assert atlassian.get("url") == ATLASSIAN_URL
        assert atlassian.get("transport") == "streamable-http"
        assert atlassian.get("auth_type") == "oauth2"

        oauth_config = atlassian.get("oauth_config", {})
        assert oauth_config.get("client_id"), "Should have client_id"
        assert oauth_config.get("client_secret"), "Should have client_secret"


# =============================================================================
# Test: MCP Servers Running
# =============================================================================

class TestMcpServersRunning:
    """Check that MCP servers are actually running and reachable."""

    def test_my_client_server_running(self):
        """Verify my_client MCP server is running."""
        reachable = check_mcp_server_reachable(MY_CLIENT_URL)

        if not reachable:
            pytest.skip(
                f"my_client server not running at {MY_CLIENT_URL}. "
                "Start with: fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5555"
            )

        print(f"\n  ✅ my_client server is reachable at {MY_CLIENT_URL}")

    def test_atlassian_server_running(self):
        """Verify mcp-atlassian Docker container is running."""
        reachable = check_mcp_server_reachable(ATLASSIAN_URL)

        if not reachable:
            pytest.skip(
                f"mcp-atlassian server not running at {ATLASSIAN_URL}. "
                "Start with: docker run -p 9000:8000 ghcr.io/sooperset/mcp-atlassian:latest"
            )

        print(f"\n  ✅ mcp-atlassian server is reachable at {ATLASSIAN_URL}")


# =============================================================================
# Test: MCP Tools Endpoint
# =============================================================================

class TestMcpToolsEndpoint:
    """Test the /mcp/tools API endpoint that aggregates tools from all servers."""

    def test_mcp_tools_endpoint_accessible(self, backend_running, auth_headers):
        """Verify /mcp/tools endpoint is accessible."""
        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        print(f"\n  Response status: {response.status_code}")

        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"

    def test_mcp_tools_returns_list(self, backend_running, auth_headers):
        """Verify /mcp/tools returns a list of tools."""
        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        assert response.status_code == 200
        tools = response.json()

        assert isinstance(tools, list), "Should return a list"
        print(f"\n  Total tools returned: {len(tools)}")

        if len(tools) > 0:
            print(f"  Sample tool:")
            sample = tools[0]
            print(f"    Name: {sample.get('name')}")
            print(f"    Description: {sample.get('description')}")

    def test_tools_have_required_fields(self, backend_running, auth_headers):
        """Verify each tool has required fields."""
        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        assert response.status_code == 200
        tools = response.json()

        if len(tools) == 0:
            pytest.skip("No tools returned - cannot verify fields")

        for tool in tools[:5]:  # Check first 5
            assert "name" in tool, f"Tool should have 'name': {tool}"
            assert "description" in tool, f"Tool should have 'description': {tool}"
            assert "input_schema" in tool, f"Tool should have 'input_schema': {tool}"

            print(f"\n  Tool: {tool['name']}")
            print(f"    Description: {tool['description'][:60]}...")


# =============================================================================
# Test: JWT Auth Server (my_client)
# =============================================================================

class TestJwtAuthServer:
    """Test tools from JWT-authenticated MCP server (my_client)."""

    def test_my_client_tools_present(self, backend_running, auth_headers):
        """Verify tools from my_client server are in the list."""
        # Skip if my_client not running
        if not check_mcp_server_reachable(MY_CLIENT_URL):
            pytest.skip(f"my_client server not running at {MY_CLIENT_URL}")

        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        assert response.status_code == 200
        tools = response.json()
        tool_names = [t["name"] for t in tools]

        # Expected tools from sample_mcp_server.py
        expected_tools = ["greet", "get_user_profile", "fetch_protected_data"]

        print(f"\n  All tool names: {tool_names}")
        print(f"  Looking for my_client tools: {expected_tools}")

        my_client_tools = [name for name in tool_names if name in expected_tools]

        if len(my_client_tools) == 0:
            print(f"  ⚠️  No my_client tools found. Available: {tool_names}")
            pytest.fail(f"Expected at least one my_client tool. Got: {tool_names}")

        print(f"\n  ✅ Found {len(my_client_tools)} my_client tools:")
        for tool_name in my_client_tools:
            print(f"    - {tool_name}")

        assert len(my_client_tools) > 0, "Should have at least one my_client tool"


# =============================================================================
# Test: OAuth2 Server (atlassian)
# =============================================================================

class TestOAuth2Server:
    """Test tools from OAuth2-authenticated MCP server (atlassian)."""

    def test_atlassian_token_exists(self):
        """Verify Atlassian OAuth token exists in database."""
        from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache

        # Token cache now gets DB session automatically - no initialization needed
        cache = get_mcp_token_cache()
        token = cache.get_token(TEST_USER_ID, "atlassian")

        if token is None:
            pytest.skip(
                f"No Atlassian OAuth token found for user_id={TEST_USER_ID}. "
                "Run OAuth flow once via UI: http://localhost:3000/connections"
            )

        print(f"\n  ✅ Atlassian token found:")
        print(f"    User: {TEST_USER_ID}")
        print(f"    Expires: {token.expires_at}")
        print(f"    Is expired: {token.is_expired()}")

        assert not token.is_expired(), "Token is expired - re-authenticate via UI"

    def test_atlassian_tools_present(self, backend_running, auth_headers):
        """Verify tools from atlassian server are in the list."""
        # Skip if mcp-atlassian not running
        if not check_mcp_server_reachable(ATLASSIAN_URL):
            pytest.skip(f"mcp-atlassian server not running at {ATLASSIAN_URL}")

        # Skip if no token
        from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
        cache = get_mcp_token_cache()
        token = cache.get_token(TEST_USER_ID, "atlassian")
        if token is None or token.is_expired():
            pytest.skip("No valid Atlassian token - run OAuth flow via UI")

        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        assert response.status_code == 200
        tools = response.json()
        tool_names = [t["name"] for t in tools]

        print(f"\n  Total tools: {len(tool_names)}")
        print(f"  All tool names: {tool_names}")

        # Look for Atlassian-specific tools
        atlassian_keywords = ["jira", "confluence", "atlassian"]
        atlassian_tools = [
            name for name in tool_names
            if any(keyword in name.lower() for keyword in atlassian_keywords)
        ]

        print(f"\n  Atlassian-related tools found: {len(atlassian_tools)}")
        for tool_name in atlassian_tools[:10]:  # Show first 10
            print(f"    - {tool_name}")

        if len(atlassian_tools) > 10:
            print(f"    ... and {len(atlassian_tools) - 10} more")

        if len(atlassian_tools) == 0:
            print(f"\n  ⚠️  WARNING: No Atlassian tools found!")
            print(f"     This suggests mcp-atlassian is not returning tools.")
            print(f"     Check mcp-atlassian Docker logs for errors.")
            pytest.fail("No Atlassian tools found - check server logs")

        assert len(atlassian_tools) > 0, "Should have Atlassian tools"


# =============================================================================
# Test: Multi-Server Discovery
# =============================================================================

class TestMultiServerDiscovery:
    """Test that tools from multiple servers are discovered together."""

    def test_both_servers_contribute_tools(self, backend_running, auth_headers):
        """Verify tools from both my_client and atlassian are present."""
        # Check if servers are running
        my_client_running = check_mcp_server_reachable(MY_CLIENT_URL)
        atlassian_running = check_mcp_server_reachable(ATLASSIAN_URL)

        if not my_client_running:
            pytest.skip("my_client not running")
        if not atlassian_running:
            pytest.skip("mcp-atlassian not running")

        # Check if atlassian token exists
        from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
        cache = get_mcp_token_cache()
        token = cache.get_token(TEST_USER_ID, "atlassian")
        if token is None or token.is_expired():
            pytest.skip("No valid Atlassian token")

        response = requests.get(
            f"{BACKEND_URL}/mcp/tools",
            headers=auth_headers,
            timeout=30
        )

        assert response.status_code == 200
        tools = response.json()
        tool_names = [t["name"] for t in tools]

        print(f"\n  Total tools from all servers: {len(tool_names)}")

        # Check for my_client tools
        my_client_tools = ["greet", "get_user_profile", "fetch_protected_data"]
        found_my_client = [name for name in tool_names if name in my_client_tools]

        # Check for atlassian tools
        atlassian_keywords = ["jira", "confluence", "atlassian"]
        found_atlassian = [
            name for name in tool_names
            if any(keyword in name.lower() for keyword in atlassian_keywords)
        ]

        print(f"\n  my_client tools: {len(found_my_client)}")
        for name in found_my_client:
            print(f"    - {name}")

        print(f"\n  atlassian tools: {len(found_atlassian)}")
        for name in found_atlassian[:5]:
            print(f"    - {name}")
        if len(found_atlassian) > 5:
            print(f"    ... and {len(found_atlassian) - 5} more")

        # Both should contribute
        assert len(found_my_client) > 0, "Should have my_client tools"
        assert len(found_atlassian) > 0, "Should have atlassian tools"

        print(f"\n  ✅ Multi-server discovery working!")
        print(f"     {len(found_my_client)} tools from my_client")
        print(f"     {len(found_atlassian)} tools from atlassian")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
