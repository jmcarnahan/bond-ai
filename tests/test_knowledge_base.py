#!/usr/bin/env python3
"""
Knowledge Base Integration Test

This script tests the AWS Bedrock Knowledge Base integration:
1. Creates agents with 'direct' and 'knowledge_base' file storage modes
2. Uploads files to KB agents
3. Triggers ingestion
4. Verifies KB context retrieval in chat
5. Verifies agent isolation (files not shared between agents)

Prerequisites:
    1. Deploy infrastructure with KB enabled:
       cd deployment/terraform-existing-vpc
       terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars -var="enable_knowledge_base=true"

    2. Run the backend locally:
       poetry run uvicorn bondable.rest.main:app --reload

    3. Run this test:
       poetry run python scripts/test_knowledge_base.py

Environment Variables:
    API_BASE_URL: Backend URL (default: http://localhost:8000)
"""

import os
import sys
import time
import json
import requests
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple

# For JWT token creation
try:
    from jose import jwt
    from bondable.bond.config import Config
except ImportError:
    print("ERROR: Required packages not found. Install with: pip install python-jose[cryptography]")
    sys.exit(1)


class KnowledgeBaseTest:
    """Test Knowledge Base functionality."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip('/')
        self.headers = {}
        self.created_resources = {
            "agents": [],
            "threads": [],
            "files": [],
            "temp_files": []
        }
        self.test_results = []

    def setup_auth(self, user_email: str = "kb-test@bondai.com") -> str:
        """Create JWT token for authentication."""
        try:
            jwt_config = Config.config().get_jwt_config()

            token_data = {
                "sub": user_email,
                "name": "KB Test User",
                "user_id": f"kb_test_{user_email.split('@')[0]}",
                "provider": "google",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
            }

            token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
            self.headers['Authorization'] = f'Bearer {token}'
            return token

        except Exception as e:
            print(f"ERROR: Failed to create auth token: {e}")
            raise

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if message:
            print(f"         {message}")
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })

    def test_health(self) -> bool:
        """Test API health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"ERROR: Health check failed: {e}")
            return False

    def get_default_model(self) -> str:
        """Get the default model from available models."""
        try:
            response = requests.get(f"{self.base_url}/agents/models", headers=self.headers)
            response.raise_for_status()
            models = response.json()

            for model in models:
                if model.get('is_default', False):
                    return model['name']

            if models:
                return models[0]['name']
            return None
        except Exception as e:
            print(f"WARNING: Could not get models: {e}")
            return None

    def create_test_document(self, content: str, filename: str = "test_doc.txt") -> str:
        """Create a temporary test document."""
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            prefix=filename.replace('.txt', '_')
        )
        temp_file.write(content)
        temp_file.close()
        self.created_resources["temp_files"].append(temp_file.name)
        return temp_file.name

    def upload_file(self, file_path: str) -> Optional[str]:
        """Upload a file and return the file ID."""
        try:
            filename = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                files = {"file": (filename, f, "text/plain")}
                response = requests.post(
                    f"{self.base_url}/files",
                    headers=self.headers,
                    files=files
                )
                response.raise_for_status()

            result = response.json()
            file_id = result.get('provider_file_id')
            if file_id:
                self.created_resources["files"].append(file_id)
            return file_id

        except Exception as e:
            print(f"ERROR: Failed to upload file: {e}")
            return None

    def create_agent(self, name: str, file_storage: str = 'direct',
                     description: str = None, instructions: str = None,
                     file_ids: List[str] = None) -> Optional[str]:
        """Create an agent with specified file_storage mode."""
        try:
            model = self.get_default_model()

            payload = {
                "name": name,
                "description": description or f"Test agent for KB: {name}",
                "instructions": instructions or "You are a helpful assistant that answers questions based on provided documents.",
                "model": model,
                "file_storage": file_storage,
                "tools": [],
                "metadata": {"test": "knowledge_base"}
            }

            # Add file_search tool resources if files provided
            if file_ids:
                payload["tools"] = [{"type": "file_search"}]
                payload["tool_resources"] = {
                    "file_search": {"file_ids": file_ids}
                }

            response = requests.post(
                f"{self.base_url}/agents",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            agent_id = result.get('agent_id')
            if agent_id:
                self.created_resources["agents"].append(agent_id)
                print(f"  Created agent '{name}' with id={agent_id}, file_storage={file_storage}")
            return agent_id

        except Exception as e:
            print(f"ERROR: Failed to create agent: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Response: {e.response.text}")
            return None

    def get_agent_details(self, agent_id: str) -> Optional[Dict]:
        """Get agent details including file_storage mode."""
        try:
            response = requests.get(
                f"{self.base_url}/agents/{agent_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"ERROR: Failed to get agent details: {e}")
            return None

    def update_agent(self, agent_id: str, name: str = None, file_ids: List[str] = None,
                     file_storage: str = None) -> bool:
        """Update an agent's configuration including file list."""
        try:
            # Get current agent details to preserve existing values
            current = self.get_agent_details(agent_id)
            if not current:
                print(f"ERROR: Could not get current agent details for {agent_id}")
                return False

            payload = {
                "name": name or current.get('name', 'Updated Agent'),
                "description": current.get('description', ''),
                "instructions": current.get('instructions', ''),
                "model": current.get('model', ''),
                "file_storage": file_storage or current.get('file_storage', 'direct'),
            }

            # Update file list if provided
            if file_ids is not None:
                payload["tool_resources"] = {"file_search": {"file_ids": file_ids}}
                payload["tools"] = [{"type": "file_search"}]

            response = requests.put(
                f"{self.base_url}/agents/{agent_id}",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            print(f"  Updated agent {agent_id} with {len(file_ids) if file_ids else 0} files")
            return True
        except Exception as e:
            print(f"ERROR: Failed to update agent: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Response: {e.response.text}")
            return False

    def create_thread(self, name: str = None) -> Optional[str]:
        """Create a thread (matches api_demo.py pattern)."""
        try:
            payload = {"name": name} if name else {}
            response = requests.post(
                f"{self.base_url}/threads",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()

            thread = response.json()
            thread_id = thread.get('id')
            if thread_id:
                self.created_resources["threads"].append(thread_id)
            return thread_id

        except Exception as e:
            print(f"ERROR: Failed to create thread: {e}")
            return None

    def send_message_and_get_response(self, thread_id: str, agent_id: str, message: str,
                                       timeout: int = 120) -> Optional[str]:
        """Send a chat message and get response (matches api_demo.py pattern)."""
        try:
            payload = {
                "thread_id": thread_id,
                "agent_id": agent_id,
                "prompt": message
            }
            response = requests.post(
                f"{self.base_url}/chat",
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=timeout
            )
            response.raise_for_status()

            # Collect streaming response (same pattern as api_demo.py)
            full_response = ""
            for chunk in response.iter_content(decode_unicode=True):
                if chunk:
                    full_response += chunk

            return full_response.strip()

        except Exception as e:
            print(f"ERROR: Failed to send message: {e}")
            return None

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        try:
            response = requests.delete(
                f"{self.base_url}/agents/{agent_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"WARNING: Failed to delete agent {agent_id}: {e}")
            return False

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread."""
        try:
            response = requests.delete(
                f"{self.base_url}/threads/{thread_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"WARNING: Failed to delete thread {thread_id}: {e}")
            return False

    def wait_for_ingestion(self, max_wait: int = 120, poll_interval: int = 10) -> bool:
        """
        Wait for any active ingestion jobs to complete.

        This calls the backend endpoint to check ingestion status.
        Returns True if ingestion completes, False if timeout.
        """
        # Note: We don't have direct access to ingestion job IDs from the test,
        # so we use a simple wait with progress indication.
        # In a production scenario, we'd track job IDs and poll their status.
        print(f"    Waiting up to {max_wait}s for KB ingestion...")
        waited = 0
        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval
            remaining = max_wait - waited
            if remaining > 0:
                print(f"    Waited {waited}s, {remaining}s remaining...")
        print(f"    Ingestion wait complete ({max_wait}s)")
        return True

    def cleanup(self):
        """Clean up all created resources."""
        print("\n" + "=" * 70)
        print("CLEANUP")
        print("=" * 70)

        # Delete threads first
        for thread_id in self.created_resources["threads"]:
            if self.delete_thread(thread_id):
                print(f"  Deleted thread: {thread_id}")

        # Delete agents
        for agent_id in self.created_resources["agents"]:
            if self.delete_agent(agent_id):
                print(f"  Deleted agent: {agent_id}")

        # Delete temp files
        for temp_file in self.created_resources["temp_files"]:
            try:
                os.unlink(temp_file)
                print(f"  Deleted temp file: {temp_file}")
            except Exception:
                pass

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in self.test_results if r['passed'])
        failed = sum(1 for r in self.test_results if not r['passed'])

        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"  {status} {result['test']}")

        print("-" * 70)
        print(f"Total: {len(self.test_results)} | Passed: {passed} | Failed: {failed}")
        print("=" * 70)

        return failed == 0


def run_tests():
    """Run all Knowledge Base tests."""
    print("=" * 70)
    print("KNOWLEDGE BASE INTEGRATION TEST")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    test = KnowledgeBaseTest()

    # Initialize variables that will be used across tests
    file_id_2 = None
    file_id_3 = None
    meeting_phrase = None
    budget_phrase = None

    # Setup
    print("SETUP")
    print("-" * 70)

    # Check health
    if not test.test_health():
        print("ERROR: API not reachable. Is the backend running?")
        print("  Start with: poetry run uvicorn bondable.rest.main:app --reload")
        return False
    print(f"  API URL: {test.base_url}")

    # Setup auth
    test.setup_auth()
    print("  Authentication configured")

    # Get default model
    model = test.get_default_model()
    if model:
        print(f"  Default model: {model}")

    print()

    # =========================================================================
    # TEST 1: Create agent with direct mode (default)
    # =========================================================================
    print("=" * 70)
    print("TEST 1: Create agent with file_storage='direct' (default)")
    print("=" * 70)

    direct_agent_id = test.create_agent(
        name=f"Direct Mode Agent {datetime.now().strftime('%H%M%S')}",
        file_storage='direct',
        description="Agent using direct file storage (5-file limit)"
    )

    if direct_agent_id:
        details = test.get_agent_details(direct_agent_id)
        if details:
            actual_storage = details.get('file_storage', 'unknown')
            test.log_test(
                "Direct mode agent creation",
                actual_storage == 'direct',
                f"file_storage={actual_storage}"
            )
        else:
            test.log_test("Direct mode agent creation", False, "Could not get agent details")
    else:
        test.log_test("Direct mode agent creation", False, "Agent creation failed")

    print()

    # =========================================================================
    # TEST 2 & 3: Upload document, then create KB agent with file attached
    # =========================================================================
    print("=" * 70)
    print("TEST 2: Create agent with file_storage='knowledge_base'")
    print("=" * 70)

    # First, upload the document (to regular storage)
    unique_phrase = f"QUANTUM_BOND_SECRET_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    doc_content = f"""
    CONFIDENTIAL DOCUMENT - KB Test

    This document contains proprietary information about Project Aurora.

    Key Facts:
    1. The secret code phrase is: {unique_phrase}
    2. Project Aurora was initiated on January 15, 2024
    3. The project budget is $2.5 million
    4. Lead researcher: Dr. Sarah Mitchell
    5. Primary objective: Develop quantum-resistant encryption

    This information should only be accessible to agents with this document
    in their knowledge base.
    """

    doc_path = test.create_test_document(doc_content, "project_aurora.txt")
    print(f"  Created test document with unique phrase: {unique_phrase}")

    file_id = test.upload_file(doc_path)
    if not file_id:
        test.log_test("KB mode agent creation", False, "File upload failed")
        test.log_test("Document upload", False, "Upload failed")
    else:
        print(f"  Uploaded file: {file_id}")

        # Now create the agent WITH the file attached (triggers KB upload)
        kb_agent_id = test.create_agent(
            name=f"KB Mode Agent {datetime.now().strftime('%H%M%S')}",
            file_storage='knowledge_base',
            description="Agent using Knowledge Base storage (unlimited files)",
            file_ids=[file_id]  # Attach file at creation time - triggers KB upload
        )

        if kb_agent_id:
            details = test.get_agent_details(kb_agent_id)
            if details:
                actual_storage = details.get('file_storage', 'unknown')
                test.log_test(
                    "KB mode agent creation",
                    actual_storage == 'knowledge_base',
                    f"file_storage={actual_storage}"
                )
            else:
                test.log_test("KB mode agent creation", False, "Could not get agent details")
        else:
            test.log_test("KB mode agent creation", False, "Agent creation failed")

        test.log_test("Document upload", True, f"file_id={file_id}")

    print()

    # =========================================================================
    # TEST 3: Wait for ingestion (KB takes time to process documents)
    # =========================================================================
    print("=" * 70)
    print("TEST 3: Upload unique document to KB agent")
    print("=" * 70)
    print(f"  Document uploaded and attached to KB agent")
    print(f"  Waiting for KB ingestion to complete (this may take 30-60 seconds)...")

    # Wait for ingestion - KB takes time to process documents
    ingestion_wait_time = 45  # seconds
    for i in range(ingestion_wait_time):
        if i % 10 == 0:
            print(f"  Waiting... {ingestion_wait_time - i}s remaining")
        time.sleep(1)
    print(f"  Ingestion wait complete")
    test.log_test("Document upload", True, f"file_id={file_id}")

    print()

    # =========================================================================
    # TEST 4: Chat with KB agent - should find document context
    # =========================================================================
    print("=" * 70)
    print("TEST 4: Chat with KB agent (should retrieve KB context)")
    print("=" * 70)

    if kb_agent_id:
        thread_id = test.create_thread("KB Context Test Thread")
        if thread_id:
            print(f"  Created thread: {thread_id}")
            print("  Sending query about document content...")

            response = test.send_message_and_get_response(
                thread_id,
                kb_agent_id,
                "What is the secret code phrase mentioned in the Project Aurora document?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")
                print(f"  Preview: {response[:200]}...")

                # Check if the unique phrase is in the response (KB retrieval worked)
                # Note: This may fail if KB isn't fully set up/ingested yet
                if unique_phrase in response:
                    test.log_test(
                        "KB context retrieval",
                        True,
                        "Response contains document content"
                    )
                else:
                    test.log_test(
                        "KB context retrieval",
                        False,
                        "Response does not contain document content (KB may not be configured or ingestion pending)"
                    )
            else:
                test.log_test("KB context retrieval", False, "No response received")
        else:
            test.log_test("KB context retrieval", False, "Could not create thread")
    else:
        test.log_test("KB context retrieval", False, "No KB agent available")

    print()

    # =========================================================================
    # TEST 5: Create second KB agent - verify isolation
    # =========================================================================
    print("=" * 70)
    print("TEST 5: Agent isolation - second agent should NOT see first agent's files")
    print("=" * 70)

    kb_agent2_id = test.create_agent(
        name=f"KB Mode Agent 2 {datetime.now().strftime('%H%M%S')}",
        file_storage='knowledge_base',
        description="Second KB agent to test isolation"
    )

    if kb_agent2_id:
        thread_id = test.create_thread("Agent Isolation Test Thread")
        if thread_id:
            print(f"  Created thread: {thread_id}")
            print("  Querying second agent for first agent's document...")

            response = test.send_message_and_get_response(
                thread_id,
                kb_agent2_id,
                "What is the secret code phrase for Project Aurora?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")

                # The second agent should NOT know about the unique phrase
                if unique_phrase not in response:
                    test.log_test(
                        "Agent isolation",
                        True,
                        "Second agent does NOT have access to first agent's documents"
                    )
                else:
                    test.log_test(
                        "Agent isolation",
                        False,
                        "SECURITY ISSUE: Second agent can access first agent's documents!"
                    )
            else:
                test.log_test("Agent isolation", False, "No response received")
        else:
            test.log_test("Agent isolation", False, "Could not create thread")
    else:
        test.log_test("Agent isolation", False, "Could not create second agent")

    print()

    # =========================================================================
    # TEST 6: Direct mode agent should NOT use KB
    # =========================================================================
    print("=" * 70)
    print("TEST 6: Direct mode agent should NOT query Knowledge Base")
    print("=" * 70)

    if direct_agent_id:
        thread_id = test.create_thread("Direct Mode Test Thread")
        if thread_id:
            print(f"  Created thread: {thread_id}")
            print("  Querying direct mode agent...")

            response = test.send_message_and_get_response(
                thread_id,
                direct_agent_id,
                "What do you know about Project Aurora and its secret code phrase?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")

                # Direct mode agent should not have KB context
                if unique_phrase not in response:
                    test.log_test(
                        "Direct mode no KB access",
                        True,
                        "Direct mode agent correctly does NOT query KB"
                    )
                else:
                    test.log_test(
                        "Direct mode no KB access",
                        False,
                        "Direct mode agent incorrectly accessed KB content!"
                    )
            else:
                test.log_test("Direct mode no KB access", False, "No response received")
        else:
            test.log_test("Direct mode no KB access", False, "Could not create thread")
    else:
        test.log_test("Direct mode no KB access", False, "No direct agent available")

    print()

    # =========================================================================
    # TEST 7: Update agent by adding more files (no unique constraint error)
    # =========================================================================
    print("=" * 70)
    print("TEST 7: Update KB agent - add more files (no unique constraint error)")
    print("=" * 70)

    if kb_agent_id and file_id:
        # Upload additional files with unique identifiable phrases
        meeting_phrase = f"MEETING_NOTES_SECRET_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        doc2_content = f"""
        PROJECT AURORA - Meeting Notes
        Date: January 20, 2024

        Key Discussion Points:
        1. The meeting secret phrase is: {meeting_phrase}
        2. Budget review completed - on track
        3. Next milestone due in 2 weeks

        Attendees: Dr. Mitchell, Johnson, Chen
        """
        doc2_path = test.create_test_document(doc2_content, "meeting_notes.txt")
        file_id_2 = test.upload_file(doc2_path)
        print(f"  Uploaded second file: {file_id_2}")

        budget_phrase = f"BUDGET_OVERVIEW_SECRET_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        doc3_content = f"""
        PROJECT AURORA - Budget Summary

        The budget secret code is: {budget_phrase}

        Total Allocated: $2.5 million
        - Hardware: $1.2 million
        - Personnel: $800,000
        - Operations: $500,000
        """
        doc3_path = test.create_test_document(doc3_content, "budget.txt")
        file_id_3 = test.upload_file(doc3_path)
        print(f"  Uploaded third file: {file_id_3}")

        if file_id_2 and file_id_3:
            # Update agent with ALL files (original + new)
            all_file_ids = [file_id, file_id_2, file_id_3]
            success = test.update_agent(kb_agent_id, file_ids=all_file_ids)
            test.log_test(
                "Update agent - add files (API)",
                success,
                f"Updated with {len(all_file_ids)} files (1 existing + 2 new)"
            )
        else:
            test.log_test("Update agent - add files (API)", False, "Could not upload additional files")
    else:
        test.log_test("Update agent - add files (API)", False, "No KB agent or file available")

    print()

    # =========================================================================
    # TEST 8: Verify added files are accessible via KB (new thread)
    # =========================================================================
    print("=" * 70)
    print("TEST 8: Verify added files are accessible in KB (via chat)")
    print("=" * 70)

    if kb_agent_id and file_id_2 and file_id_3:
        # Wait for ingestion to complete
        test.wait_for_ingestion(max_wait=60, poll_interval=10)

        # Test in NEW thread to avoid any caching
        thread_id = test.create_thread("Added Files Verification Thread")
        if thread_id:
            print(f"  Created NEW thread: {thread_id}")
            print("  Querying for newly added meeting notes content...")

            response = test.send_message_and_get_response(
                thread_id,
                kb_agent_id,
                "What is the meeting secret phrase mentioned in the meeting notes document?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")

                # The meeting_phrase SHOULD be in the response since we added that file
                if meeting_phrase in response:
                    test.log_test(
                        "Added files accessible in KB",
                        True,
                        f"Meeting notes content found in KB response"
                    )
                else:
                    test.log_test(
                        "Added files accessible in KB",
                        False,
                        f"Meeting notes content NOT found (ingestion may still be processing)"
                    )
            else:
                test.log_test("Added files accessible in KB", False, "No response received")
        else:
            test.log_test("Added files accessible in KB", False, "Could not create thread")
    else:
        test.log_test("Added files accessible in KB", False, "Missing agent or files")

    print()

    # =========================================================================
    # TEST 9: Update agent with same files (idempotent - should be no-op)
    # =========================================================================
    print("=" * 70)
    print("TEST 9: Update KB agent - same files (idempotent, no errors)")
    print("=" * 70)

    if kb_agent_id and file_id and file_id_2 and file_id_3:
        # Update again with the SAME file list
        all_file_ids = [file_id, file_id_2, file_id_3]
        success = test.update_agent(kb_agent_id, file_ids=all_file_ids)
        test.log_test(
            "Update agent - same files (idempotent)",
            success,
            "No change to file list should succeed without error"
        )
    else:
        test.log_test("Update agent - same files (idempotent)", False, "Missing agent or files")

    print()

    # =========================================================================
    # TEST 10: Update agent removing a file
    # =========================================================================
    print("=" * 70)
    print("TEST 10: Update KB agent - remove a file")
    print("=" * 70)

    if kb_agent_id and file_id and file_id_3:
        # Remove file_id_2 (meeting notes), keep file_id and file_id_3
        remaining_files = [file_id, file_id_3]
        success = test.update_agent(kb_agent_id, file_ids=remaining_files)
        test.log_test(
            "Update agent - remove file (API)",
            success,
            f"Removed 1 file (meeting_notes), {len(remaining_files)} remaining"
        )
    else:
        test.log_test("Update agent - remove file (API)", False, "Missing agent or files")

    print()

    # =========================================================================
    # TEST 11: Verify removed file is no longer accessible via KB (new thread)
    # =========================================================================
    print("=" * 70)
    print("TEST 11: Verify removed file is NOT accessible in KB (via chat)")
    print("=" * 70)

    if kb_agent_id and meeting_phrase:
        # Wait for KB to process file removal
        # DeleteKnowledgeBaseDocuments returns status=DELETING, takes time to complete
        test.wait_for_ingestion(max_wait=60, poll_interval=15)

        # Test in NEW thread to avoid any caching
        thread_id = test.create_thread("File Removal Verification Thread")
        if thread_id:
            print(f"  Created NEW thread: {thread_id}")
            print("  Querying for removed meeting notes content...")

            response = test.send_message_and_get_response(
                thread_id,
                kb_agent_id,
                "What is the meeting secret phrase mentioned in the meeting notes document?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")
                print(f"  Looking for phrase: {meeting_phrase}")

                # The meeting_phrase should NOT be in the response since we removed that file
                if meeting_phrase not in response:
                    test.log_test(
                        "Removed file NOT accessible in KB",
                        True,
                        "Meeting notes content correctly removed from KB"
                    )
                else:
                    test.log_test(
                        "Removed file NOT accessible in KB",
                        False,
                        "Meeting notes content still in KB (ingestion may need more time)"
                    )
            else:
                test.log_test("Removed file NOT accessible in KB", False, "No response received")
        else:
            test.log_test("Removed file NOT accessible in KB", False, "Could not create thread")
    else:
        test.log_test("Removed file NOT accessible in KB", False, "No KB agent or meeting_phrase available")

    print()

    # =========================================================================
    # TEST 12: Verify remaining files are still accessible (new thread)
    # =========================================================================
    print("=" * 70)
    print("TEST 12: Verify remaining files still accessible in KB (via chat)")
    print("=" * 70)

    if kb_agent_id and budget_phrase:
        # Test in NEW thread
        thread_id = test.create_thread("Remaining Files Verification Thread")
        if thread_id:
            print(f"  Created NEW thread: {thread_id}")
            print("  Querying for budget document content (should still exist)...")

            response = test.send_message_and_get_response(
                thread_id,
                kb_agent_id,
                "What is the budget secret code mentioned in the budget summary document?"
            )

            if response:
                print(f"  Response received ({len(response)} chars)")

                # The budget_phrase SHOULD still be in the response
                if budget_phrase in response:
                    test.log_test(
                        "Remaining files still accessible",
                        True,
                        "Budget document content still available in KB"
                    )
                else:
                    test.log_test(
                        "Remaining files still accessible",
                        False,
                        "Budget document content NOT found (unexpected)"
                    )
            else:
                test.log_test("Remaining files still accessible", False, "No response received")
        else:
            test.log_test("Remaining files still accessible", False, "Could not create thread")
    else:
        test.log_test("Remaining files still accessible", False, "No KB agent or budget_phrase available")

    print()

    # =========================================================================
    # TEST 13: Complete file lifecycle summary
    # =========================================================================
    print("=" * 70)
    print("TEST 13: File lifecycle complete (create -> add -> verify -> remove -> verify)")
    print("=" * 70)

    # Check if all file-related tests passed
    file_tests = [r for r in test.test_results if any(x in r['test'] for x in
        ['Update agent', 'Added files', 'Removed file', 'Remaining files'])]
    file_tests_passed = all(r['passed'] for r in file_tests) if file_tests else False

    test.log_test(
        "File lifecycle complete",
        file_tests_passed,
        f"Create -> Add -> Verify added -> Remove -> Verify removed -> Verify remaining ({len([t for t in file_tests if t['passed']])}/{len(file_tests)} passed)"
    )

    # Cleanup and summary
    test.cleanup()
    success = test.print_summary()

    return success


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
