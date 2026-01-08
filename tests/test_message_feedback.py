#!/usr/bin/env python3
"""
Test Message Feedback Feature

This test exercises the message feedback REST API endpoints:
1. Get messages for a thread and verify no feedback initially
2. Add thumbs up feedback to a message
3. Verify feedback is present in the message
4. Edit the feedback (change type and message)
5. Verify edited feedback
6. Delete the feedback
7. Verify feedback is removed

Prerequisites:
- Backend server running: uvicorn bondable.rest.main:app --reload
- python-jose package: pip install python-jose[cryptography]
"""

import requests
import time
from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Optional, Dict, List
import sys


def create_auth_token(user_email: str = "feedback_test@example.com") -> str:
    """Create a JWT token using Bond's JWT configuration."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": user_email,
        "name": "Feedback Test User",
        "user_id": f"test_user_{user_email.split('@')[0]}",
        "provider": "google",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
    return token


class MessageFeedbackTest:
    """Test class for message feedback functionality."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        self.thread_id = None
        self.test_message_id = None

    def set_token(self, token: str):
        """Set the authentication token."""
        self.headers['Authorization'] = f'Bearer {token}'
        self.headers['Content-Type'] = 'application/json'

    def test_health(self) -> bool:
        """Test API health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"   Health check failed: {e}")
            return False

    def get_default_agent(self) -> dict:
        """Get the default agent (home agent)."""
        response = requests.get(f"{self.base_url}/agents/default", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def create_thread(self, name: str = None) -> dict:
        """Create a new thread."""
        payload = {"name": name} if name else {}
        response = requests.post(f"{self.base_url}/threads", headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def chat(self, thread_id: str, agent_id: str, prompt: str) -> str:
        """Send a chat message and get the response."""
        payload = {
            "thread_id": thread_id,
            "agent_id": agent_id,
            "prompt": prompt
        }

        response = requests.post(f"{self.base_url}/chat", headers=self.headers, json=payload, stream=True)
        response.raise_for_status()

        full_response = ""
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                full_response += chunk

        return full_response

    def get_thread_messages(self, thread_id: str) -> List[Dict]:
        """Get messages from a thread."""
        response = requests.get(f"{self.base_url}/threads/{thread_id}/messages", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def submit_feedback(self, thread_id: str, message_id: str, feedback_type: str, feedback_message: str = None) -> dict:
        """Submit or update feedback for a message."""
        payload = {
            "feedback_type": feedback_type,
            "feedback_message": feedback_message
        }
        response = requests.put(
            f"{self.base_url}/threads/{thread_id}/messages/{message_id}/feedback",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def delete_feedback(self, thread_id: str, message_id: str) -> bool:
        """Delete feedback for a message."""
        response = requests.delete(
            f"{self.base_url}/threads/{thread_id}/messages/{message_id}/feedback",
            headers=self.headers
        )
        return response.status_code == 204

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread."""
        response = requests.delete(f"{self.base_url}/threads/{thread_id}", headers=self.headers)
        return response.status_code == 204


def run_test():
    """Run the message feedback test."""
    print("\n" + "=" * 60)
    print("Message Feedback Feature Test")
    print("=" * 60)

    test = MessageFeedbackTest()
    passed = 0
    failed = 0

    try:
        # Step 0: Health check
        print("\n[1/9] Checking API health...")
        if test.test_health():
            print("   PASS: API is healthy")
            passed += 1
        else:
            print("   FAIL: API health check failed")
            failed += 1
            return passed, failed

        # Step 1: Authenticate
        print("\n[2/9] Authenticating...")
        token = create_auth_token()
        test.set_token(token)
        print("   PASS: Authenticated")
        passed += 1

        # Step 2: Get default agent (home agent)
        print("\n[3/9] Getting default agent...")
        agent = test.get_default_agent()
        agent_id = agent['agent_id']
        print(f"   PASS: Got default agent: {agent['name']} (ID: {agent_id})")
        passed += 1

        # Step 3: Create thread and send a message
        print("\n[4/9] Creating thread and sending message...")
        thread = test.create_thread("Feedback Test Thread")
        test.thread_id = thread['id']
        print(f"   Created thread: {test.thread_id}")

        # Send a simple message to get a response
        response = test.chat(test.thread_id, agent_id, "Hello! Please respond with a brief greeting.")
        print(f"   Got response from agent")

        # Get messages and find an assistant message
        messages = test.get_thread_messages(test.thread_id)
        assistant_messages = [m for m in messages if m['role'] == 'assistant']

        if not assistant_messages:
            print("   FAIL: No assistant messages found")
            failed += 1
            return passed, failed

        test.test_message_id = assistant_messages[0]['id']
        print(f"   PASS: Got assistant message: {test.test_message_id}")
        passed += 1

        # Step 4: Verify no feedback initially
        print("\n[5/9] Verifying no initial feedback...")
        messages = test.get_thread_messages(test.thread_id)
        test_msg = next((m for m in messages if m['id'] == test.test_message_id), None)

        if test_msg and test_msg.get('feedback_type') is None and test_msg.get('feedback_message') is None:
            print("   PASS: No feedback on message initially")
            passed += 1
        else:
            print(f"   FAIL: Expected no feedback, got: type={test_msg.get('feedback_type')}, msg={test_msg.get('feedback_message')}")
            failed += 1

        # Step 5: Add thumbs up feedback
        print("\n[6/9] Adding thumbs up feedback...")
        feedback_response = test.submit_feedback(
            test.thread_id,
            test.test_message_id,
            feedback_type="up",
            feedback_message="Great response!"
        )
        print(f"   Feedback submitted: {feedback_response}")

        # Verify feedback was saved
        messages = test.get_thread_messages(test.thread_id)
        test_msg = next((m for m in messages if m['id'] == test.test_message_id), None)

        if test_msg and test_msg.get('feedback_type') == 'up' and test_msg.get('feedback_message') == 'Great response!':
            print("   PASS: Feedback saved correctly (type=up, message='Great response!')")
            passed += 1
        else:
            print(f"   FAIL: Feedback not saved correctly. Got: type={test_msg.get('feedback_type')}, msg={test_msg.get('feedback_message')}")
            failed += 1

        # Step 6: Edit feedback (change to thumbs down with different message)
        print("\n[7/9] Editing feedback to thumbs down...")
        feedback_response = test.submit_feedback(
            test.thread_id,
            test.test_message_id,
            feedback_type="down",
            feedback_message="Actually, could be better"
        )
        print(f"   Feedback updated: {feedback_response}")

        # Verify edited feedback
        messages = test.get_thread_messages(test.thread_id)
        test_msg = next((m for m in messages if m['id'] == test.test_message_id), None)

        if test_msg and test_msg.get('feedback_type') == 'down' and test_msg.get('feedback_message') == 'Actually, could be better':
            print("   PASS: Feedback edited correctly (type=down, message='Actually, could be better')")
            passed += 1
        else:
            print(f"   FAIL: Feedback not edited correctly. Got: type={test_msg.get('feedback_type')}, msg={test_msg.get('feedback_message')}")
            failed += 1

        # Step 7: Delete feedback
        print("\n[8/9] Deleting feedback...")
        if test.delete_feedback(test.thread_id, test.test_message_id):
            print("   Feedback deletion returned 204")

            # Verify feedback was deleted
            messages = test.get_thread_messages(test.thread_id)
            test_msg = next((m for m in messages if m['id'] == test.test_message_id), None)

            if test_msg and test_msg.get('feedback_type') is None and test_msg.get('feedback_message') is None:
                print("   PASS: Feedback deleted successfully")
                passed += 1
            else:
                print(f"   FAIL: Feedback not deleted. Got: type={test_msg.get('feedback_type')}, msg={test_msg.get('feedback_message')}")
                failed += 1
        else:
            print("   FAIL: Delete request did not return 204")
            failed += 1

        # Step 8: Cleanup
        print("\n[9/9] Cleaning up...")
        if test.delete_thread(test.thread_id):
            print(f"   PASS: Deleted test thread {test.thread_id}")
            passed += 1
        else:
            print(f"   WARN: Failed to delete test thread {test.thread_id}")
            # Don't count as failed since test logic passed

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the REST API server.")
        print("   Make sure the server is running:")
        print("   uvicorn bondable.rest.main:app --reload")
        failed += 1

    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: HTTP Error: {e}")
        try:
            error_detail = e.response.json()
            print(f"   Details: {error_detail}")
        except:
            print(f"   Response: {e.response.text}")
        failed += 1

        # Cleanup on error
        if test.thread_id:
            print("\n   Cleaning up after error...")
            test.delete_thread(test.thread_id)

    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

        # Cleanup on error
        if test.thread_id:
            print("\n   Cleaning up after error...")
            test.delete_thread(test.thread_id)

    return passed, failed


def main():
    """Main entry point."""
    passed, failed = run_test()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
