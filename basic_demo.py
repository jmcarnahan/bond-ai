#!/usr/bin/env python3
"""
Basic Bond AI REST API demo - tests core functionality without chat streaming.

This version avoids the streaming chat issue and focuses on basic CRUD operations.
"""

import requests
from datetime import datetime, timedelta, timezone
from jose import jwt


def create_auth_token() -> str:
    """Create a JWT token using Bond's JWT configuration."""
    try:
        from bondable.bond.config import Config
        jwt_config = Config.config().get_jwt_config()
        
        token_data = {
            "sub": "demo@example.com",
            "name": "Demo User",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        
        token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        return token
        
    except Exception as e:
        print(f"Error creating token: {e}")
        raise


def main():
    print("🤖 Basic Bond AI Demo")
    print("=" * 30)
    
    base_url = "http://localhost:8000"
    
    try:
        # Step 1: Create authentication token
        print("🔑 Creating authentication token...")
        token = create_auth_token()
        headers = {"Authorization": f"Bearer {token}"}
        print("   ✅ Token created")
        
        # Step 2: Test health endpoint
        print("\n🏥 Testing health endpoint...")
        response = requests.get(f"{base_url}/health")
        response.raise_for_status()
        print(f"   ✅ API health: {response.json()}")
        
        # Step 3: Get current user
        print("\n👤 Testing user authentication...")
        response = requests.get(f"{base_url}/users/me", headers=headers)
        response.raise_for_status()
        user = response.json()
        print(f"   ✅ Authenticated as: {user['email']}")
        
        # Step 4: List existing agents
        print("\n📋 Listing existing agents...")
        response = requests.get(f"{base_url}/agents", headers=headers)
        response.raise_for_status()
        agents = response.json()
        print(f"   ✅ Found {len(agents)} existing agents")
        
        # Step 5: Create a simple agent
        print("\n🤖 Creating new agent...")
        agent_data = {
            "name": "Basic Demo Agent",
            "description": "A basic test agent",
            "instructions": "You are a helpful assistant.",
            "model": "gpt-3.5-turbo",
            "tools": [],
            "metadata": {"demo": "true", "created_by": "basic_demo_script"}
        }
        
        response = requests.post(f"{base_url}/agents", headers=headers, json=agent_data)
        response.raise_for_status()
        agent = response.json()
        print(f"   ✅ Agent created: {agent['name']} (ID: {agent['agent_id']})")
        
        # Step 6: Get agent details
        print("\n🔍 Getting agent details...")
        response = requests.get(f"{base_url}/agents/{agent['agent_id']}", headers=headers)
        response.raise_for_status()
        agent_details = response.json()
        print(f"   ✅ Agent details: {agent_details['name']}")
        print(f"       Model: {agent_details['model']}")
        print(f"       Tools: {len(agent_details['tools'])} tools")
        
        # Step 7: Create a thread
        print("\n💬 Creating thread...")
        thread_data = {"name": "Basic Demo Thread"}
        
        response = requests.post(f"{base_url}/threads", headers=headers, json=thread_data)
        response.raise_for_status()
        thread = response.json()
        print(f"   ✅ Thread created: {thread['name']} (ID: {thread['id']})")
        
        # Step 8: List threads
        print("\n📋 Listing threads...")
        response = requests.get(f"{base_url}/threads", headers=headers)
        response.raise_for_status()
        threads = response.json()
        print(f"   ✅ Found {len(threads)} threads")
        
        # Step 9: Get thread messages (should be empty)
        print("\n📨 Getting thread messages...")
        response = requests.get(f"{base_url}/threads/{thread['id']}/messages", headers=headers)
        response.raise_for_status()
        messages = response.json()
        print(f"   ✅ Thread has {len(messages)} messages")
        
        # Step 10: Clean up thread
        print("\n🧹 Cleaning up thread...")
        response = requests.delete(f"{base_url}/threads/{thread['id']}", headers=headers)
        if response.status_code == 204:
            print("   ✅ Thread deleted successfully")
        else:
            print(f"   ⚠️ Thread deletion returned status: {response.status_code}")
        
        print(f"\n🎉 Basic demo complete!")
        print(f"   Created agent: {agent['name']} (ID: {agent['agent_id']})")
        print(f"   Note: Agent is kept for future use. Chat functionality needs debugging.")
        
    except requests.exceptions.ConnectionError:
        print("❌ Can't connect to API server. Make sure it's running:")
        print("   uvicorn bondable.rest.main:app --reload")
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response.status_code == 401:
            print("   Authentication failed - check your JWT configuration")
        else:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response text: {e.response.text}")
                
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()