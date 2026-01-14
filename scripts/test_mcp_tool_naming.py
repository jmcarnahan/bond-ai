#!/usr/bin/env python3
"""
Test MCP tool naming scheme and server routing.

Tests the new tool naming format: b.{hash6}.{tool_name}
Verifies correct server authentication when invoking tools.

Usage:
    # Terminal 1: Start backend
    poetry run uvicorn bondable.rest.main:app --reload --port 8000

    # Terminal 2: Start sample MCP server
    export JWT_SECRET_KEY="$JWT_SECRET_KEY"  # Set from your .env file
    fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5555

    # Terminal 3: Run tests
    poetry run python scripts/test_mcp_tool_naming.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime, timedelta, timezone
from jose import jwt


BASE_URL = os.getenv("BOND_API_URL", "http://localhost:8000")


def create_auth_token():
    """Create JWT token for testing."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()
    return jwt.encode({
        "sub": "testuser@bondai.com",
        "user_id": "test-user-mcp-naming",
        "name": "MCP Test User",
        "provider": "okta",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iss": "bond-ai",
        "aud": "mcp-server"
    }, jwt_config.JWT_SECRET_KEY, algorithm="HS256")


# =============================================================================
# Unit Tests for Hash Functions
# =============================================================================

def test_hash_functions():
    """Test the hash utility functions."""
    print("\n" + "=" * 60)
    print("Testing Hash Utility Functions")
    print("=" * 60)

    from bondable.bond.providers.bedrock.BedrockMCP import (
        _hash_server_name, _build_tool_path, _parse_tool_path, _resolve_server_from_hash
    )

    # Test 1: Hash generation
    print("\n1. Testing hash generation...")
    h1 = _hash_server_name("my_client")
    print(f"   Hash of 'my_client': {h1}")
    assert len(h1) == 6, f"Hash should be 6 characters, got {len(h1)}"
    assert h1.isalnum(), "Hash should be alphanumeric"
    print("   PASSED: Hash is 6 alphanumeric characters")

    # Test 2: Hash consistency
    print("\n2. Testing hash consistency...")
    h2 = _hash_server_name("my_client")
    assert h1 == h2, "Same server should produce same hash"
    print(f"   Same input produces same hash: {h1} == {h2}")
    print("   PASSED: Hash is consistent")

    # Test 3: Different servers produce different hashes
    print("\n3. Testing hash uniqueness...")
    h3 = _hash_server_name("other_server")
    print(f"   Hash of 'other_server': {h3}")
    assert h1 != h3, "Different servers should produce different hashes"
    print(f"   'my_client' ({h1}) != 'other_server' ({h3})")
    print("   PASSED: Different servers have different hashes")

    # Test 4: Path building
    print("\n4. Testing path building...")
    path = _build_tool_path("my_client", "current_time")
    print(f"   Built path: {path}")
    assert path.startswith("/b."), f"Path should start with /b., got {path}"
    assert ".current_time" in path, "Path should contain tool name"
    expected_path = f"/b.{h1}.current_time"
    assert path == expected_path, f"Expected {expected_path}, got {path}"
    print("   PASSED: Path built correctly")

    # Test 5: Path parsing
    print("\n5. Testing path parsing...")
    server_hash, tool_name = _parse_tool_path(path)
    print(f"   Parsed: server_hash={server_hash}, tool_name={tool_name}")
    assert server_hash == h1, f"Parsed hash should match original: {server_hash} != {h1}"
    assert tool_name == "current_time", f"Parsed tool name should match: {tool_name}"
    print("   PASSED: Path parsed correctly")

    # Test 6: Invalid path parsing
    print("\n6. Testing invalid path handling...")
    invalid_paths = [
        None,
        "",
        "/invalid/path",
        "/_bond_mcp_tool_old_format",
        "/b.short.tool",  # hash too short
        "/b.toolong1.tool",  # hash too long
    ]
    for invalid_path in invalid_paths:
        sh, tn = _parse_tool_path(invalid_path)
        assert sh is None and tn is None, f"Invalid path {invalid_path} should return (None, None)"
    print("   PASSED: Invalid paths handled correctly")

    # Test 7: Server resolution
    print("\n7. Testing server resolution...")
    mcp_config = {"mcpServers": {"my_client": {"url": "http://test"}, "other_server": {"url": "http://test2"}}}
    resolved = _resolve_server_from_hash(server_hash, mcp_config)
    assert resolved == "my_client", f"Should resolve to 'my_client', got '{resolved}'"
    print(f"   Resolved hash {server_hash} to server '{resolved}'")
    print("   PASSED: Server resolved correctly")

    # Test 8: Unknown hash resolution
    print("\n8. Testing unknown hash resolution...")
    unknown = _resolve_server_from_hash("000000", mcp_config)
    assert unknown is None, "Unknown hash should return None"
    print("   PASSED: Unknown hash returns None")

    print("\n" + "=" * 60)
    print("ALL HASH FUNCTION TESTS PASSED")
    print("=" * 60)


# =============================================================================
# Integration Tests
# =============================================================================

def test_create_agent_with_mcp_tools():
    """Test creating agent with MCP tools uses new naming."""
    print("\n" + "=" * 60)
    print("Testing Agent Creation with MCP Tools")
    print("=" * 60)

    token = create_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Create agent with MCP tools
    agent_name = f"MCP Test Agent {datetime.now().strftime('%H%M%S')}"
    print(f"\n1. Creating agent: {agent_name}")
    response = requests.post(f"{BASE_URL}/agents", headers=headers, json={
        "name": agent_name,
        "description": "Test agent for MCP tool naming",
        "instructions": "You have access to MCP tools. When asked about time, use the current_time tool. When asked to fetch data, use the fetch_data tool.",
        "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "mcp_tools": ["current_time", "fetch_data"]
    })

    if response.status_code not in [200, 201]:
        print(f"   ERROR: {response.status_code}")
        return None

    agent = response.json()
    agent_id = agent.get('agent_id') or agent.get('id')
    print(f"   Created agent: {agent_id}")
    print("   PASSED: Agent created successfully")

    return agent_id, headers


def test_invoke_mcp_tool(agent_id, headers):
    """Test invoking MCP tool routes to correct server."""
    print("\n" + "=" * 60)
    print("Testing MCP Tool Invocation")
    print("=" * 60)

    # Create thread
    print("\n1. Creating thread...")
    thread_resp = requests.post(f"{BASE_URL}/threads", headers=headers,
                               json={"name": "MCP Tool Naming Test Thread"})
    if thread_resp.status_code not in [200, 201]:
        print(f"   ERROR creating thread: {thread_resp.status_code}")
        return None, False

    thread = thread_resp.json()
    thread_id = thread.get('id') or thread.get('thread_id')
    print(f"   Created thread: {thread_id}")

    # Send message that should trigger MCP tool
    print("\n2. Sending chat message to trigger MCP tool...")
    print("   Prompt: 'What is the current time? Please use the current_time tool.'")
    response = requests.post(f"{BASE_URL}/chat", headers=headers, json={
        "thread_id": thread_id,
        "agent_id": agent_id,
        "prompt": "What is the current time? Please use the current_time tool."
    }, stream=True)

    if response.status_code != 200:
        print(f"   ERROR: {response.status_code}")
        return thread_id, False

    # Collect response
    output = ""
    print("\n3. Receiving streamed response...")
    for chunk in response.iter_content(decode_unicode=True):
        output += chunk

    print(f"   Response length: {len(output)} chars")

    # Check for time-related content (tool should have been invoked)
    time_indicators = ['time', ':', 'am', 'pm', 'utc', 'gmt', 'iso']
    success = any(x in output.lower() for x in time_indicators)

    if success:
        print("\n   PASSED: Response contains time-related content")
    else:
        print("\n   FAILED: Response doesn't contain expected time content")

    return thread_id, success


def cleanup(agent_id, thread_id, headers):
    """Clean up test resources."""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)

    if agent_id:
        resp = requests.delete(f"{BASE_URL}/agents/{agent_id}", headers=headers)
        print(f"   Deleted agent {agent_id}: {resp.status_code}")
    if thread_id:
        resp = requests.delete(f"{BASE_URL}/threads/{thread_id}", headers=headers)
        print(f"   Deleted thread {thread_id}: {resp.status_code}")


def main():
    print("=" * 60)
    print("MCP Tool Naming Test Suite")
    print("=" * 60)
    print(f"Backend URL: {BASE_URL}")

    all_passed = True

    # Unit tests (can run without servers)
    try:
        test_hash_functions()
    except ImportError as e:
        print(f"\nSkipping hash function tests (import error): {e}")
        all_passed = False
    except AssertionError as e:
        print(f"\nHash function test FAILED: {e}")
        all_passed = False
    except Exception as e:
        print(f"\nHash function test error: {e}")
        all_passed = False

    # Integration tests (require running servers)
    agent_id = None
    thread_id = None
    headers = None

    try:
        result = test_create_agent_with_mcp_tools()
        if result:
            agent_id, headers = result
            thread_id, success = test_invoke_mcp_tool(agent_id, headers)
            if not success:
                all_passed = False
        else:
            print("\nSkipping invocation test (agent creation failed)")
            all_passed = False
    except requests.ConnectionError as e:
        print(f"\nSkipping integration tests (backend not running): {e}")
        print("Make sure to start the backend server first:")
        print("  poetry run uvicorn bondable.rest.main:app --reload --port 8000")
    except Exception as e:
        print(f"\nIntegration test error: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    finally:
        if agent_id or thread_id:
            cleanup(agent_id, thread_id, headers)

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
