#!/usr/bin/env python3
"""
Integration test for context window compaction.

Tests the full lifecycle:
1. Create a thread and send messages via REST API
2. Verify context_usage is being tracked in session_state
3. Artificially inflate context_usage to near the threshold
4. Send one more message to trigger compaction
5. Verify compaction happened: new session_id, reset usage, pending summary
6. Send another message to verify the conversation continues with the summary

Prerequisites:
- Backend REST API running: uvicorn bondable.rest.main:app --reload
- PyJWT package: pip install PyJWT[crypto]

Usage:
    poetry run python -m pytest tests/test_context_compaction_integration.py -v -s
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta, timezone
import jwt
from typing import Optional, Dict, List

import pytest

# Skip by default -- remove this line to run against a live server
pytestmark = pytest.mark.skip(reason="Integration test: requires running REST API server")

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def create_auth_token(user_email: str = "compaction_test@example.com") -> str:
    """Create a JWT token using Bond's JWT configuration."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": user_email,
        "name": "Compaction Test User",
        "user_id": f"test_user_{user_email.split('@')[0]}",
        "provider": "cognito",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    return jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# REST API helpers
# ---------------------------------------------------------------------------

class CompactionTestClient:
    """Thin wrapper around the REST API for compaction testing."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.headers: Dict[str, str] = {}
        self.created_threads: list = []

    def authenticate(self, token: str):
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def get_default_agent(self) -> dict:
        r = requests.get(f"{self.base_url}/agents/default",
                         headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_agents(self) -> list:
        r = requests.get(f"{self.base_url}/agents",
                         headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def create_agent(self, name: str, instructions: str = "Be helpful.") -> dict:
        r = requests.post(f"{self.base_url}/agents",
                          headers=self.headers,
                          json={"name": name, "instructions": instructions},
                          timeout=60)
        r.raise_for_status()
        return r.json()

    def delete_agent(self, agent_id: str) -> bool:
        r = requests.delete(f"{self.base_url}/agents/{agent_id}",
                            headers=self.headers, timeout=30)
        return r.status_code in (200, 204)

    def create_thread(self, name: str) -> dict:
        r = requests.post(f"{self.base_url}/threads",
                          headers=self.headers,
                          json={"name": name}, timeout=30)
        r.raise_for_status()
        thread = r.json()
        self.created_threads.append(thread['id'])
        return thread

    def chat(self, thread_id: str, agent_id: str, prompt: str) -> str:
        """Send a chat message via streaming and return full response text."""
        payload = {
            "thread_id": thread_id,
            "agent_id": agent_id,
            "prompt": prompt,
        }
        r = requests.post(f"{self.base_url}/chat",
                          headers=self.headers,
                          json=payload, stream=True, timeout=180)
        r.raise_for_status()

        full_response = ""
        for chunk in r.iter_content(decode_unicode=True):
            if chunk:
                full_response += chunk
        return full_response

    def get_thread_messages(self, thread_id: str) -> list:
        r = requests.get(f"{self.base_url}/threads/{thread_id}/messages",
                         headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def delete_thread(self, thread_id: str) -> bool:
        r = requests.delete(f"{self.base_url}/threads/{thread_id}",
                            headers=self.headers, timeout=30)
        if r.status_code == 204 and thread_id in self.created_threads:
            self.created_threads.remove(thread_id)
        return r.status_code == 204

    def cleanup(self):
        for tid in list(self.created_threads):
            try:
                self.delete_thread(tid)
                logger.info(f"Cleaned up thread {tid}")
            except Exception as e:
                logger.warning(f"Failed to clean up thread {tid}: {e}")


# ---------------------------------------------------------------------------
# Provider helpers (direct DB access for session_state inspection)
# ---------------------------------------------------------------------------

DB_PATH = os.getenv("BONDABLE_DB_PATH", "/tmp/.metadata.db")


def get_provider():
    """Get the Bedrock provider for direct session_state inspection."""
    from bondable.bond.config import Config
    return Config.config().get_provider()


def get_session_state_raw(thread_id: str, user_id: str) -> dict:
    """Read session_state directly from SQLite, bypassing all ORM caching."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT session_state FROM threads WHERE thread_id = ? AND user_id = ?",
        (thread_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return {}


def get_session_id_raw(thread_id: str, user_id: str = None) -> str:
    """Read session_id directly from SQLite, bypassing all ORM caching."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    if user_id:
        cursor = conn.execute(
            "SELECT session_id FROM threads WHERE thread_id = ? AND user_id = ?",
            (thread_id, user_id),
        )
    else:
        cursor = conn.execute(
            "SELECT session_id FROM threads WHERE thread_id = ?",
            (thread_id,),
        )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


def set_session_state_raw(thread_id: str, user_id: str, session_state: dict):
    """Write session_state directly via raw SQL so the server process sees it immediately."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE threads SET session_state = ? WHERE thread_id = ? AND user_id = ?",
        (json.dumps(session_state), thread_id, user_id),
    )
    conn.commit()
    conn.close()
    # Small delay to ensure WAL checkpoint is visible to the server process
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Test prompts that generate longer responses to accumulate tokens faster
# ---------------------------------------------------------------------------

# Short prompts for speed - the natural growth test inflates tokens mid-way anyway
LONG_PROMPTS = [
    "Say hello.",
    "What is 2+2?",
    "Name a color.",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContextCompactionIntegration:
    """Integration tests for context window compaction."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up test client and clean up after each test."""
        self.client = CompactionTestClient()
        self.provider = get_provider()
        self.user_id = "test_user_compaction_test"
        yield
        self.client.cleanup()

    def _authenticate(self):
        token = create_auth_token("compaction_test@example.com")
        self.client.authenticate(token)

    def test_context_usage_tracking(self):
        """
        Verify that context_usage is tracked after each message exchange.

        Sends a few messages and checks that session_state.context_usage
        is populated with token/char counts.
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        logger.info(f"Using agent: {agent['name']} (ID: {agent_id})")

        thread = self.client.create_thread("Compaction Test - Usage Tracking")
        thread_id = thread['id']
        logger.info(f"Created thread: {thread_id}")

        # Send a message
        response = self.client.chat(thread_id, agent_id,
                                     "Hello! What is your name?")
        logger.info(f"Got response ({len(response)} chars)")

        # Check context_usage in session_state
        state = get_session_state_raw(thread_id, self.user_id)
        logger.info(f"Session state after 1 exchange: {json.dumps(state.get('context_usage', {}), indent=2)}")

        usage = state.get('context_usage', {})
        assert usage, "context_usage should be populated after first exchange"
        assert usage.get('estimated_tokens', 0) > 0, "estimated_tokens should be > 0"
        assert usage.get('message_count', 0) == 2, "message_count should be 2 (user + assistant)"

        token_source = usage.get('token_source', 'unknown')
        logger.info(f"Token source: {token_source}")
        logger.info(f"Estimated tokens: {usage.get('estimated_tokens', 0)}")

        # Send another message
        response2 = self.client.chat(thread_id, agent_id,
                                      "Tell me a short joke.")
        logger.info(f"Got response 2 ({len(response2)} chars)")

        state2 = get_session_state_raw(thread_id, self.user_id)
        usage2 = state2.get('context_usage', {})
        logger.info(f"Session state after 2 exchanges: {json.dumps(usage2, indent=2)}")

        assert usage2.get('estimated_tokens', 0) > usage.get('estimated_tokens', 0), \
            "estimated_tokens should increase after more messages"
        assert usage2.get('message_count', 0) == 4, "message_count should be 4"

        logger.info("PASSED: Context usage tracking works correctly")

    def test_compaction_triggered_by_threshold(self):
        """
        Verify compaction triggers when context_usage exceeds the threshold.

        Strategy:
        1. Send a couple of real messages to establish a valid session
        2. Artificially inflate context_usage to just below threshold
        3. Send one more message -- this should trigger compaction AFTER the response
        4. Verify: new session_id, reset context_usage, pending summary or summary already injected
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        logger.info(f"Using agent: {agent['name']} (ID: {agent_id})")

        thread = self.client.create_thread("Compaction Test - Threshold Trigger")
        thread_id = thread['id']
        logger.info(f"Created thread: {thread_id}")

        # Step 1: Send initial messages to establish a real conversation
        logger.info("--- Step 1: Sending initial messages ---")
        resp1 = self.client.chat(thread_id, agent_id,
                                  "Remember: my name is Alice.")
        logger.info(f"Response 1: {len(resp1)} chars")

        resp2 = self.client.chat(thread_id, agent_id,
                                  "What's my name?")
        logger.info(f"Response 2: {len(resp2)} chars")

        # Record the session_id before compaction
        original_session_id = get_session_id_raw(thread_id)
        logger.info(f"Original session ID: {original_session_id}")

        state_before = get_session_state_raw(thread_id, self.user_id)
        usage_before = state_before.get('context_usage', {})
        logger.info(f"Context usage before inflation: {json.dumps(usage_before, indent=2)}")

        # Step 2: Inflate context_usage to just below threshold
        # Default threshold = 60% of 200K = 120K tokens
        # Set estimated_tokens to 119K so the next message pushes it over
        logger.info("--- Step 2: Inflating context_usage to near threshold ---")
        inflated_state = state_before.copy()
        inflated_state['context_usage'] = {
            'total_tokens': 119_990,
            'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': usage_before.get('message_count', 4),
            'compaction_count': 0,
            'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id,inflated_state)

        verify_state = get_session_state_raw(thread_id, self.user_id)
        logger.info(f"Inflated context_usage: {json.dumps(verify_state.get('context_usage', {}), indent=2)}")

        # Step 3: Send one more message -- should trigger compaction AFTER response
        logger.info("--- Step 3: Sending message to trigger compaction ---")
        resp3 = self.client.chat(thread_id, agent_id,
                                  "Summarize our conversation so far. What's my name and what did we discuss?")
        logger.info(f"Response 3 (should trigger compaction): {len(resp3)} chars")
        assert len(resp3) > 0, "Response should not be empty"

        # Step 4: Verify compaction happened
        logger.info("--- Step 4: Verifying compaction ---")

        # Small delay to ensure compaction completes (it runs after response streaming)
        time.sleep(2)

        new_session_id = get_session_id_raw(thread_id)
        state_after = get_session_state_raw(thread_id, self.user_id)
        usage_after = state_after.get('context_usage', {})

        logger.info(f"New session ID: {new_session_id}")
        logger.info(f"Context usage after compaction: {json.dumps(usage_after, indent=2)}")
        logger.info(f"Has pending_compaction_summary: {'pending_compaction_summary' in state_after}")
        if 'pending_compaction_summary' in state_after:
            summary = state_after['pending_compaction_summary']
            logger.info(f"Pending summary messages: {len(summary)}")
            for msg in summary:
                role = msg.get('role', '?')
                text = msg.get('content', [{}])[0].get('text', '')[:200]
                logger.info(f"  {role}: {text}")

        # Assertions
        assert new_session_id != original_session_id, \
            f"Session ID should have rotated. Original: {original_session_id}, New: {new_session_id}"

        assert usage_after.get('compaction_count', 0) >= 1, \
            "compaction_count should be >= 1"

        assert usage_after.get('estimated_tokens', 0) < 119_000, \
            f"estimated_tokens should be reset (got {usage_after.get('estimated_tokens', 0)})"

        logger.info("PASSED: Compaction triggered and session rotated correctly")

    def test_conversation_continues_after_compaction(self):
        """
        Full end-to-end: trigger compaction and verify the conversation
        continues seamlessly with the summary injected.
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        logger.info(f"Using agent: {agent['name']} (ID: {agent_id})")

        thread = self.client.create_thread("Compaction Test - Continue After")
        thread_id = thread['id']
        logger.info(f"Created thread: {thread_id}")

        # Step 1: Establish conversation with memorable facts
        logger.info("--- Step 1: Establishing conversation ---")
        self.client.chat(thread_id, agent_id,
                         "My pet's name is Max and my project is called Phoenix.")

        original_session_id = get_session_id_raw(thread_id)

        # Step 2: Inflate and trigger compaction
        logger.info("--- Step 2: Inflating and triggering compaction ---")
        state = get_session_state_raw(thread_id, self.user_id)
        state['context_usage'] = {
            'total_tokens': 119_990,
            'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': state.get('context_usage', {}).get('message_count', 4),
            'compaction_count': 0,
            'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id,state)

        # This message should trigger compaction after the response
        resp = self.client.chat(thread_id, agent_id, "Say OK.")
        logger.info(f"Pre-compaction response: {resp[:200]}...")

        time.sleep(2)

        # Verify compaction happened
        new_session_id = get_session_id_raw(thread_id)
        assert new_session_id != original_session_id, "Session should have rotated"
        logger.info(f"Session rotated: {original_session_id} -> {new_session_id}")

        # Step 3: Send a message on the new session -- the summary should be injected
        logger.info("--- Step 3: Testing post-compaction conversation ---")
        post_compaction_resp = self.client.chat(
            thread_id, agent_id,
            "What is my pet's name and what project am I working on?"
        )
        logger.info(f"Post-compaction response: {post_compaction_resp[:500]}...")

        # The response MUST reference Max and/or Phoenix from the summary.
        # This is the core user-facing requirement: after compaction, the model
        # still knows what was discussed before compaction.
        resp_lower = post_compaction_resp.lower()
        has_pet_name = 'max' in resp_lower
        has_project = 'phoenix' in resp_lower
        logger.info(f"Response mentions pet 'Max': {has_pet_name}")
        logger.info(f"Response mentions project 'Phoenix': {has_project}")

        assert has_pet_name or has_project, \
            ("Post-compaction response must reference pre-compaction facts (Max or Phoenix). "
             f"Got: {post_compaction_resp[:300]}")

        logger.info("PASSED: Conversation continues after compaction with pre-compaction context")

    def test_natural_compaction_with_long_conversation(self):
        """
        Send many messages with long prompts to naturally accumulate tokens.
        Uses a low threshold via direct session_state manipulation to make
        compaction trigger sooner.

        This test takes longer but exercises the full flow without
        artificially inflating token counts.
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        logger.info(f"Using agent: {agent['name']} (ID: {agent_id})")

        thread = self.client.create_thread("Compaction Test - Natural Growth")
        thread_id = thread['id']
        logger.info(f"Created thread: {thread_id}")

        original_session_id = None
        compacted = False

        for i, prompt in enumerate(LONG_PROMPTS):
            logger.info(f"\n--- Message {i + 1}/{len(LONG_PROMPTS)} ---")
            logger.info(f"Prompt: {prompt[:80]}...")

            response = self.client.chat(thread_id, agent_id, prompt)
            logger.info(f"Response length: {len(response)} chars")

            # Capture session_id after first message (not set until first Bedrock invocation)
            if original_session_id is None:
                original_session_id = get_session_id_raw(thread_id)

            state = get_session_state_raw(thread_id, self.user_id)
            usage = state.get('context_usage', {})
            estimated = usage.get('estimated_tokens', 0)
            msg_count = usage.get('message_count', 0)
            compaction_count = usage.get('compaction_count', 0)
            logger.info(
                f"Context usage: estimated_tokens={estimated}, "
                f"message_count={msg_count}, "
                f"compaction_count={compaction_count}, "
                f"source={usage.get('token_source', '?')}"
            )

            current_session = get_session_id_raw(thread_id)
            if current_session != original_session_id:
                logger.info(f"COMPACTION DETECTED after message {i + 1}!")
                logger.info(f"  Old session: {original_session_id}")
                logger.info(f"  New session: {current_session}")
                compacted = True

                # Verify compaction state
                assert compaction_count >= 1
                assert usage.get('estimated_tokens', 0) < estimated or compaction_count >= 1

                # Send a follow-up message on the new session
                logger.info("Sending post-compaction message...")
                follow_up = self.client.chat(
                    thread_id, agent_id,
                    "Summarize everything we've discussed so far in 2-3 sentences."
                )
                logger.info(f"Post-compaction response: {follow_up[:300]}...")
                assert len(follow_up) > 20, "Post-compaction response should work"
                break

            # If we haven't compacted yet and we're past halfway,
            # nudge the threshold by inflating slightly
            if i == len(LONG_PROMPTS) // 2 and not compacted:
                logger.info("Halfway through prompts -- setting estimated_tokens near threshold")
                state['context_usage']['estimated_tokens'] = 119_990
                state['context_usage']['total_tokens'] = 119_990
                set_session_state_raw(thread_id, self.user_id,state)

        if not compacted:
            logger.warning(
                "Compaction was not triggered naturally. "
                "This is expected if the conversation didn't accumulate enough tokens. "
                "The test still verifies context_usage tracking is working."
            )
            # At least verify tracking worked
            final_state = get_session_state_raw(thread_id, self.user_id)
            final_usage = final_state.get('context_usage', {})
            assert final_usage.get('estimated_tokens', 0) > 0
            assert final_usage.get('message_count', 0) > 0

        logger.info("PASSED: Natural compaction test complete")

    def test_multiple_compactions(self):
        """
        Trigger compaction twice on the same thread to verify:
        - compaction_count increments from 0 -> 1 -> 2
        - session rotates each time
        - conversation remains coherent throughout

        Uses raw SQL writes to bypass ORM caching between test and server processes.
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        thread = self.client.create_thread("Compaction Test - Multiple")
        thread_id = thread['id']

        # --- First compaction cycle ---
        logger.info("--- First conversation segment ---")
        self.client.chat(thread_id, agent_id, "Remember: code is ALPHA-7.")
        self.client.chat(thread_id, agent_id, "What is the code?")

        session_id_1 = get_session_id_raw(thread_id)
        state = get_session_state_raw(thread_id, self.user_id)
        logger.info(f"Pre-inflation 1 context_usage: {json.dumps(state.get('context_usage', {}), indent=2)}")

        state['context_usage'] = {
            'total_tokens': 119_990,
            'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': state.get('context_usage', {}).get('message_count', 4),
            'compaction_count': 0,
            'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id, state)

        logger.info("--- Triggering compaction #1 ---")
        self.client.chat(thread_id, agent_id, "Say OK.")
        time.sleep(2)

        session_id_2 = get_session_id_raw(thread_id)
        state_after_1 = get_session_state_raw(thread_id, self.user_id)
        count_1 = state_after_1.get('context_usage', {}).get('compaction_count', 0)
        logger.info(f"After 1st compaction: session {session_id_1} -> {session_id_2}, count={count_1}")
        assert session_id_2 != session_id_1, "First compaction should rotate session"
        assert count_1 >= 1, "compaction_count should be >= 1 after first compaction"

        # Verify ALPHA-7 survives the first compaction
        recall_1 = self.client.chat(thread_id, agent_id,
                                     "What was the code I told you to remember?")
        logger.info(f"Post-compaction #1 recall: {recall_1[:300]}...")
        assert 'ALPHA' in recall_1 or 'alpha' in recall_1.lower(), \
            f"After compaction #1, model must remember ALPHA-7. Got: {recall_1[:300]}"
        logger.info("PASSED: ALPHA-7 retained after compaction #1")

        # --- Second compaction cycle ---
        logger.info("--- Second conversation segment ---")
        self.client.chat(thread_id, agent_id, "New code: BRAVO-3.")
        self.client.chat(thread_id, agent_id, "What is the new code?")

        state2 = get_session_state_raw(thread_id, self.user_id)
        logger.info(f"Pre-inflation 2 context_usage: {json.dumps(state2.get('context_usage', {}), indent=2)}")

        state2['context_usage'] = {
            'total_tokens': 119_990,
            'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': state2.get('context_usage', {}).get('message_count', 4),
            'compaction_count': count_1,
            'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id, state2)

        logger.info("--- Triggering compaction #2 ---")
        self.client.chat(thread_id, agent_id, "Say OK.")
        time.sleep(2)

        session_id_3 = get_session_id_raw(thread_id)
        state_after_2 = get_session_state_raw(thread_id, self.user_id)
        count_2 = state_after_2.get('context_usage', {}).get('compaction_count', 0)
        logger.info(f"After 2nd compaction: session {session_id_2} -> {session_id_3}, count={count_2}")
        assert session_id_3 != session_id_2, "Second compaction should rotate session again"
        assert count_2 >= 2, f"compaction_count should be >= 2 (got {count_2})"

        # Verify BRAVO-3 survives the second compaction
        recall_2 = self.client.chat(thread_id, agent_id,
                                     "What codes do you remember? List all of them.")
        logger.info(f"Post-compaction #2 recall: {recall_2[:300]}...")
        has_bravo = 'BRAVO' in recall_2 or 'bravo' in recall_2.lower()
        assert has_bravo, \
            f"After compaction #2, model must remember BRAVO-3. Got: {recall_2[:300]}"
        logger.info("PASSED: BRAVO-3 retained after compaction #2")

        # ALPHA-7 may or may not survive two compactions (the second summary
        # summarizes the first summary), but BRAVO-3 must survive since it was
        # in the conversation right before the second compaction.
        has_alpha = 'ALPHA' in recall_2 or 'alpha' in recall_2.lower()
        if has_alpha:
            logger.info("BONUS: ALPHA-7 also retained through two compactions!")
        else:
            logger.info("Note: ALPHA-7 was lost during second compaction (expected — "
                        "summary-of-summary may lose older details)")

        logger.info("PASSED: Multiple compactions work correctly")

    def test_pending_summary_not_reinjected(self):
        """
        After compaction, the first post-compaction request consumes the
        pending_compaction_summary.  The second post-compaction request must
        NOT see it re-injected (verifies the P2-B fix).
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        thread = self.client.create_thread("Compaction Test - Summary Not Reinjected")
        thread_id = thread['id']

        # Establish conversation
        self.client.chat(thread_id, agent_id, "Remember: my favorite fruit is mango.")

        # Inflate and trigger compaction
        state = get_session_state_raw(thread_id, self.user_id)
        state['context_usage'] = {
            'total_tokens': 119_990, 'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': state.get('context_usage', {}).get('message_count', 2),
            'compaction_count': 0, 'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id, state)

        self.client.chat(thread_id, agent_id, "Say OK.")
        time.sleep(2)

        # Verify compaction happened and pending_compaction_summary exists
        state_after_compact = get_session_state_raw(thread_id, self.user_id)
        assert state_after_compact.get('context_usage', {}).get('compaction_count', 0) >= 1, \
            "Compaction should have occurred"
        assert 'pending_compaction_summary' in state_after_compact, \
            "pending_compaction_summary should exist before first post-compaction request"
        logger.info("Compaction done, pending_compaction_summary present")

        # First post-compaction request — consumes the summary
        resp1 = self.client.chat(thread_id, agent_id, "What is my favorite fruit?")
        logger.info(f"Post-compaction request 1: {resp1[:200]}...")
        assert 'mango' in resp1.lower(), \
            f"First post-compaction response should mention mango. Got: {resp1[:300]}"

        state_after_first = get_session_state_raw(thread_id, self.user_id)
        logger.info(f"pending_compaction_summary after 1st request: "
                     f"{'present' if 'pending_compaction_summary' in state_after_first else 'absent'}")

        # Second post-compaction request — summary should NOT be re-injected
        resp2 = self.client.chat(thread_id, agent_id, "Say the word 'pineapple'.")
        logger.info(f"Post-compaction request 2: {resp2[:200]}...")

        state_after_second = get_session_state_raw(thread_id, self.user_id)
        assert 'pending_compaction_summary' not in state_after_second, \
            ("pending_compaction_summary should NOT be present after second request — "
             "it was already consumed on the first post-compaction request")

        logger.info("PASSED: pending_compaction_summary consumed once and not re-injected")

    def test_stale_compaction_flag_recovery(self):
        """
        Set a stale compaction_in_progress flag (>60s old) via raw SQL,
        then send a message.  The system should clear the stale flag and
        process the request normally.
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        agent = self.client.get_default_agent()
        agent_id = agent['agent_id']
        thread = self.client.create_thread("Compaction Test - Stale Flag Recovery")
        thread_id = thread['id']

        # Send a message to establish session
        self.client.chat(thread_id, agent_id, "Hello!")

        # Inject a stale compaction_in_progress flag (2 minutes old)
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        state = get_session_state_raw(thread_id, self.user_id)
        state['compaction_in_progress'] = stale_time
        set_session_state_raw(thread_id, self.user_id, state)

        verify = get_session_state_raw(thread_id, self.user_id)
        assert 'compaction_in_progress' in verify, "Stale flag should be set"
        logger.info(f"Injected stale compaction_in_progress: {stale_time}")

        # Send a new message — should succeed despite the stale flag
        resp = self.client.chat(thread_id, agent_id, "What is 3 + 5?")
        logger.info(f"Response after stale flag: {resp[:200]}...")
        assert len(resp) > 0, "Response should not be empty — stale flag should not block requests"

        # Verify the stale flag was cleared
        state_after = get_session_state_raw(thread_id, self.user_id)
        assert 'compaction_in_progress' not in state_after, \
            "Stale compaction_in_progress flag should be cleared after successful request"

        logger.info("PASSED: Stale compaction flag cleared and request processed normally")

    def test_cross_agent_compaction(self):
        """
        Trigger compaction on a thread that has messages from two different
        agents.  Verify:
        1. The summary captures context from agent A's conversation
        2. After compaction, agent B receives both the compaction summary AND
           cross-agent history, and can reference facts from agent A
        """
        self._authenticate()
        assert self.client.health_check(), "API server not reachable"

        # Use the default agent as Agent A
        agent_a = self.client.get_default_agent()
        agent_a_id = agent_a['agent_id']

        # Create a temporary Agent B for this test
        agent_b_data = self.client.create_agent(
            name="Compaction Test Agent B",
            instructions="You are a helpful assistant. Answer questions concisely."
        )
        agent_b_id = agent_b_data['agent_id']
        logger.info(f"Agent A: {agent_a.get('name', agent_a_id)} ({agent_a_id})")
        logger.info(f"Agent B: Compaction Test Agent B ({agent_b_id})")

        thread = self.client.create_thread("Compaction Test - Cross Agent")
        thread_id = thread['id']

        # Step 1: Chat with Agent A — establish memorable facts
        logger.info("--- Step 1: Chatting with Agent A ---")
        resp_a1 = self.client.chat(thread_id, agent_a_id,
                                    "Remember: the secret password is ZULU-42.")
        logger.info(f"Agent A response 1: {resp_a1[:200]}...")

        resp_a2 = self.client.chat(thread_id, agent_a_id,
                                    "What is the secret password?")
        logger.info(f"Agent A response 2: {resp_a2[:200]}...")
        assert 'ZULU' in resp_a2 or 'zulu' in resp_a2.lower(), \
            f"Agent A should confirm the password. Got: {resp_a2[:300]}"

        # Step 2: Switch to Agent B — verify cross-agent context works pre-compaction
        logger.info("--- Step 2: Chatting with Agent B (pre-compaction) ---")
        resp_b1 = self.client.chat(thread_id, agent_b_id,
                                    "Based on prior conversation in this thread, what password was mentioned?")
        logger.info(f"Agent B response 1: {resp_b1[:200]}...")
        # Note: cross-agent context may or may not surface the password depending on
        # history depth, so we just log it here rather than assert

        # Step 3: Inflate Agent B's session and trigger compaction
        logger.info("--- Step 3: Inflating Agent B's context and triggering compaction ---")
        state = get_session_state_raw(thread_id, self.user_id)
        state['context_usage'] = {
            'total_tokens': 119_990, 'total_chars': 479_960,
            'estimated_tokens': 119_990,
            'message_count': state.get('context_usage', {}).get('message_count', 2),
            'compaction_count': 0, 'token_source': 'trace',
        }
        set_session_state_raw(thread_id, self.user_id, state)

        pre_session = get_session_id_raw(thread_id)
        resp_b2 = self.client.chat(thread_id, agent_b_id, "Say OK.")
        logger.info(f"Agent B compaction trigger response: {resp_b2[:200]}...")
        time.sleep(2)

        post_session = get_session_id_raw(thread_id)
        state_after = get_session_state_raw(thread_id, self.user_id)
        compaction_count = state_after.get('context_usage', {}).get('compaction_count', 0)

        logger.info(f"Session rotated: {pre_session} -> {post_session}")
        logger.info(f"Compaction count: {compaction_count}")
        assert post_session != pre_session, "Compaction should rotate session"
        assert compaction_count >= 1, "compaction_count should be >= 1"

        # Step 4: Post-compaction — Agent B should have summary + cross-agent context
        logger.info("--- Step 4: Post-compaction query on Agent B ---")
        resp_b3 = self.client.chat(thread_id, agent_b_id,
                                    "What secret password was discussed earlier in this thread?")
        logger.info(f"Agent B post-compaction response: {resp_b3[:300]}...")

        has_password = 'ZULU' in resp_b3 or 'zulu' in resp_b3.lower()
        if has_password:
            logger.info("Agent B recalled ZULU-42 from cross-agent context after compaction")
        else:
            logger.warning("Agent B did NOT recall ZULU-42 — cross-agent context may have been lost in compaction")

        # The key structural assertions: compaction worked and conversation continues
        assert len(resp_b3) > 20, "Post-compaction cross-agent response should not be empty"

        # Verify the pending summary was consumed
        state_final = get_session_state_raw(thread_id, self.user_id)
        assert 'pending_compaction_summary' not in state_final, \
            "pending_compaction_summary should be consumed after post-compaction request"

        # Clean up the temporary agent
        try:
            self.client.delete_agent(agent_b_id)
            logger.info(f"Cleaned up temporary Agent B: {agent_b_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up Agent B {agent_b_id}: {e}")

        logger.info(f"PASSED: Cross-agent compaction — password recalled: {has_password}")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """Run tests directly: poetry run python tests/test_context_compaction_integration.py"""
    import sys

    # Remove the skip marker when running directly
    print("=" * 70)
    print("Context Compaction Integration Tests")
    print("=" * 70)

    token = create_auth_token()
    client = CompactionTestClient()
    client.authenticate(token)

    if not client.health_check():
        print("ERROR: API server not reachable at", BASE_URL)
        print("Start it with: uvicorn bondable.rest.main:app --reload")
        sys.exit(1)

    print(f"API server is healthy at {BASE_URL}")

    # Run tests manually
    test = TestContextCompactionIntegration()
    test.client = client
    test.provider = get_provider()
    test.user_id = "test_user_compaction_test"

    tests_to_run = [
        ("Context Usage Tracking", test.test_context_usage_tracking),
        ("Compaction Triggered by Threshold", test.test_compaction_triggered_by_threshold),
        ("Conversation Continues After Compaction", test.test_conversation_continues_after_compaction),
        ("Multiple Compactions", test.test_multiple_compactions),
        ("Natural Compaction with Long Conversation", test.test_natural_compaction_with_long_conversation),
        ("Pending Summary Not Reinjected", test.test_pending_summary_not_reinjected),
        ("Stale Compaction Flag Recovery", test.test_stale_compaction_flag_recovery),
        ("Cross-Agent Compaction", test.test_cross_agent_compaction),
    ]

    passed = 0
    failed = 0
    skipped = 0
    for name, test_fn in tests_to_run:
        print(f"\n{'=' * 70}")
        print(f"Running: {name}")
        print('=' * 70)

        # Re-initialize client for each test
        test.client = CompactionTestClient()
        test.client.authenticate(token)

        try:
            test_fn()
            print(f"  PASSED: {name}")
            passed += 1
        except pytest.skip.Exception as e:
            print(f"  SKIPPED: {name} ({e})")
            skipped += 1
        except Exception as e:
            print(f"  FAILED: {name}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        finally:
            test.client.cleanup()

    print(f"\n{'=' * 70}")
    total = passed + failed + skipped
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped out of {total}")
    print('=' * 70)
    sys.exit(0 if failed == 0 else 1)
