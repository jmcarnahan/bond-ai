#!/usr/bin/env python3
"""
Live integration test for OAuth token auto-refresh.

This test validates that the token refresh mechanism works against a real
OAuth provider (Atlassian). It requires a previously completed OAuth flow
with a valid refresh_token stored in the database.

Prerequisites:
- Bond API server running (or at minimum, database accessible)
- Atlassian OAuth completed once via UI: Connections -> Atlassian -> Connect
- The stored token must have a refresh_token (offline_access scope)

Usage:
    poetry run pytest tests/test_oauth_refresh_live.py -v -s

WARNING: This test makes real HTTP calls to Atlassian's OAuth token endpoint.
It will consume a refresh_token rotation (Atlassian uses rotating refresh tokens).
"""

import pytest
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Test configuration - can be overridden via environment variables
TEST_CONNECTION_NAME = os.environ.get("TEST_CONNECTION_NAME", "atlassian")
TEST_USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "johncarnahan@bondableai.com")
TEST_USER_ID = os.environ.get("TEST_USER_ID", TEST_USER_EMAIL)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def token_cache():
    """Get the MCP token cache instance."""
    from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
    return get_mcp_token_cache()


@pytest.fixture
def database_token(token_cache):
    """Load existing token from database.

    The token should have been stored via the OAuth flow in the UI.
    We load it directly from the DB (bypassing expiry checks) to access
    the refresh_token even if the access_token is expired.
    """
    token_data = token_cache._load_from_database(TEST_USER_ID, TEST_CONNECTION_NAME)

    if token_data is None:
        pytest.skip(
            f"No token found for user={TEST_USER_ID}, connection={TEST_CONNECTION_NAME}. "
            "Complete OAuth via UI first: Connections -> Atlassian -> Connect"
        )

    if not token_data.refresh_token:
        pytest.skip(
            "Token exists but has no refresh_token. "
            "Re-authenticate with offline_access scope via UI."
        )

    return token_data


# =============================================================================
# Test: Live Token Refresh
# =============================================================================

class TestLiveTokenRefresh:
    """Test token refresh against the real Atlassian OAuth endpoint."""

    def test_refresh_token_exists(self, database_token):
        """Step 1: Verify the stored token has a refresh_token."""
        print(f"\n{'='*60}")
        print(f"Token info:")
        print(f"  Provider: {database_token.provider}")
        print(f"  Has refresh_token: {database_token.refresh_token is not None}")
        print(f"  Expires at: {database_token.expires_at}")
        print(f"  Is expired: {database_token.is_expired()}")
        print(f"  Scopes: {database_token.scopes}")
        print(f"{'='*60}")

        assert database_token.refresh_token is not None, "refresh_token must exist"
        print("  refresh_token present")

    def test_force_expire_and_refresh(self, token_cache, database_token):
        """Step 2: Force-expire the token, then refresh via real HTTP call."""
        original_access = database_token.access_token
        original_refresh = database_token.refresh_token

        print(f"\n{'='*60}")
        print(f"LIVE REFRESH TEST")
        print(f"  Original access_token (first 20 chars): {original_access[:20]}...")
        print(f"  Original refresh_token (first 20 chars): {original_refresh[:20]}...")

        # Force-expire the token by updating expires_at in the database
        session = token_cache._get_db_session()
        if session is None:
            pytest.skip("Cannot get database session")

        try:
            from bondable.bond.providers.metadata import UserConnectionToken
            record = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == TEST_USER_ID,
                UserConnectionToken.connection_name == TEST_CONNECTION_NAME
            ).first()

            if record is None:
                pytest.skip("Token record not found in database")

            # Save original expiry for restoration
            original_expires_at = record.expires_at

            # Set token to be expired (1 hour ago)
            record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            session.commit()
            print(f"  Manually expired token (set expires_at to 1 hour ago)")
        finally:
            session.close()

        # Now call get_token with auto_refresh=True - this should trigger real refresh
        print(f"  Calling get_token(auto_refresh=True)...")
        refreshed = token_cache.get_token(TEST_USER_ID, TEST_CONNECTION_NAME, auto_refresh=True)

        if refreshed is None:
            # Restore the original token if refresh failed
            print("  REFRESH FAILED - attempting to restore original token")
            session = token_cache._get_db_session()
            if session:
                try:
                    record = session.query(UserConnectionToken).filter(
                        UserConnectionToken.user_id == TEST_USER_ID,
                        UserConnectionToken.connection_name == TEST_CONNECTION_NAME
                    ).first()
                    if record:
                        record.expires_at = original_expires_at
                        session.commit()
                        print("  Original token restored")
                finally:
                    session.close()
            pytest.fail("Token refresh failed - check OAuth config and logs")

        print(f"  New access_token (first 20 chars): {refreshed.access_token[:20]}...")
        print(f"  New refresh_token (first 20 chars): {refreshed.refresh_token[:20]}...")
        print(f"  New expires_at: {refreshed.expires_at}")
        print(f"{'='*60}")

        # Verify new tokens are different from original
        assert refreshed.access_token != original_access, \
            "New access_token should be different from original"
        assert not refreshed.is_expired(), \
            "Refreshed token should not be expired"

        # Atlassian uses rotating refresh tokens, so the refresh_token should be new
        print(f"  Refresh token rotated: {refreshed.refresh_token != original_refresh}")
        if refreshed.refresh_token != original_refresh:
            print("  Rotating refresh token confirmed")

        # Verify the new token is persisted in the database
        from bondable.bond.auth.token_encryption import decrypt_token
        session = token_cache._get_db_session()
        try:
            record = session.query(UserConnectionToken).filter(
                UserConnectionToken.user_id == TEST_USER_ID,
                UserConnectionToken.connection_name == TEST_CONNECTION_NAME
            ).first()
            assert record is not None
            assert decrypt_token(record.access_token_encrypted) == refreshed.access_token
            print("  New token verified in database")
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_mcp_tool_call_with_refreshed_token(self, token_cache, database_token):
        """Step 3: Use the refreshed token to make an actual MCP tool call."""
        # Get a valid token (may have been refreshed in the previous test)
        token_data = token_cache.get_token(TEST_USER_ID, TEST_CONNECTION_NAME, auto_refresh=True)

        if token_data is None:
            pytest.skip("No valid token available (refresh may have failed)")

        if token_data.is_expired():
            pytest.skip("Token is still expired after refresh attempt")

        print(f"\n{'='*60}")
        print(f"MCP TOOL CALL TEST")
        print(f"  Token valid: {not token_data.is_expired()}")
        print(f"  Expires at: {token_data.expires_at}")

        # Try connecting to the Atlassian MCP server
        from fastmcp import Client
        from fastmcp.client.transports import SSETransport

        atlassian_url = os.environ.get("ATLASSIAN_MCP_URL", "https://mcp.atlassian.com/v1/sse")
        cloud_id = os.environ.get("ATLASSIAN_CLOUD_ID", "ec8ace41-7cde-4e66-aaf1-6fca83a00c53")

        headers = {
            'Authorization': f'Bearer {token_data.access_token}',
            'X-Atlassian-Cloud-Id': cloud_id,
            'User-Agent': 'Bond-AI-MCP-Client/1.0',
        }

        try:
            transport = SSETransport(atlassian_url, headers=headers)
            async with Client(transport) as client:
                tools = await client.list_tools()
                print(f"  Connected to Atlassian MCP: {len(tools)} tools available")

                # Try a simple read-only tool call
                tool_names = [t.name for t in tools]
                print(f"  Available tools: {tool_names[:10]}...")

                if 'get_myself' in tool_names:
                    result = await client.call_tool('get_myself', {})
                    print(f"  get_myself result: {str(result)[:200]}...")
                    print("  MCP tool call with refreshed token: SUCCESS")
                elif 'list_projects' in tool_names:
                    result = await client.call_tool('list_projects', {})
                    print(f"  list_projects result: {str(result)[:200]}...")
                    print("  MCP tool call with refreshed token: SUCCESS")
                else:
                    print(f"  No suitable read-only tool found, but connection succeeded")

        except Exception as e:
            print(f"  MCP connection error: {e}")
            pytest.fail(f"MCP tool call failed with refreshed token: {e}")

        print(f"{'='*60}")
