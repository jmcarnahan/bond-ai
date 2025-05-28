#!/usr/bin/env python3
"""
Simple demo script for the Bond AI REST API.

This script demonstrates:
1. Automatic authentication (creates token programmatically)
2. Creating a simple agent (no functions or files)
3. Creating a thread
4. Running a chat session
5. Cleaning up resources

Prerequisites:
- REST API server running (e.g., uvicorn bondable.rest.main:app --reload)
- Google OAuth credentials in environment or .env file
"""

import requests
import json
import time
import os
from typing import Optional
from datetime import datetime, timedelta, timezone
from jose import jwt


def create_demo_token(user_email: str = "demo@example.com") -> str:
    """Create a demo JWT token for testing using Bond's JWT configuration."""
    try:
        # Import Bond config to get JWT settings
        from bondable.bond.config import Config
        jwt_config = Config.config().get_jwt_config()
        
        # Create token data
        token_data = {
            "sub": user_email,
            "name": "Demo User",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        
        # Create JWT token using Bond's settings
        token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        return token
        
    except Exception as e:
        print(f"Error creating token with Bond config: {e}")
        raise


class BondAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {}
        
        if self.token:
            self.headers['Authorization'] = f'Bearer {self.token}'
    
    def set_token(self, token: str):
        """Set the authentication token."""
        self.token = token
        self.headers['Authorization'] = f'Bearer {token}'
    
    def create_agent(self, name: str, description: str = None, instructions: str = None) -> dict:
        """Create a simple agent."""
        payload = {
            "name": name,
            "description": description or f"A simple agent named {name}",
            "instructions": instructions or "You are a helpful assistant. Be concise and friendly.",
            "model": "gpt-3.5-turbo",
            "tools": [],
            "metadata": {"demo": "true"}
        }
        
        response = requests.post(f"{self.base_url}/agents", headers=self.headers, json=payload)
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
        
        # Collect streaming response
        full_response = ""
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                full_response += chunk
                print(chunk, end='', flush=True)
        
        return full_response
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread."""
        response = requests.delete(f"{self.base_url}/threads/{thread_id}", headers=self.headers)
        return response.status_code == 204
    
    def get_agents(self) -> list:
        """Get list of agents."""
        response = requests.get(f"{self.base_url}/agents", headers=self.headers)
        response.raise_for_status()
        return response.json()


def main():
    """Main demo function."""
    print("🤖 Bond AI REST API Demo")
    print("=" * 40)
    
    # Initialize client
    client = BondAPIClient()
    
    # Try to get token from environment, otherwise create demo token
    token = os.getenv('TOKEN')
    if token:
        print("📱 Using token from environment variable")
        client.set_token(token)
    else:
        print("🔑 Creating demo authentication token...")
        try:
            demo_token = create_demo_token("demo@example.com")
            client.set_token(demo_token)
            print("   ✅ Demo token created successfully")
        except Exception as e:
            print(f"❌ Error creating demo token: {e}")
            print("   Make sure you have the 'python-jose' package installed:")
            print("   pip install python-jose[cryptography]")
            return
    
    try:
        # Step 1: Create a simple agent
        print("\n1️⃣ Creating a simple agent...")
        agent = client.create_agent(
            name="Demo Assistant",
            description="A simple demo agent for testing",
            instructions="You are a helpful assistant. Keep responses brief and friendly."
        )
        agent_id = agent['agent_id']
        print(f"   ✅ Created agent: {agent['name']} (ID: {agent_id})")
        
        # Step 2: Create a thread
        print("\n2️⃣ Creating a thread...")
        thread = client.create_thread("Demo Conversation")
        thread_id = thread['id']
        print(f"   ✅ Created thread: {thread['name']} (ID: {thread_id})")
        
        # Step 3: Run a chat session
        print("\n3️⃣ Starting chat session...")
        prompt = "Hello! Can you tell me a brief joke about programming?"
        print(f"   👤 User: {prompt}")
        print(f"   🤖 Assistant: ", end='')
        
        response = client.chat(thread_id, agent_id, prompt)
        print()  # New line after streaming response
        
        # Step 4: Another chat message
        print("\n4️⃣ Sending another message...")
        prompt2 = "Thanks! Can you explain what an API is in one sentence?"
        print(f"   👤 User: {prompt2}")
        print(f"   🤖 Assistant: ", end='')
        
        response2 = client.chat(thread_id, agent_id, prompt2)
        print()  # New line after streaming response
        
        # Step 5: Clean up (optional)
        print("\n5️⃣ Cleaning up...")
        if client.delete_thread(thread_id):
            print(f"   ✅ Deleted thread: {thread_id}")
        else:
            print(f"   ⚠️ Could not delete thread: {thread_id}")
        
        print("\n🎉 Demo completed successfully!")
        print(f"   Agent ID: {agent_id} (kept for future use)")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the REST API server.")
        print("   Make sure the server is running on http://localhost:8000")
        print("   Start with: uvicorn bondable.rest.main:app --reload")
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response.status_code == 401:
            print("   Check your authentication token.")
        elif e.response.status_code == 404:
            print("   Check that the API endpoints are correct.")
        else:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
                
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()