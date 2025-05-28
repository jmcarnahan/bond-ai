#!/usr/bin/env python3
"""
Super simple Bond AI REST API demo with automatic authentication.

This script automatically creates a valid JWT token using your Bond config,
so no manual OAuth steps are needed!
"""

import requests
from datetime import datetime, timedelta, timezone
from jose import jwt


def create_auth_token() -> str:
    """Create a JWT token using Bond's JWT configuration."""
    try:
        # Import Bond config to get JWT settings
        from bondable.bond.config import Config
        jwt_config = Config.config().get_jwt_config()
        
        # Create token data
        token_data = {
            "sub": "demo@example.com",  # User email
            "name": "Demo User",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        
        # Create JWT token using Bond's settings
        token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        return token
        
    except Exception as e:
        print(f"Error creating token: {e}")
        raise


def main():
    print("🤖 Simple Bond AI Demo")
    print("=" * 30)
    
    base_url = "http://localhost:8000"
    
    try:
        # Step 1: Create authentication token
        print("🔑 Creating authentication token...")
        token = create_auth_token()
        headers = {"Authorization": f"Bearer {token}"}
        print("   ✅ Token created")
        
        # Step 2: Create a simple agent
        print("\n🤖 Creating agent...")
        agent_data = {
            "name": "Simple Demo Agent",
            "description": "A basic demo agent",
            "instructions": "You are a helpful assistant. Keep responses brief.",
            "model": "gpt-3.5-turbo",
            "metadata": {"demo": "true"}
        }
        
        response = requests.post(f"{base_url}/agents", headers=headers, json=agent_data)
        response.raise_for_status()
        agent = response.json()
        print(f"   ✅ Agent created: {agent['name']}")
        
        # Step 3: Create a thread
        print("\n💬 Creating thread...")
        thread_data = {"name": "Demo Chat"}
        
        response = requests.post(f"{base_url}/threads", headers=headers, json=thread_data)
        response.raise_for_status()
        thread = response.json()
        print(f"   ✅ Thread created: {thread['name']}")
        
        # Step 4: Send a chat message
        print("\n💭 Sending chat message...")
        chat_data = {
            "thread_id": thread['id'],
            "agent_id": agent['agent_id'],
            "prompt": "Hello! Tell me a fun fact about Python programming."
        }
        
        print("   👤 User: Hello! Tell me a fun fact about Python programming.")
        print("   🤖 Assistant: ", end='', flush=True)
        
        response = requests.post(f"{base_url}/chat", headers=headers, json=chat_data, stream=True)
        response.raise_for_status()
        
        # Stream the response
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                print(chunk, end='', flush=True)
        print()  # New line
        
        # Step 5: Clean up
        print("\n🧹 Cleaning up...")
        requests.delete(f"{base_url}/threads/{thread['id']}", headers=headers)
        print("   ✅ Thread deleted")
        
        print(f"\n🎉 Demo complete! Agent '{agent['name']}' is ready for more chats.")
        
    except requests.exceptions.ConnectionError:
        print("❌ Can't connect to API server. Make sure it's running:")
        print("   uvicorn bondable.rest.main:app --reload")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()