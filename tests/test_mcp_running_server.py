#!/usr/bin/env python3
"""
Test MCP authentication against a running MCP server.

Prerequisites:
    Run the MCP server in a separate terminal:
    fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5555

Usage:
    poetry run python scripts/test_mcp_running_server.py
"""

import os
import asyncio
import json
from jose import jwt
from bondable.bond.config import Config
from bondable.bond.providers.bedrock.BedrockMCP import execute_mcp_tool
from bondable.rest.models.auth import User

# Load JWT secret from config
jwt_config = Config.config().get_jwt_config()
JWT_SECRET_KEY = jwt_config.JWT_SECRET_KEY
JWT_ALGORITHM = jwt_config.JWT_ALGORITHM

print("=" * 70)
print("MCP Authentication Test - Against Running Server")
print("=" * 70)
print(f"MCP Server Expected: http://127.0.0.1:5555/mcp")
print(f"JWT Algorithm: {JWT_ALGORITHM}")
print("=" * 70)
print()


async def test_mcp_auth():
    """Test MCP authentication with a running server."""

    # Create test user
    test_user = User(
        email="testuser2@bondai.com",
        name="Test User 2",
        provider="okta",
        user_id="test-user-123",
        okta_sub="okta-sub-456",
        given_name="Test",
        family_name="User",
        locale="en-US"
    )

    # Create JWT token with test user info
    # Note: Must include iss (issuer) and aud (audience) claims for MCP JWTVerifier
    jwt_payload = {
        'sub': test_user.email,
        'name': test_user.name,
        'provider': test_user.provider,
        'user_id': test_user.user_id,
        'okta_sub': test_user.okta_sub,
        'given_name': test_user.given_name,
        'family_name': test_user.family_name,
        'locale': test_user.locale,
        'iss': 'bond-ai',  # Issuer - must match MCP server configuration
        'aud': 'mcp-server'  # Audience - must match MCP server configuration
    }

    test_jwt_token = jwt.encode(jwt_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    print(f"Test User: {test_user.email}")
    print(f"JWT Token: {test_jwt_token[:50]}...")
    print()

    # Get MCP config
    config = Config.config()
    mcp_config = config.get_mcp_config()

    print(f"MCP Config: {json.dumps(mcp_config, indent=2)}")
    print()

    # Test 1: greet (protected tool - requires auth)
    print("=" * 70)
    print("TEST 1: greet() - Protected tool (requires auth)")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="greet",
            parameters={},  # No parameters - greets the authenticated user
            current_user=test_user,
            jwt_token=test_jwt_token
        )
        print(f"✅ SUCCESS: {json.dumps(result, indent=2)}")

        # Check if greeting contains user info
        result_text = result.get('result', '')
        if 'Test' in result_text or test_user.email in result_text:
            print(f"✅ VERIFIED: Greeting is personalized for authenticated user")
        else:
            print(f"⚠️  WARNING: Response doesn't contain user info")

    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()

    # Test 2: current_time (public tool)
    print("=" * 70)
    print("TEST 2: current_time() - Public tool")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="current_time",
            parameters={},
            current_user=test_user,
            jwt_token=test_jwt_token
        )
        print(f"✅ SUCCESS: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()

    # Test 3: get_user_profile (protected tool)
    print("=" * 70)
    print("TEST 3: get_user_profile() - Protected tool (requires auth)")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="get_user_profile",
            parameters={},
            current_user=test_user,
            jwt_token=test_jwt_token
        )
        print(f"✅ SUCCESS: {json.dumps(result, indent=2)}")

        # Verify user profile data
        if test_user.email in result.get('result', ''):
            print(f"✅ VERIFIED: Profile contains user email")
        if test_user.given_name in result.get('result', ''):
            print(f"✅ VERIFIED: Profile contains given name")
        if test_user.family_name in result.get('result', ''):
            print(f"✅ VERIFIED: Profile contains family name")

    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()

    # Test 4: get_user_profile without auth (should fail)
    print("=" * 70)
    print("TEST 4: get_user_profile() - Without auth (should fail)")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="get_user_profile",
            parameters={},
            current_user=None,
            jwt_token=None
        )
        if result.get('success'):
            print(f"❌ UNEXPECTED: Protected tool succeeded without auth!")
            print(f"   Result: {json.dumps(result, indent=2)}")
        else:
            print(f"✅ CORRECT: Protected tool rejected unauthenticated request")
            print(f"   Error: {result.get('error')}")

    except Exception as e:
        print(f"✅ CORRECT: Protected tool raised exception: {e}")

    print()

    # Test 5: fetch_protected_data (protected tool)
    print("=" * 70)
    print("TEST 5: fetch_protected_data(query='test') - Protected tool")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="fetch_protected_data",
            parameters={"query": "test data query"},
            current_user=test_user,
            jwt_token=test_jwt_token
        )
        print(f"✅ SUCCESS: {json.dumps(result, indent=2)}")

        # Check for user-specific data
        if test_user.email in result.get('result', ''):
            print(f"✅ VERIFIED: Data is user-specific for {test_user.email}")

    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()

    # Test 6: validate_auth (auth validation tool)
    print("=" * 70)
    print("TEST 6: validate_auth() - Validate JWT token")
    print("=" * 70)
    try:
        result = await execute_mcp_tool(
            mcp_config=mcp_config,
            tool_name="validate_auth",
            parameters={},
            current_user=test_user,
            jwt_token=test_jwt_token
        )
        print(f"✅ SUCCESS: {json.dumps(result, indent=2)}")

        # Check JWT validation result
        result_data = result.get('result', '')
        if 'authenticated' in result_data and test_user.email in result_data:
            print(f"✅ VERIFIED: JWT validation successful")

    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()
    print("=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_mcp_auth())
