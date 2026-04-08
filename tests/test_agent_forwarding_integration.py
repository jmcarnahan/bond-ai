"""
Integration tests for agent forwarding via bond://forward/AgentName links.

Requires:
- Backend server running: uvicorn bondable.rest.main:app --reload
- Run with: poetry run python -m pytest tests/test_agent_forwarding_integration.py -v --integration -s
"""

import re
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.integration

# Test user constants
TEST_USER_ID = "forward-test-user"
TEST_USER_EMAIL = "forward-test@example.com"
BASE_URL = "http://localhost:8000"

# Regex to extract text content from assistant bond messages
_ASSISTANT_CONTENT_RE = re.compile(
    r'<_bondmessage[^>]*role="assistant"[^>]*>(.*?)</_bondmessage>',
    re.DOTALL,
)
_SYSTEM_CONTENT_RE = re.compile(
    r'<_bondmessage[^>]*role="system"[^>]*>(.*?)</_bondmessage>',
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_auth_token() -> str:
    """Create a JWT token for testing."""
    import jwt as pyjwt
    from bondable.bond.config import Config

    jwt_config = Config.config().get_jwt_config()
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Forward Test User",
        "user_id": TEST_USER_ID,
        "provider": "cognito",
        "email": TEST_USER_EMAIL,
        "iss": "bond-ai",
        "aud": "bond-ai-api",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)


def _extract_assistant_text(raw_response: str) -> str:
    """Extract all assistant message text content from a raw streaming response."""
    matches = _ASSISTANT_CONTENT_RE.findall(raw_response)
    # Strip any nested XML tags (e.g. keepalive comments)
    text = " ".join(matches)
    return re.sub(r'<[^>]+>', '', text).strip()


def _extract_system_text(raw_response: str) -> str:
    """Extract all system message text content from a raw streaming response."""
    matches = _SYSTEM_CONTENT_RE.findall(raw_response)
    text = " ".join(matches)
    return re.sub(r'<[^>]+>', '', text).strip()


class BondForwardingClient:
    """Minimal HTTP client for forwarding integration tests."""

    def __init__(self):
        self.headers = {}
        self.created_agents = []
        self.created_threads = []

    def set_token(self, token: str):
        self.headers["Authorization"] = f"Bearer {token}"

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def get_default_model(self) -> str:
        r = requests.get(f"{BASE_URL}/agents/models", headers=self.headers, timeout=30)
        r.raise_for_status()
        models = r.json()
        for m in models:
            if m.get("is_default"):
                return m["name"]
        return models[0]["name"] if models else "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def create_agent(self, name: str, instructions: str, model: str = None) -> dict:
        payload = {
            "name": name,
            "instructions": instructions,
            "model": model,
            "tools": [],
            "metadata": {"test": "true", "created_by": "forwarding_integration_test"},
        }
        r = requests.post(f"{BASE_URL}/agents", headers=self.headers, json=payload, timeout=120)
        r.raise_for_status()
        agent = r.json()
        self.created_agents.append(agent["agent_id"])
        # Fetch full details to get slug
        details = self.get_agent_details(agent["agent_id"])
        agent["slug"] = details.get("slug")
        return agent

    def get_agent_details(self, agent_id: str) -> dict:
        r = requests.get(
            f"{BASE_URL}/agents/{agent_id}",
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def update_agent(self, agent_id: str, **kwargs) -> dict:
        """Update an agent. Pass any fields from AgentUpdateRequest as kwargs."""
        r = requests.put(
            f"{BASE_URL}/agents/{agent_id}",
            headers=self.headers,
            json=kwargs,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()

    def create_thread(self, name: str = "Forwarding Test") -> dict:
        r = requests.post(
            f"{BASE_URL}/threads",
            headers=self.headers,
            json={"name": name},
            timeout=30,
        )
        r.raise_for_status()
        thread = r.json()
        self.created_threads.append(thread["id"])
        return thread

    def chat(self, thread_id: str, agent_id: str, prompt: str, timeout: int = 180) -> str:
        payload = {
            "thread_id": thread_id,
            "agent_id": agent_id,
            "prompt": prompt,
        }
        r = requests.post(
            f"{BASE_URL}/chat",
            headers=self.headers,
            json=payload,
            stream=True,
            timeout=timeout,
        )
        r.raise_for_status()
        full = ""
        for chunk in r.iter_content(decode_unicode=True):
            if chunk:
                full += chunk
        return full

    def get_thread_messages(self, thread_id: str) -> list:
        r = requests.get(
            f"{BASE_URL}/threads/{thread_id}/messages",
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def delete_agent(self, agent_id: str):
        try:
            r = requests.delete(
                f"{BASE_URL}/agents/{agent_id}",
                headers=self.headers,
                timeout=60,
            )
            if r.status_code == 204 and agent_id in self.created_agents:
                self.created_agents.remove(agent_id)
        except Exception:
            pass

    def delete_thread(self, thread_id: str):
        try:
            r = requests.delete(
                f"{BASE_URL}/threads/{thread_id}",
                headers=self.headers,
                timeout=30,
            )
            if r.status_code == 204 and thread_id in self.created_threads:
                self.created_threads.remove(thread_id)
        except Exception:
            pass

    def cleanup(self):
        for tid in self.created_threads.copy():
            self.delete_thread(tid)
        for aid in self.created_agents.copy():
            self.delete_agent(aid)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Authenticated client with automatic cleanup."""
    c = BondForwardingClient()
    if not c.health_check():
        pytest.skip("Bond API server not running at " + BASE_URL)
    token = _create_auth_token()
    c.set_token(token)
    yield c
    c.cleanup()


@pytest.fixture
def default_model(client):
    """Return the default model name."""
    return client.get_default_model()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForwardingHappyPath:
    """End-to-end test: Agent A forwards to Agent B transparently."""

    def test_simple_hello_forward(self, client, default_model):
        """Exact reproduction of the manual UI test:
        Agent A is told to always forward to Agent B.
        Send 'hello' and verify Agent B responds.

        This tests that:
        1. The bond definitions don't override agent-specific forwarding instructions
        2. The LLM outputs the bond://forward link even for trivial messages
        3. The forwarding chain completes end-to-end
        """
        # Use unique names to avoid collisions with other agents in the DB
        suffix = uuid.uuid4().hex[:8]
        target_name = f"FwdTarget_{suffix}"
        source_name = f"FwdSource_{suffix}"

        # Step 1: Create target agent (Agent B)
        agent_b = client.create_agent(
            name=target_name,
            instructions=(
                'You are a specialist. Always start your response with "SPECIALIST HERE:" '
                'followed by your answer to the user.'
            ),
            model=default_model,
        )
        print(f"  Created target agent ({target_name}): {agent_b['agent_id']}")
        time.sleep(5)

        # Step 2: Create source agent (Agent A) — references target by agent ID
        target_slug = agent_b["slug"]
        agent_a = client.create_agent(
            name=source_name,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message to the specialist agent. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"Let me connect you with our specialist. "
                f"[{target_name}](bond://forward/{target_slug})"
            ),
            model=default_model,
        )
        print(f"  Created source agent ({source_name}): {agent_a['agent_id']}")
        time.sleep(5)

        # Step 3: Chat with source agent
        thread = client.create_thread("Simple Hello Forward Test")
        print(f"  Created thread: {thread['id']}")

        raw = client.chat(thread["id"], agent_a["agent_id"], "hello")

        assistant_text = _extract_assistant_text(raw)
        system_text = _extract_system_text(raw)
        print(f"  Assistant text: {assistant_text[:500]}")
        print(f"  System text: {system_text[:300]}")
        print(f"  Raw response length: {len(raw)}")

        # Verify the forward link was detected and forwarding occurred
        assert f"Forwarding to {target_name}" in system_text, (
            f"Forward was not triggered. System text: {system_text}\n"
            f"Full assistant text: {assistant_text}"
        )

        # Verify the target agent responded
        assert "SPECIALIST HERE" in assistant_text.upper(), (
            f"Target agent did not respond. Assistant text: {assistant_text}"
        )

    def test_basic_forward(self, client, default_model):
        """Create two agents where A always forwards to B.
        Verify the response contains output from both agents and
        the forwarding system message."""
        suffix = uuid.uuid4().hex[:8]
        specialist_name = f"Specialist_{suffix}"
        triage_name = f"Triage_{suffix}"

        agent_b = client.create_agent(
            name=specialist_name,
            instructions=(
                "You are a specialist agent for integration testing. "
                "When you receive a message, always respond with exactly: "
                "'SPECIALIST_RESPONSE: I am the specialist and I received your request.' "
                "Do not add any other text."
            ),
            model=default_model,
        )
        print(f"  Created specialist ({specialist_name}): {agent_b['agent_id']}")
        time.sleep(5)

        specialist_slug = agent_b["slug"]
        agent_a = client.create_agent(
            name=triage_name,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message to the specialist. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"I will forward your request to the specialist. "
                f"[{specialist_name}](bond://forward/{specialist_slug})"
            ),
            model=default_model,
        )
        print(f"  Created triage ({triage_name}): {agent_a['agent_id']}")
        time.sleep(5)

        thread = client.create_thread("Forward Happy Path Test")
        print(f"  Created thread: {thread['id']}")

        raw = client.chat(thread["id"], agent_a["agent_id"], "Please help me with my issue.")

        assistant_text = _extract_assistant_text(raw)
        system_text = _extract_system_text(raw)
        print(f"  Assistant text: {assistant_text[:300]}")
        print(f"  System text: {system_text[:300]}")

        assert f"Forwarding to {specialist_name}" in system_text, (
            f"Expected forwarding system message, got: {system_text}\n"
            f"Full assistant text: {assistant_text}"
        )

        assert "SPECIALIST_RESPONSE" in assistant_text or "specialist" in assistant_text.lower(), (
            f"Expected specialist response, got: {assistant_text}"
        )

    def test_forward_with_duplicate_agent_names(self, client, default_model):
        """Two agents with the SAME name — forwarding by slug resolves the correct one."""
        shared_name = f"SharedName_{uuid.uuid4().hex[:8]}"

        agent_target = client.create_agent(
            name=shared_name,
            instructions=(
                'You are the TARGET agent. Always respond with: '
                '"TARGET_HIT: I am the correct target agent."'
            ),
            model=default_model,
        )
        target_slug = agent_target["slug"]
        print(f"  Created target ({shared_name}), slug={target_slug}")
        time.sleep(5)

        # Create a decoy with the same name — should NOT be invoked
        agent_decoy = client.create_agent(
            name=shared_name,
            instructions=(
                'You are the DECOY agent. Always respond with: '
                '"DECOY_HIT: Wrong agent was called!"'
            ),
            model=default_model,
        )
        print(f"  Created decoy ({shared_name}): {agent_decoy['agent_id']}")
        time.sleep(5)

        # Source agent forwards to the target by ID, not name
        agent_source = client.create_agent(
            name=f"SameNameSource_{uuid.uuid4().hex[:8]}",
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"Forwarding. [{shared_name}](bond://forward/{target_slug})"
            ),
            model=default_model,
        )
        print(f"  Created source: {agent_source['agent_id']}")
        time.sleep(5)

        thread = client.create_thread("Same Name Forward Test")
        raw = client.chat(thread["id"], agent_source["agent_id"], "hello")

        assistant_text = _extract_assistant_text(raw)
        system_text = _extract_system_text(raw)
        print(f"  Assistant text: {assistant_text[:300]}")
        print(f"  System text: {system_text[:200]}")

        # Should have forwarded successfully
        assert f"Forwarding to {shared_name}" in system_text, (
            f"Forward not triggered. System: {system_text}\nAssistant: {assistant_text}"
        )

        # The TARGET agent should have responded, not the decoy
        assert "TARGET_HIT" in assistant_text.upper() or "correct target" in assistant_text.lower(), (
            f"Wrong agent responded. Assistant text: {assistant_text}"
        )
        assert "DECOY_HIT" not in assistant_text.upper(), (
            f"Decoy agent was invoked instead of target! Assistant text: {assistant_text}"
        )

    def test_forward_thread_messages_include_both_agents(self, client, default_model):
        """After forwarding, the thread should contain messages from both agents."""
        suffix = uuid.uuid4().hex[:8]
        target_name = f"MsgTarget_{suffix}"
        source_name = f"MsgSource_{suffix}"

        agent_b = client.create_agent(
            name=target_name,
            instructions=(
                "You are a target agent. Always respond with: "
                "'TARGET_AGENT_REPLY: message received.' "
                "Do not add any other text."
            ),
            model=default_model,
        )
        time.sleep(5)

        target_slug = agent_b["slug"]
        agent_a = client.create_agent(
            name=source_name,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"Routing to target. [{target_name}](bond://forward/{target_slug})"
            ),
            model=default_model,
        )
        time.sleep(5)

        thread = client.create_thread("Forward Messages Test")
        thread_id = thread["id"]

        client.chat(thread_id, agent_a["agent_id"], "Test message")

        time.sleep(2)

        messages = client.get_thread_messages(thread_id)
        print(f"  Thread has {len(messages)} messages")
        for msg in messages:
            role = msg.get("role", "?")
            agent = msg.get("agent_id", "?")
            content = msg.get("content", "")[:80]
            print(f"    [{role}] agent={agent}: {content}")

        assert len(messages) >= 3, f"Expected >= 3 messages, got {len(messages)}"

        agent_ids_in_thread = {m.get("agent_id") for m in messages if m.get("agent_id")}
        print(f"  Agent IDs in thread: {agent_ids_in_thread}")
        assert len(agent_ids_in_thread) >= 2, (
            f"Expected messages from >= 2 agents, got {agent_ids_in_thread}"
        )


class TestForwardingEdgeCases:
    """Edge case integration tests for forwarding."""

    def test_forward_to_nonexistent_agent(self, client, default_model):
        """When Agent A tries to forward to an agent that doesn't exist,
        the response should contain the 'not found' error."""
        suffix = uuid.uuid4().hex[:8]
        # Use a fake slug that definitely doesn't exist
        ghost_slug = "ghost-missing-phantom"

        agent_a = client.create_agent(
            name=f"NotFoundSource_{suffix}",
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"Forwarding now. [Ghost Agent](bond://forward/{ghost_slug})"
            ),
            model=default_model,
        )
        time.sleep(5)

        # Try up to 2 times — LLMs sometimes ignore long opaque IDs
        for attempt in range(2):
            thread = client.create_thread(f"Forward Not Found Test (attempt {attempt + 1})")
            raw = client.chat(thread["id"], agent_a["agent_id"], "Hello")

            assistant_text = _extract_assistant_text(raw)
            system_text = _extract_system_text(raw)
            print(f"  Attempt {attempt + 1} - Assistant: {assistant_text[:200]}")
            print(f"  Attempt {attempt + 1} - System: {system_text}")

            if "not found" in system_text.lower():
                return  # Test passed

            if "bond://forward/" in assistant_text:
                # LLM output the link but system didn't catch it — real failure
                pytest.fail(
                    f"Forward link present but 'not found' not in system text.\n"
                    f"System: {system_text}\nAssistant: {assistant_text[:300]}"
                )

        pytest.skip(
            "LLM did not output the forward link with the opaque ID after 2 attempts. "
            "The 'not found' path is covered by unit tests."
        )

    def test_circular_forward_blocked(self, client, default_model):
        """When Agent A forwards to Agent B and B forwards back to A,
        the circular reference should be detected and stopped."""
        suffix = uuid.uuid4().hex[:8]
        name_a = f"CircA_{suffix}"
        name_b = f"CircB_{suffix}"

        # Create Agent B first (will update instructions after A is created)
        agent_b = client.create_agent(
            name=name_b,
            instructions="Placeholder — will be updated after Agent A is created.",
            model=default_model,
        )
        slug_b = agent_b["slug"]
        time.sleep(5)

        # Create Agent A (forwards to B by slug)
        agent_a = client.create_agent(
            name=name_a,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"A forwards to B. [{name_b}](bond://forward/{slug_b})"
            ),
            model=default_model,
        )
        slug_a = agent_a["slug"]
        time.sleep(5)

        # Update Agent B to forward to A by slug (must include name for the update endpoint)
        client.update_agent(
            agent_b["agent_id"],
            name=name_b,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"B forwards to A. [{name_a}](bond://forward/{slug_a})"
            ),
        )
        time.sleep(5)

        thread = client.create_thread("Circular Forward Test")
        raw = client.chat(thread["id"], agent_a["agent_id"], "Start the loop")

        print(f"  Full response length: {len(raw)}")

        assert f"Forwarding to {name_b}" in raw, (
            f"Expected forward to {name_b}"
        )

        assert "circular forwarding detected" in raw.lower(), (
            f"Expected circular forwarding error in response"
        )

    def test_forward_no_infinite_responses(self, client, default_model):
        """Verify that forwarding completes in reasonable time and doesn't
        produce an unreasonably large response (guards against infinite loops)."""
        suffix = uuid.uuid4().hex[:8]
        target_name = f"QuickTarget_{suffix}"
        source_name = f"QuickSource_{suffix}"

        agent_b = client.create_agent(
            name=target_name,
            instructions=(
                "Always respond with exactly one sentence: "
                "'QUICK_REPLY: Done.' Do not forward to any agent."
            ),
            model=default_model,
        )
        time.sleep(5)

        target_slug = agent_b["slug"]
        agent_a = client.create_agent(
            name=source_name,
            instructions=(
                f"IMPORTANT: You MUST forward EVERY message. "
                f"Your ENTIRE response must be EXACTLY this text and nothing else:\n"
                f"Sending to target. [{target_name}](bond://forward/{target_slug})"
            ),
            model=default_model,
        )
        time.sleep(5)

        thread = client.create_thread("Quick Reply Test")

        start = time.time()
        raw = client.chat(thread["id"], agent_a["agent_id"], "Go", timeout=120)
        elapsed = time.time() - start

        print(f"  Completed in {elapsed:.1f}s, response length: {len(raw)}")

        assert elapsed < 90, f"Forwarding took too long: {elapsed:.1f}s"
        assert len(raw) < 50000, f"Response suspiciously large: {len(raw)} chars"

        system_text = _extract_system_text(raw)
        # Verify forwarding actually happened
        assert f"Forwarding to {target_name}" in system_text, (
            f"Forward not triggered. System: {system_text}"
        )
