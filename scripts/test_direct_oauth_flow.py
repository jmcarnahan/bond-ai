#!/usr/bin/env python3
"""
Test the new direct OAuth flow (without mcp-remote).

This script tests whether Atlassian accepts our Bond backend callback URL
directly without requiring the mcp-remote tool.

Usage:
    poetry run python scripts/test_direct_oauth_flow.py

What it does:
    1. Deletes existing Atlassian token (forces re-auth)
    2. Starts OAuth flow via /connections/atlassian/authorize
    3. Opens authorization URL in browser
    4. You complete OAuth in browser
    5. Atlassian redirects to Bond backend callback
    6. Script verifies if token was stored successfully

Expected outcomes:
    - SUCCESS: Bond stores token, connection shows as "connected"
    - FAILURE: Atlassian rejects redirect_uri with error message
"""

import os
import sys
import time
import requests
import webbrowser
from datetime import datetime, timedelta, timezone
from jose import jwt

# Configuration
API_BASE_URL = os.environ.get("BOND_API_URL", "http://localhost:8000")
TEST_USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "johncarnahan@bondableai.com")
TEST_USER_ID = os.environ.get("TEST_USER_ID", TEST_USER_EMAIL)
CONNECTION_NAME = "atlassian"

# How long to wait for user to complete OAuth
OAUTH_TIMEOUT_SECONDS = 300  # 5 minutes


def create_test_jwt_token() -> str:
    """Create a JWT token for API authentication."""
    from bondable.bond.config import Config

    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Test User",
        "user_id": TEST_USER_ID,
        "provider": "okta",
        "email": TEST_USER_EMAIL,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }

    return jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)


def check_api_health() -> bool:
    """Check if Bond API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False


def get_connection_status(headers: dict) -> dict:
    """Get current connection status."""
    try:
        response = requests.get(f"{API_BASE_URL}/connections", headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        connections = data.get("connections", [])

        for conn in connections:
            if conn.get("name") == CONNECTION_NAME:
                return conn

        return None
    except Exception as e:
        print(f"❌ Error getting connection status: {e}")
        return None


def delete_connection_token(headers: dict) -> bool:
    """Delete existing connection token to force re-authentication."""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/connections/{CONNECTION_NAME}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("disconnected", False)
        else:
            print(f"⚠️  Delete returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error deleting token: {e}")
        return False


def get_authorization_url(headers: dict) -> str:
    """Get OAuth authorization URL from Bond API."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/connections/{CONNECTION_NAME}/authorize",
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print(f"❌ Authorization endpoint returned {response.status_code}")
            print(f"Response: {response.text}")
            return None

        data = response.json()
        return data.get("authorization_url")
    except Exception as e:
        print(f"❌ Error getting authorization URL: {e}")
        return None


def wait_for_connection(headers: dict, timeout_seconds: int = 300) -> bool:
    """Poll connection status until connected or timeout."""
    print(f"\n⏳ Waiting for OAuth completion (timeout: {timeout_seconds}s)...")
    print("   Complete the OAuth flow in your browser.")

    start_time = time.time()
    last_check_time = 0
    check_interval = 3  # Check every 3 seconds

    while time.time() - start_time < timeout_seconds:
        # Only check every N seconds to avoid hammering the API
        if time.time() - last_check_time < check_interval:
            time.sleep(0.5)
            continue

        last_check_time = time.time()

        status = get_connection_status(headers)
        if status and status.get("connected"):
            return True

        # Show progress every 15 seconds
        elapsed = int(time.time() - start_time)
        if elapsed % 15 == 0 and elapsed > 0:
            print(f"   Still waiting... ({elapsed}s / {timeout_seconds}s)")

    return False


def main():
    """Run the direct OAuth flow test."""
    print("=" * 70)
    print("DIRECT OAUTH FLOW TEST (WITHOUT mcp-remote)")
    print("=" * 70)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"User: {TEST_USER_EMAIL}")
    print(f"Connection: {CONNECTION_NAME}")

    # Step 1: Check API is running
    print("\n[Step 1] Checking API health...")
    if not check_api_health():
        print("\n❌ Bond API is not running!")
        print("Start it with: uvicorn bondable.rest.main:app --reload --port 8000")
        sys.exit(1)
    print("✅ API is running")

    # Step 2: Create auth token
    print("\n[Step 2] Creating JWT token...")
    try:
        jwt_token = create_test_jwt_token()
        headers = {"Authorization": f"Bearer {jwt_token}"}
        print("✅ JWT token created")
    except Exception as e:
        print(f"❌ Failed to create JWT token: {e}")
        sys.exit(1)

    # Step 3: Check current connection status
    print("\n[Step 3] Checking current connection status...")
    status = get_connection_status(headers)
    if status:
        print(f"Current status: connected={status.get('connected')}, valid={status.get('valid')}")

        if status.get("connected"):
            print("\n⚠️  Connection already exists. Deleting to force re-auth...")
            if delete_connection_token(headers):
                print("✅ Token deleted")
                time.sleep(2)  # Give DB time to update
            else:
                print("❌ Failed to delete token")
                sys.exit(1)
    else:
        print("✅ No existing connection found")

    # Step 4: Get authorization URL
    print("\n[Step 4] Getting OAuth authorization URL...")
    auth_url = get_authorization_url(headers)
    if not auth_url:
        print("❌ Failed to get authorization URL")
        sys.exit(1)

    print(f"✅ Authorization URL received")
    print(f"\n📎 URL: {auth_url}")

    # Check if URL contains our expected redirect_uri
    if "http://localhost:8000/connections/atlassian/callback" in auth_url:
        print("✅ URL contains Bond's callback URI (not mcp-remote)")
    elif "http://localhost:5598" in auth_url:
        print("⚠️  URL still contains mcp-remote callback URI!")

    # Step 5: Open browser
    print("\n[Step 5] Opening browser for OAuth...")
    try:
        webbrowser.open(auth_url)
        print("✅ Browser opened")
    except Exception as e:
        print(f"⚠️  Could not open browser automatically: {e}")
        print(f"\n📋 Please open this URL manually in your browser:")
        print(f"   {auth_url}")

    # Step 6: Wait for OAuth completion
    print("\n[Step 6] Waiting for OAuth callback to complete...")
    print("=" * 70)
    print("IMPORTANT: Look for the browser redirect after OAuth")
    print("=" * 70)
    print("\nYou should see:")
    print("  1. Atlassian login/authorization page")
    print("  2. After approving, redirect to Bond backend")
    print("  3. Success or error message from Bond\n")
    print("If you see an error about 'redirect_uri', that means Atlassian")
    print("does not accept our Bond callback URL.")
    print("=" * 70)

    if wait_for_connection(headers, timeout_seconds=OAUTH_TIMEOUT_SECONDS):
        print("\n" + "=" * 70)
        print("✅ SUCCESS - OAuth flow completed!")
        print("=" * 70)
        print("\nAtlassian accepted Bond's redirect URI!")
        print("The direct OAuth flow (without mcp-remote) works!")

        # Verify final status
        final_status = get_connection_status(headers)
        if final_status:
            print(f"\nFinal connection status:")
            print(f"  - Connected: {final_status.get('connected')}")
            print(f"  - Valid: {final_status.get('valid')}")
            print(f"  - Expires at: {final_status.get('expires_at', 'N/A')}")

        return 0
    else:
        print("\n" + "=" * 70)
        print("⏱️  TIMEOUT - OAuth not completed in time")
        print("=" * 70)
        print("\nPossible issues:")
        print("  1. You didn't complete the OAuth flow")
        print("  2. Atlassian rejected the redirect_uri")
        print("  3. Bond callback endpoint has an error\n")

        # Check final status
        final_status = get_connection_status(headers)
        if final_status and final_status.get("connected"):
            print("✅ But wait - connection IS connected!")
            print("The OAuth may have completed but we missed the status update.")
            return 0
        else:
            print("❌ Connection not established")
            print("\nCheck Bond backend logs for errors:")
            print("  - Look for errors in /connections/atlassian/callback endpoint")
            print("  - Look for Atlassian API errors about redirect_uri")
            return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
