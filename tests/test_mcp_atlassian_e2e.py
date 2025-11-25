#!/usr/bin/env python3
"""
End-to-end integration test for mcp-atlassian (third-party MCP server).

This test suite validates the complete flow of:
1. Authentication via Bond REST API
2. Agent creation with Jira MCP tools
3. Message sending that triggers tool execution
4. Response validation
5. Cleanup

Prerequisites:
- Bond API server running: poetry run uvicorn bondable.rest.main:app --reload --port 8000
- mcp-atlassian Docker container running on port 9000
- Atlassian OAuth token stored in database (via UI OAuth flow)

Usage:
    poetry run pytest tests/test_mcp_atlassian_e2e.py -v -s

Test Flow:
- TestE2EAtlassianIntegration: Complete flow from API auth to tool execution
"""

import pytest
import requests
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# Test configuration
BACKEND_URL = "http://localhost:8000"
ATLASSIAN_MCP_URL = "http://localhost:9000/mcp"

# Test user - must match your Okta user
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


@pytest.fixture
def atlassian_token_exists():
    """Verify Atlassian OAuth token exists in database."""
    from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache

    cache = get_mcp_token_cache()
    token = cache.get_token(TEST_USER_ID, "atlassian")

    if token is None:
        pytest.skip(
            f"No Atlassian OAuth token found for user_id={TEST_USER_ID}. "
            "Authorize via UI: http://localhost:3000/connections"
        )

    if token.is_expired():
        pytest.skip(
            "Atlassian token is expired. Re-authorize via UI: http://localhost:3000/connections"
        )

    print(f"\n  ✅ Atlassian token found:")
    print(f"     User: {TEST_USER_ID}")
    print(f"     Expires: {token.expires_at}")
    print(f"     Scopes: {token.scopes}")

    return token


# =============================================================================
# Bond API Client
# =============================================================================

class BondAPIClient:
    """HTTP client for interacting with Bond AI REST API in tests."""

    def __init__(self, base_url: str, headers: dict):
        self.base_url = base_url.rstrip('/')
        self.headers = headers
        self.created_agents = []
        self.created_threads = []

    def create_agent_with_mcp_tools(
        self,
        name: str,
        mcp_tools: list,
        description: str = None,
        instructions: str = None
    ) -> dict:
        """Create an agent with MCP tools configured."""
        payload = {
            "name": name,
            "description": description or f"Test agent: {name}",
            "instructions": instructions or "You are a helpful assistant with access to Jira tools.",
            "tools": [],
            "mcp_tools": mcp_tools,
            "mcp_resources": [],
            "metadata": {"test": "true", "created_by": "e2e_test"}
        }

        print(f"\n  Creating agent: {name}")
        print(f"  MCP tools: {mcp_tools}")

        response = requests.post(
            f"{self.base_url}/agents",
            headers=self.headers,
            json=payload,
            timeout=120  # Agent creation can take a while
        )

        if response.status_code != 200:
            print(f"  ❌ Agent creation failed: {response.status_code}")
            print(f"     Response: {response.text[:500]}")
            response.raise_for_status()

        agent = response.json()
        self.created_agents.append(agent['agent_id'])

        print(f"  ✅ Agent created: {agent['agent_id']}")
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        print(f"\n  Deleting agent: {agent_id}")
        try:
            response = requests.delete(
                f"{self.base_url}/agents/{agent_id}",
                headers=self.headers,
                timeout=60
            )
            if response.status_code == 204:
                if agent_id in self.created_agents:
                    self.created_agents.remove(agent_id)
                print(f"  ✅ Agent deleted")
                return True
            print(f"  ⚠️  Delete returned: {response.status_code}")
            return False
        except Exception as e:
            print(f"  ❌ Delete failed: {e}")
            return False

    def chat(self, agent_id: str, prompt: str, thread_id: str = None, timeout: int = 120) -> str:
        """Send a chat message and collect the streaming response."""
        payload = {
            "agent_id": agent_id,
            "prompt": prompt
        }

        if thread_id:
            payload["thread_id"] = thread_id

        print(f"\n  Sending chat message:")
        print(f"    Prompt: {prompt}")
        print(f"    Agent: {agent_id}")

        response = requests.post(
            f"{self.base_url}/chat",
            headers=self.headers,
            json=payload,
            stream=True,
            timeout=timeout
        )

        if response.status_code != 200:
            print(f"  ❌ Chat failed: {response.status_code}")
            print(f"     Response: {response.text[:500]}")
            response.raise_for_status()

        # Collect streaming response
        full_response = ""
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                full_response += chunk

        print(f"  ✅ Received response ({len(full_response)} chars)")
        return full_response

    def cleanup(self):
        """Clean up all created resources."""
        print(f"\n  Cleaning up {len(self.created_agents)} agent(s)...")
        for agent_id in self.created_agents.copy():
            self.delete_agent(agent_id)


# =============================================================================
# Test: Complete E2E Flow
# =============================================================================

class TestE2EAtlassianIntegration:
    """End-to-end test of Atlassian MCP integration via Bond REST API."""

    def test_complete_jira_integration_flow(
        self,
        backend_running,
        auth_headers,
        atlassian_token_exists
    ):
        """
        Complete flow:
        1. Create agent with Jira tools
        2. Send message to query Jira
        3. Verify response contains real Jira data
        4. Delete agent
        """
        print("\n" + "=" * 70)
        print("E2E TEST: Complete Jira Integration Flow")
        print("=" * 70)

        client = BondAPIClient(BACKEND_URL, auth_headers)

        try:
            # Step 1: Create agent with Jira tool
            print("\n[Step 1] Creating agent with Jira tools...")
            agent_name = f"Jira E2E Test Agent {datetime.now().strftime('%Y%m%d_%H%M%S')}"

            agent = client.create_agent_with_mcp_tools(
                name=agent_name,
                mcp_tools=["jira_get_issue"],  # Tool from mcp-atlassian
                instructions=(
                    "You are a helpful assistant with access to Jira. "
                    "When asked about Jira issues, use the jira_get_issue tool to get real data. "
                    "Always call the tool - never say you can't access Jira."
                )
            )

            agent_id = agent['agent_id']
            assert agent_id, "Agent should have an ID"
            print(f"  ✅ Agent created successfully")

            # Step 2: Send message that should trigger Jira tool
            print("\n[Step 2] Sending message to trigger Jira tool...")
            prompt = "Tell me about Jira issue ECS-6"

            response = client.chat(
                agent_id=agent_id,
                prompt=prompt,
                timeout=180  # MCP tool execution can take time
            )

            assert response, "Expected non-empty response"
            print(f"  ✅ Response received")

            # Step 3: Validate response contains real Jira data
            print("\n[Step 3] Validating response contains real Jira data...")

            response_lower = response.lower()

            # Check for denial phrases (bad - means tool wasn't called)
            denial_phrases = [
                "don't have access",
                "unable to",
                "cannot access",
                "i apologize",
                "i don't have",
                "no access to",
            ]
            has_denial = any(phrase in response_lower for phrase in denial_phrases)

            if has_denial:
                print(f"\n  ❌ TOOL NOT CALLED - Agent returned denial:")
                print(f"     {response[:300]}...")
                pytest.fail("Agent did not call Jira tool - returned denial message")

            # Check for indicators of real Jira data
            # ECS-6 is a real issue in the test Jira instance
            jira_indicators = [
                "ecs-6",  # Issue key
                "epic",   # Likely in the issue
                "jira",   # Should mention Jira
                "status", # Issue should have status
                "summary" # Issue should have summary
            ]

            found_indicators = [ind for ind in jira_indicators if ind in response_lower]

            print(f"\n  Response analysis:")
            print(f"    Length: {len(response)} chars")
            print(f"    Found Jira indicators: {found_indicators}")
            print(f"    Has denial phrases: {has_denial}")

            # Response should contain at least some Jira-specific data
            assert len(found_indicators) >= 2, (
                f"Expected response to contain real Jira data. "
                f"Found only: {found_indicators}. "
                f"Response preview: {response[:300]}..."
            )

            print(f"  ✅ Response contains real Jira data")
            print(f"\n  Response preview:")
            print(f"  {response[:400]}...")

            # Step 4: Cleanup
            print("\n[Step 4] Cleaning up...")
            deleted = client.delete_agent(agent_id)
            assert deleted, "Failed to delete agent"
            print(f"  ✅ Cleanup successful")

            print("\n" + "=" * 70)
            print("✅ E2E TEST PASSED - Complete Jira integration working!")
            print("=" * 70)

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            # Cleanup on failure
            client.cleanup()
            raise

    def test_multiple_tools_in_single_agent(
        self,
        backend_running,
        auth_headers,
        atlassian_token_exists
    ):
        """Test agent with multiple Jira tools."""
        print("\n" + "=" * 70)
        print("E2E TEST: Agent with Multiple Jira Tools")
        print("=" * 70)

        client = BondAPIClient(BACKEND_URL, auth_headers)

        try:
            # Create agent with multiple tools
            print("\n[Step 1] Creating agent with multiple Jira tools...")
            agent_name = f"Multi-Tool Test Agent {datetime.now().strftime('%Y%m%d_%H%M%S')}"

            agent = client.create_agent_with_mcp_tools(
                name=agent_name,
                mcp_tools=["jira_get_issue", "jira_search"],
                instructions="You are a Jira assistant with search and get capabilities."
            )

            agent_id = agent['agent_id']
            print(f"  ✅ Agent created with 2 tools")

            # Send message that could use either tool
            print("\n[Step 2] Sending message...")
            response = client.chat(
                agent_id=agent_id,
                prompt="Search for issues in project ECS",
                timeout=180
            )

            assert response, "Expected non-empty response"
            print(f"  ✅ Response received ({len(response)} chars)")

            # Cleanup
            print("\n[Step 3] Cleaning up...")
            client.delete_agent(agent_id)

            print("\n" + "=" * 70)
            print("✅ Multi-tool test passed!")
            print("=" * 70)

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            client.cleanup()
            raise


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
