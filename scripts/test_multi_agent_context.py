#!/usr/bin/env python3
"""
Integration test for multi-agent thread context sharing.

Tests that Agent B can see what Agent A said in the same thread by verifying
that conversationHistory is passed via sessionState.

Prerequisites:
- REST API server running: uvicorn bondable.rest.main:app --reload
- python-jose package: pip install python-jose[cryptography]

Usage:
    python scripts/test_multi_agent_context.py [--base-url http://localhost:8000]
"""

import sys
import os
import re
import time
import argparse

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.api_demo import BondAPIDemo, create_auth_token


PHRASE = "PURPLE ELEPHANT 42"


def run_test(base_url: str = "http://localhost:8000"):
    """Run the multi-agent context sharing integration test."""
    print("=" * 60)
    print("Multi-Agent Thread Context Sharing Test")
    print("=" * 60)

    demo = BondAPIDemo(base_url)

    # Health check
    print("\n[1/8] Health check...")
    if not demo.test_health():
        print("   FAIL: API is not healthy")
        return False
    print("   OK")

    # Authenticate
    print("\n[2/8] Authenticating...")
    try:
        token = create_auth_token("multi_agent_test@example.com")
        demo.set_token(token)
        user = demo.get_user_info()
        print(f"   OK - Authenticated as {user['email']}")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    # Get default model
    print("\n[3/8] Getting default model...")
    try:
        models, default_model = demo.get_available_models()
        print(f"   OK - Using model: {default_model}")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    try:
        # Create Agent 1 ("Phrase Bot")
        print("\n[4/8] Creating Agent 1 (Phrase Bot)...")
        agent1 = demo.create_agent(
            name="Phrase Bot",
            description="A friendly assistant that includes a special code phrase in every response",
            instructions=(
                f"You are a friendly assistant called Phrase Bot. "
                f"In every response you give, you must naturally include this code phrase: {PHRASE}. "
                f"For example, if someone asks how you are, say something like: "
                f"'I'm doing great! By the way, my code phrase is {PHRASE}.' "
                f"Always work the phrase '{PHRASE}' into your reply."
            ),
            model=default_model
        )
        agent1_id = agent1['agent_id']
        print(f"   OK - Agent 1 ID: {agent1_id}")

        # Create Agent 2 ("Context Checker")
        print("\n[5/8] Creating Agent 2 (Context Checker)...")
        agent2 = demo.create_agent(
            name="Context Checker",
            description="An agent that reports what prior agents said",
            instructions=(
                "You are Context Checker. Your job is to look at the conversation history "
                "and report exactly what the previous assistant said. "
                "Quote the previous assistant's response word for word. "
                "If you can see prior conversation, repeat the exact phrase that was used."
            ),
            model=default_model
        )
        agent2_id = agent2['agent_id']
        print(f"   OK - Agent 2 ID: {agent2_id}")

        # Wait for agents to be ready (Bedrock agent creation is async)
        print("\n   Waiting for agents to be ready...")
        time.sleep(5)

        # Create shared thread
        print("\n[6/8] Creating shared thread...")
        thread = demo.create_thread(name="Multi-Agent Context Test")
        thread_id = thread['id']
        print(f"   OK - Thread ID: {thread_id}")

        # Send message to Agent 1
        print(f"\n[7/8] Sending message to Agent 1 (Phrase Bot)...")
        print(f"   User: What is your special phrase?")
        response1 = demo.chat(
            thread_id=thread_id,
            agent_id=agent1_id,
            prompt="What is your special phrase?"
        )
        print(f"\n   Checking Agent 1 response contains '{PHRASE}'...")
        if PHRASE in response1.upper() or PHRASE.lower() in response1.lower():
            print(f"   OK - Agent 1 responded with the phrase")
        else:
            print(f"   WARNING - Agent 1 response may not contain exact phrase")
            print(f"   Response: {response1[:200]}")

        # Brief pause between agent switches
        time.sleep(2)

        # Send message to Agent 2 in same thread
        print(f"\n[8/8] Sending message to Agent 2 (Context Checker) in SAME thread...")
        print(f"   User: What did the previous agent say? What was the special phrase?")
        response2 = demo.chat(
            thread_id=thread_id,
            agent_id=agent2_id,
            prompt="What did the previous agent say? What was the special phrase? Please quote it exactly."
        )

        # Verify Agent 2 can see Agent 1's response
        print(f"\n{'=' * 60}")
        print("RESULTS")
        print(f"{'=' * 60}")

        # Extract Agent 1's actual text from the raw response
        agent1_text = ""
        text_matches = re.findall(r'type="text" role="assistant"[^>]*>([^<]+)<', response1)
        if text_matches:
            agent1_text = text_matches[0].strip()
        print(f"\n   Agent 1 said: \"{agent1_text}\"")

        # Check if PURPLE ELEPHANT 42 appears in Agent 2's response
        phrase_found = PHRASE in response2.upper() or PHRASE.lower() in response2.lower()
        # Also check partial matches for the phrase
        partial_found = "PURPLE" in response2.upper() and "ELEPHANT" in response2.upper()
        # Check if Agent 2 references what Agent 1 actually said (context sharing proof)
        context_found = False
        if agent1_text:
            # Check if Agent 2 quotes or closely references Agent 1's actual words
            # Use longer, more distinctive phrases to avoid false positives
            agent1_lower = agent1_text.lower()
            response2_lower = response2.lower()
            # Look for 3+ word sequences from Agent 1's response in Agent 2's response
            agent1_words = agent1_lower.split()
            for i in range(len(agent1_words) - 2):
                trigram = f"{agent1_words[i]} {agent1_words[i+1]} {agent1_words[i+2]}"
                if trigram in response2_lower:
                    context_found = True
                    break
        # Check for signals that Agent 2 has NO context at all
        no_context_signals = [
            "first message", "no prior", "no previous", "beginning of our conversation",
            "nothing to quote", "no conversation history", "no earlier",
            "haven't had any previous", "no record of"
        ]
        no_context = any(signal in response2.lower() for signal in no_context_signals)

        if phrase_found:
            print(f"\n   PASS: Agent 2 referenced the exact phrase '{PHRASE}'")
            print(f"   Cross-agent context sharing is WORKING!")
            success = True
        elif partial_found:
            print(f"\n   PARTIAL PASS: Agent 2 referenced parts of the phrase")
            print(f"   Cross-agent context sharing appears to be working")
            success = True
        elif context_found and not no_context:
            print(f"\n   PASS: Agent 2 referenced Agent 1's actual response content")
            print(f"   (Agent 1 didn't say the exact phrase, but Agent 2 has cross-agent context)")
            print(f"   Cross-agent context sharing is WORKING!")
            success = True
        elif no_context:
            print(f"\n   FAIL: Agent 2 has NO context from Agent 1")
            print(f"   Agent 2 thinks this is the first message in the conversation")
            print(f"   Agent 2 response: {response2[:500]}")
            success = False
        else:
            print(f"\n   INCONCLUSIVE: Agent 2 did not reference '{PHRASE}' or Agent 1's words")
            print(f"   Agent 2 response: {response2[:500]}")
            success = False

        # Verify thread messages show both agent IDs
        print(f"\n   Verifying thread messages...")
        try:
            messages = demo.get_thread_messages(thread_id)
            agent_ids_in_thread = set()
            for msg in messages:
                aid = msg.get('agent_id')
                if aid:
                    agent_ids_in_thread.add(aid)

            if agent1_id in agent_ids_in_thread and agent2_id in agent_ids_in_thread:
                print(f"   OK - Both agents present in thread: {agent_ids_in_thread}")
            else:
                print(f"   WARNING - Expected both agents in thread, found: {agent_ids_in_thread}")
        except Exception as e:
            print(f"   WARNING - Could not verify thread messages: {e}")

        return success

    finally:
        # Cleanup
        print(f"\nCleaning up resources...")
        results = demo.cleanup_all()
        for resource_type, status in results.items():
            deleted = len(status.get("deleted", []))
            failed = len(status.get("failed", []))
            if deleted or failed:
                print(f"   {resource_type}: {deleted} deleted, {failed} failed")
        print("   Done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test multi-agent context sharing")
    parser.add_argument("--base-url", default="http://localhost:8000",
                       help="Base URL of the Bond AI API")
    args = parser.parse_args()

    success = run_test(args.base_url)
    sys.exit(0 if success else 1)
