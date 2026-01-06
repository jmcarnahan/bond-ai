#!/usr/bin/env python3
"""
Test script for Atlassian MCP OAuth flow.

This script demonstrates the OAuth flow for connecting to the Atlassian MCP server:
1. Authenticate to Bond (create JWT)
2. Request authorization URL from Bond
3. User opens URL in browser and authorizes
4. Callback stores token in Bond's cache
5. Test MCP tool calls with stored token

Usage:
    # Make sure the backend is running first:
    # uvicorn bondable.rest.main:app --reload --port 8000

    python scripts/test_atlassian_mcp_oauth.py
"""

import requests
import webbrowser
from datetime import datetime, timedelta, timezone
from jose import jwt
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MCP_SERVER_NAME = "atlassian"

def create_test_jwt(email: str = "johncarnahan@bondableai.com") -> str:
    """Create a JWT token for testing."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": email,
        "email": email,
        "name": "John Carnahan",
        "user_id": f"test_user_{email.split('@')[0]}",
        "provider": "okta",
        "iss": jwt_config.JWT_ISSUER,
        "aud": "mcp-server",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
    return token


def test_health():
    """Test backend health."""
    print("\n1. Testing backend health...")
    response = requests.get(f"{BACKEND_URL}/health")
    if response.status_code == 200:
        print(f"   ✅ Backend is healthy: {response.json()}")
        return True
    else:
        print(f"   ❌ Backend health check failed: {response.status_code}")
        return False


def test_mcp_status(token: str):
    """Test MCP status endpoint."""
    print("\n2. Testing MCP status...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BACKEND_URL}/mcp/status", headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ MCP Status: {data}")
        return data
    else:
        print(f"   ❌ MCP status failed: {response.status_code} - {response.text}")
        return None


def test_mcp_connections(token: str):
    """Test MCP connections endpoint."""
    print("\n3. Checking MCP connections...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BACKEND_URL}/mcp/connections", headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ MCP Connections: {data}")
        return data
    else:
        print(f"   ❌ MCP connections failed: {response.status_code} - {response.text}")
        return None


def test_server_status(token: str, server_name: str):
    """Test specific server connection status."""
    print(f"\n4. Checking {server_name} connection status...")
    headers = {"Authorization": f"Bearer {token}"}
    # Use the /connections/ endpoint (OAuth is handled there, not /mcp/servers/)
    response = requests.get(f"{BACKEND_URL}/connections/{server_name}/status", headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Connection Status: {data}")
        return data
    elif response.status_code == 404:
        print(f"   ❌ Connection '{server_name}' not found in configuration")
        print(f"      Make sure BOND_MCP_CONFIG in .env includes '{server_name}' with auth_type='oauth2'")
        return None
    else:
        print(f"   ❌ Connection status failed: {response.status_code} - {response.text}")
        return None


def initiate_oauth_connect(token: str, server_name: str):
    """Initiate OAuth connection."""
    print(f"\n5. Initiating OAuth connection to {server_name}...")
    headers = {"Authorization": f"Bearer {token}"}
    # Use the /connections/ endpoint (OAuth is handled there, not /mcp/servers/)
    response = requests.get(f"{BACKEND_URL}/connections/{server_name}/authorize", headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ OAuth initiation successful")

        if "authorization_url" in data:
            print(f"\n   Authorization URL generated!")
            print(f"   URL: {data['authorization_url'][:100]}...")
            return data
        else:
            print(f"   Response: {data}")
            return data
    else:
        print(f"   ❌ OAuth initiation failed: {response.status_code} - {response.text}")
        return None


def main():
    print("=" * 60)
    print("Atlassian MCP OAuth Flow Test")
    print("=" * 60)

    # Step 1: Test health
    if not test_health():
        print("\n❌ Backend is not running. Start it with:")
        print("   uvicorn bondable.rest.main:app --reload --port 8000")
        return

    # Step 2: Create JWT token
    print("\n2. Creating test JWT token...")
    try:
        token = create_test_jwt()
        print(f"   ✅ JWT token created for johncarnahan@bondableai.com")
    except Exception as e:
        print(f"   ❌ Failed to create JWT: {e}")
        return

    # Step 3: Test MCP status
    test_mcp_status(token)

    # Step 4: Test connections
    test_mcp_connections(token)

    # Step 5: Test server status
    server_status = test_server_status(token, MCP_SERVER_NAME)
    if server_status is None:
        print("\n❌ Atlassian connection not configured. Add to .env:")
        print('''
BOND_MCP_CONFIG='{
  "mcpServers": {
    "atlassian": {
      "url": "http://localhost:9000/mcp",
      "auth_type": "oauth2",
      "transport": "streamable-http",
      "display_name": "Atlassian",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "YOUR_CLIENT_ID",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work offline_access",
        "redirect_uri": "http://localhost:8000/connections/atlassian/callback"
      }
    }
  }
}'
''')
        return

    # Step 6: Check if already connected
    if server_status.get("connected"):
        print(f"\n✅ Already connected to {MCP_SERVER_NAME}!")
        print(f"   Provider: {server_status.get('provider')}")
        print(f"   Expires: {server_status.get('expires_at')}")
    else:
        # Step 7: Initiate OAuth
        oauth_result = initiate_oauth_connect(token, MCP_SERVER_NAME)

        if oauth_result and "authorization_url" in oauth_result:
            print("\n" + "=" * 60)
            print("NEXT STEPS:")
            print("=" * 60)
            print("\n1. Open this URL in your browser:")
            print(f"\n   {oauth_result['authorization_url']}")
            print("\n2. Log in with your Okta credentials (johncarnahan@bondableai.com)")
            print("\n3. Authorize the MCP to access your Atlassian data")
            print("\n4. You'll be redirected back to the callback URL")
            print("\n5. Re-run this script to verify the connection")

            # Ask if user wants to open browser
            print("\n" + "-" * 60)
            open_browser = input("Open authorization URL in browser now? (y/n): ")
            if open_browser.lower() == 'y':
                webbrowser.open(oauth_result['authorization_url'])
                print("\n   Browser opened! Complete the authorization flow.")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
