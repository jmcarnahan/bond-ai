#!/usr/bin/env python3
"""
Comprehensive Bond AI REST API Demo

This script demonstrates the full lifecycle of working with the Bond AI REST API:
1. Authentication
2. Agent creation
3. Thread creation
4. Chat interaction
5. Cleanup (delete thread and agent)

Prerequisites:
- REST API server running: uvicorn bondable.rest.main:app --reload
- python-jose package: pip install python-jose[cryptography]
"""

import requests
import time
import tempfile
import csv
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Optional, Dict, List


def create_auth_token(user_email: str = "demo@example.com") -> str:
    """Create a JWT token using Bond's JWT configuration."""
    try:
        from bondable.bond.config import Config
        jwt_config = Config.config().get_jwt_config()
        
        # Token needs user_id and provider fields based on auth.py requirements
        token_data = {
            "sub": user_email,
            "name": "Demo User",
            "user_id": f"test_user_{user_email.split('@')[0]}",
            "provider": "google",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        
        token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        return token
        
    except Exception as e:
        print(f"Error creating token: {e}")
        raise


class BondAPIDemo:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        self.created_resources = {"agents": [], "threads": [], "files": [], "temp_files": []}
    
    def set_token(self, token: str):
        """Set the authentication token."""
        self.headers['Authorization'] = f'Bearer {token}'
    
    def test_health(self) -> bool:
        """Test API health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return True
        except Exception:
            return False
    
    def get_user_info(self) -> dict:
        """Get current user information."""
        response = requests.get(f"{self.base_url}/users/me", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def create_customer_data_file(self) -> str:
        """Create a temporary CSV file with fake customer data."""
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        temp_path = temp_file.name
        
        # Track temp file for cleanup
        self.created_resources["temp_files"].append(temp_path)
        
        # Create fake customer data
        customer_data = [
            ["customer_id", "name", "email", "age", "city", "purchase_amount", "subscription_tier"],
            ["001", "Alice Johnson", "alice.johnson@email.com", 29, "New York", 150.75, "Premium"],
            ["002", "Bob Smith", "bob.smith@email.com", 34, "Los Angeles", 89.99, "Basic"],
            ["003", "Carol Davis", "carol.davis@email.com", 42, "Chicago", 220.50, "Premium"],
            ["004", "David Wilson", "david.wilson@email.com", 26, "Houston", 45.25, "Basic"],
            ["005", "Eve Brown", "eve.brown@email.com", 31, "Phoenix", 175.00, "Premium"],
            ["006", "Frank Miller", "frank.miller@email.com", 38, "Philadelphia", 92.80, "Standard"],
            ["007", "Grace Lee", "grace.lee@email.com", 45, "San Antonio", 310.99, "Premium"],
            ["008", "Henry Taylor", "henry.taylor@email.com", 33, "San Diego", 67.45, "Basic"],
            ["009", "Ivy Chen", "ivy.chen@email.com", 28, "Dallas", 198.75, "Standard"],
            ["010", "Jack Thompson", "jack.thompson@email.com", 36, "San Jose", 124.50, "Standard"]
        ]
        
        # Write CSV data
        writer = csv.writer(temp_file)
        writer.writerows(customer_data)
        temp_file.close()
        
        return temp_path
    
    def upload_file(self, file_path: str) -> dict:
        """Upload a file to the API."""
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {"file": (filename, f, "text/csv")}
            response = requests.post(f"{self.base_url}/files", headers=self.headers, files=files)
            response.raise_for_status()
            
        result = response.json()
        
        # Track uploaded file for cleanup
        if 'provider_file_id' in result:
            self.created_resources["files"].append(result['provider_file_id'])
        
        return result
    
    def create_agent(self, name: str, description: str = None, instructions: str = None, 
                     file_ids: list = None) -> dict:
        """Create a new agent with optional code interpreter and files."""
        payload = {
            "name": name,
            "description": description or f"Demo agent: {name}",
            "instructions": instructions or "You are a helpful assistant. Be concise and friendly.",
            "model": "gpt-4o",
            "tools": [],
            "metadata": {"demo": "true", "created_by": "api_demo_script"}
        }
        
        # Add code interpreter tool and file resources if file_ids provided
        if file_ids:
            payload["tools"] = [{"type": "code_interpreter"}]
            payload["tool_resources"] = {
                "code_interpreter": {
                    "file_ids": file_ids
                }
            }
        
        response = requests.post(f"{self.base_url}/agents", headers=self.headers, json=payload)
        response.raise_for_status()
        agent = response.json()
        
        # Track created resource for cleanup
        self.created_resources["agents"].append(agent['agent_id'])
        return agent
    
    def get_default_agent(self) -> dict:
        """Get the default agent."""
        response = requests.get(f"{self.base_url}/agents/default", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_agent_details(self, agent_id: str) -> dict:
        """Get detailed information about an agent."""
        response = requests.get(f"{self.base_url}/agents/{agent_id}", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def create_thread(self, name: str = None) -> dict:
        """Create a new thread."""
        payload = {"name": name} if name else {}
        
        response = requests.post(f"{self.base_url}/threads", headers=self.headers, json=payload)
        response.raise_for_status()
        thread = response.json()
        
        # Track created resource for cleanup
        self.created_resources["threads"].append(thread['id'])
        return thread
    
    def parse_bond_messages(self, xml_string: str) -> List[Dict[str, str]]:
        """Parse bond messages from XML string."""
        messages = []
        try:
            # Wrap in root element to handle multiple messages
            wrapped_xml = f"<root>{xml_string}</root>"
            root = ET.fromstring(wrapped_xml)
            
            for bond_msg in root.findall('.//bond_message'):
                msg_data = {
                    'id': bond_msg.get('message_id', ''),
                    'thread_id': bond_msg.get('thread_id', ''),
                    'agent_id': bond_msg.get('agent_id', ''),
                    'type': bond_msg.get('type', ''),
                    'role': bond_msg.get('role', ''),
                    'content': bond_msg.text or ''
                }
                messages.append(msg_data)
        except Exception as e:
            print(f"\n   ⚠️  Error parsing bond messages: {e}")
        
        return messages
    
    def chat(self, thread_id: str, agent_id: str, prompt: str, show_response: bool = True) -> str:
        """Send a chat message and get the response with ID tracking."""
        payload = {
            "thread_id": thread_id,
            "agent_id": agent_id,
            "prompt": prompt
        }
        
        response = requests.post(f"{self.base_url}/chat", headers=self.headers, json=payload, stream=True)
        response.raise_for_status()
        
        # Collect streaming response
        full_response = ""
        if show_response:
            print("   🤖 Assistant: ", end='', flush=True)
        
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                full_response += chunk
                if show_response:
                    print(chunk, end='', flush=True)
        
        if show_response:
            print()  # New line after response
        
        # Parse bond messages from the response
        messages = self.parse_bond_messages(full_response)
        if messages:
            print("\n   📋 Streamed Message Details:")
            for msg in messages:
                print(f"       - Message ID: {msg['id']}")
                print(f"         Thread ID: {msg['thread_id']}")
                print(f"         Agent ID: {msg['agent_id'] or 'None'}")
                print(f"         Type: {msg['type']}, Role: {msg['role']}")
        
        return full_response
    
    def get_thread_messages(self, thread_id: str, limit: int = 100) -> list:
        """Get messages from a thread with detailed information."""
        response = requests.get(f"{self.base_url}/threads/{thread_id}/messages?limit={limit}", headers=self.headers)
        response.raise_for_status()
        messages = response.json()
        
        print(f"\n   📨 Retrieved {len(messages)} messages from thread:")
        for msg in messages:
            print(f"       - Message ID: {msg.get('id', 'Unknown')}")
            print(f"         Agent ID: {msg.get('agent_id', 'None')}")
            print(f"         Type: {msg.get('type', 'Unknown')}, Role: {msg.get('role', 'Unknown')}")
            content_preview = msg.get('content', '')[:50]
            if len(msg.get('content', '')) > 50:
                content_preview += "..."
            print(f"         Content: {content_preview}")
            print()
        
        return messages
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread."""
        response = requests.delete(f"{self.base_url}/threads/{thread_id}", headers=self.headers)
        success = response.status_code == 204
        if success and thread_id in self.created_resources["threads"]:
            self.created_resources["threads"].remove(thread_id)
        return success
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        response = requests.delete(f"{self.base_url}/agents/{agent_id}", headers=self.headers)
        success = response.status_code == 204
        if success and agent_id in self.created_resources["agents"]:
            self.created_resources["agents"].remove(agent_id)
        return success
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file."""
        response = requests.delete(f"{self.base_url}/files/{file_id}", headers=self.headers)
        success = response.status_code == 200  # Files return 200, not 204
        if success and file_id in self.created_resources["files"]:
            self.created_resources["files"].remove(file_id)
        return success
    
    def cleanup_all(self) -> dict:
        """Clean up all created resources."""
        results = {
            "threads": {"deleted": [], "failed": []}, 
            "agents": {"deleted": [], "failed": []},
            "files": {"deleted": [], "failed": []},
            "temp_files": {"deleted": [], "failed": []}
        }
        
        # Delete threads first
        for thread_id in self.created_resources["threads"].copy():
            if self.delete_thread(thread_id):
                results["threads"]["deleted"].append(thread_id)
            else:
                results["threads"]["failed"].append(thread_id)
        
        # Delete agents (this should be done before files as agents may reference files)
        for agent_id in self.created_resources["agents"].copy():
            if self.delete_agent(agent_id):
                results["agents"]["deleted"].append(agent_id)
            else:
                results["agents"]["failed"].append(agent_id)
        
        # Delete uploaded files
        for file_id in self.created_resources["files"].copy():
            if self.delete_file(file_id):
                results["files"]["deleted"].append(file_id)
            else:
                results["files"]["failed"].append(file_id)
        
        # Delete temporary files from filesystem
        for temp_path in self.created_resources["temp_files"].copy():
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    results["temp_files"]["deleted"].append(temp_path)
                    self.created_resources["temp_files"].remove(temp_path)
                else:
                    results["temp_files"]["deleted"].append(temp_path)  # Already deleted
                    self.created_resources["temp_files"].remove(temp_path)
            except Exception as e:
                results["temp_files"]["failed"].append(f"{temp_path} ({str(e)})")
        
        return results


def main():
    """Main demo function."""
    print("🤖 Bond AI REST API Comprehensive Demo")
    print("=" * 50)
    
    demo = BondAPIDemo()
    
    try:
        # Step 0: Check API health
        print("🏥 Checking API health...")
        if demo.test_health():
            print("   ✅ API is healthy")
        else:
            print("   ❌ API health check failed")
            return
        
        # Step 1: Create authentication token
        print("\n🔑 Creating authentication token...")
        token = create_auth_token("demo@example.com")
        demo.set_token(token)
        print("   ✅ Token created")
        
        # Step 2: Verify authentication
        print("\n👤 Verifying authentication...")
        user = demo.get_user_info()
        print(f"   ✅ Authenticated as: {user['email']}")
        
        # Step 3: Create customer data file
        print("\n📊 Creating customer data file...")
        data_file_path = demo.create_customer_data_file()
        print(f"   ✅ Created temporary CSV file: {os.path.basename(data_file_path)}")
        
        # Step 4: Upload the data file
        print("\n📤 Uploading data file...")
        upload_result = demo.upload_file(data_file_path)
        file_id = upload_result['provider_file_id']
        print(f"   ✅ Uploaded file: {upload_result['file_name']} (ID: {file_id})")
        
        # Step 5: Create an agent with code interpreter and the uploaded file
        print("\n🤖 Creating agent with data analysis capabilities...")
        agent = demo.create_agent(
            name="Data Analysis Assistant",
            description="An agent capable of analyzing customer data using code interpreter",
            instructions="You are a data analyst assistant. You can analyze CSV data, create visualizations, and provide insights. When analyzing data, always start by examining the structure and contents of the file.",
            file_ids=[file_id]
        )
        agent_id = agent['agent_id']
        print(f"   ✅ Created agent: {agent['name']} (ID: {agent_id})")
        print(f"       Agent has code_interpreter tool and access to the customer data file")
        
        # Step 6: Get agent details
        print("\n🔍 Getting agent details...")
        agent_details = demo.get_agent_details(agent_id)
        print(f"   ✅ Agent: {agent_details['name']}")
        print(f"       Model: {agent_details['model']}")
        print(f"       Tools: {len(agent_details['tools'])} tools configured")
        tool_resources = agent_details.get('tool_resources')
        if tool_resources and isinstance(tool_resources, dict):
            code_interpreter = tool_resources.get('code_interpreter', {})
            if code_interpreter:
                ci_files = code_interpreter.get('file_ids', [])
                print(f"       Code Interpreter Files: {len(ci_files)} file(s)")
        else:
            print(f"       Tool Resources: Not configured")
        
        # Step 7: Create a thread
        print("\n💬 Creating conversation thread...")
        thread = demo.create_thread("Customer Data Analysis Chat")
        thread_id = thread['id']
        print(f"   ✅ Created thread: {thread['name']} (ID: {thread_id})")
        
        # Step 8: Start data analysis conversation
        print("\n💭 Starting data analysis conversation...")
        
        # First message - Introduction and data exploration
        prompt1 = "Hello! I've uploaded a customer data file. Can you first examine the data and tell me what information it contains?"
        print(f"   👤 User: {prompt1}")
        response1 = demo.chat(thread_id, agent_id, prompt1)
        
        # Second message - Analysis question
        prompt2 = "Great! Now can you analyze the customer data and tell me: What is the average purchase amount by subscription tier? And which city has the highest total purchase amount?"
        print(f"\n   👤 User: {prompt2}")
        response2 = demo.chat(thread_id, agent_id, prompt2)
        
        # Third message - Follow-up
        prompt3 = "Excellent analysis! Can you also tell me what percentage of customers are in each subscription tier?"
        print(f"\n   👤 User: {prompt3}")
        response3 = demo.chat(thread_id, agent_id, prompt3)
        
        # Step 9: Check thread messages with detailed information
        print(f"\n📨 Checking conversation history with message details...")
        messages = demo.get_thread_messages(thread_id)
        print(f"   ✅ Thread contains {len(messages)} messages")
        
        # Show detailed message information
        print("\n   📊 Message Details:")
        for i, msg in enumerate(messages, 1):
            print(f"\n   Message {i}:")
            print(f"      ID: {msg.get('id', 'Unknown')}")
            print(f"      Agent ID: {msg.get('agent_id', 'None')}")
            print(f"      Type: {msg.get('type', 'Unknown')}")
            print(f"      Role: {msg.get('role', 'Unknown')}")
            content_preview = msg.get('content', '')[:60]
            if len(msg.get('content', '')) > 60:
                content_preview += "..."
            print(f"      Content: {content_preview}")
        
        # Step 10: Clean up resources
        print(f"\n🧹 Cleaning up resources...")
        cleanup_results = demo.cleanup_all()
        
        # Report cleanup results
        threads_deleted = len(cleanup_results["threads"]["deleted"])
        threads_failed = len(cleanup_results["threads"]["failed"])
        agents_deleted = len(cleanup_results["agents"]["deleted"])
        agents_failed = len(cleanup_results["agents"]["failed"])
        files_deleted = len(cleanup_results["files"]["deleted"])
        files_failed = len(cleanup_results["files"]["failed"])
        temp_files_deleted = len(cleanup_results["temp_files"]["deleted"])
        temp_files_failed = len(cleanup_results["temp_files"]["failed"])
        
        print(f"   ✅ Deleted {threads_deleted} thread(s)")
        print(f"   ✅ Deleted {agents_deleted} agent(s)")
        print(f"   ✅ Deleted {files_deleted} uploaded file(s)")
        print(f"   ✅ Deleted {temp_files_deleted} temporary file(s)")
        
        if threads_failed > 0:
            print(f"   ⚠️ Failed to delete {threads_failed} thread(s)")
        if agents_failed > 0:
            print(f"   ⚠️ Failed to delete {agents_failed} agent(s)")
        if files_failed > 0:
            print(f"   ⚠️ Failed to delete {files_failed} uploaded file(s)")
        if temp_files_failed > 0:
            print(f"   ⚠️ Failed to delete {temp_files_failed} temporary file(s)")
        
        print(f"\n🎉 Comprehensive data analysis demo completed successfully!")
        print(f"   • Created customer data file and uploaded it")
        print(f"   • Created agent with code interpreter capabilities")
        print(f"   • Analyzed customer data with AI-powered insights")
        print(f"   • Cleaned up all resources including temporary files")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the REST API server.")
        print("   Make sure the server is running:")
        print("   uvicorn bondable.rest.main:app --reload")
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response.status_code == 401:
            print("   Authentication failed - check your JWT configuration")
        elif e.response.status_code == 404:
            print("   Endpoint not found - check API server configuration")
        else:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
        
        # Attempt cleanup even if there was an error
        print("\n🧹 Attempting cleanup after error...")
        cleanup_results = demo.cleanup_all()
        threads_cleaned = len(cleanup_results['threads']['deleted'])
        agents_cleaned = len(cleanup_results['agents']['deleted']) 
        files_cleaned = len(cleanup_results['files']['deleted'])
        temp_files_cleaned = len(cleanup_results['temp_files']['deleted'])
        print(f"   Cleaned up {threads_cleaned} threads, {agents_cleaned} agents, {files_cleaned} files, and {temp_files_cleaned} temp files")
                
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
        # Attempt cleanup even if there was an error
        print("\n🧹 Attempting cleanup after error...")
        cleanup_results = demo.cleanup_all()
        threads_cleaned = len(cleanup_results['threads']['deleted'])
        agents_cleaned = len(cleanup_results['agents']['deleted']) 
        files_cleaned = len(cleanup_results['files']['deleted'])
        temp_files_cleaned = len(cleanup_results['temp_files']['deleted'])
        print(f"   Cleaned up {threads_cleaned} threads, {agents_cleaned} agents, {files_cleaned} files, and {temp_files_cleaned} temp files")


if __name__ == "__main__":
    main()