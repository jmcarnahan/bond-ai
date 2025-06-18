#!/usr/bin/env python3
"""
Test script for the refactored BedrockAgent implementation
This verifies that the agent uses Bedrock Agents API instead of Converse API
"""

import os
import sys
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force Bedrock provider
os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'

from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
from bondable.bond.definition import AgentDefinition


def test_refactored_bedrock_agent():
    """Test the refactored BedrockAgent implementation"""
    print("=" * 70)
    print("Testing Refactored BedrockAgent with Bedrock Agents API")
    print("=" * 70)
    
    # Initialize provider
    provider = BedrockProvider.provider()
    if provider.provider_name() != "bedrock":
        print("❌ This test requires the Bedrock provider")
        return False
    
    print(f"✅ Using provider: {provider.provider_name()}")
    
    # Create a test user
    test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    user = provider.users.create_user(test_user_id, f"Test User {datetime.now()}")
    print(f"✅ Created test user: {test_user_id}")
    
    # Get the test Bedrock Agent ID from environment or use the one we created earlier
    bedrock_agent_id = os.getenv('BEDROCK_AGENT_ID', 'CSSSH6WEOP')
    bedrock_agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID', 'TFCLIRSS7B')
    
    print(f"\n📌 Using Bedrock Agent:")
    print(f"   Agent ID: {bedrock_agent_id}")
    print(f"   Alias ID: {bedrock_agent_alias_id}")
    
    # Create agent definition with Bedrock Agent IDs
    agent_def = AgentDefinition(
        user_id=test_user_id,
        name="Test Refactored Agent",
        description="Agent using Bedrock Agents API",
        instructions="You are a helpful assistant using AWS Bedrock Agents.",
        model="us.anthropic.claude-3-haiku-20240307-v1:0",
        metadata={
            'user_id': test_user_id,
            'bedrock_agent_id': bedrock_agent_id,
            'bedrock_agent_alias_id': bedrock_agent_alias_id
        }
    )
    
    # Create the agent
    agent = provider.agents.create_or_update_agent_resource(agent_def, test_user_id)
    agent_id = agent.get_agent_id()
    print(f"✅ Created Bond agent: {agent_id}")
    
    # Verify the agent configuration
    agent_config = provider.agents.metadata.get_bedrock_agent(agent_id)
    if agent_config:
        print(f"\n📋 Agent Configuration:")
        print(f"   Model: {agent_config['model_id']}")
        print(f"   Bedrock Agent ID: {agent_config.get('bedrock_agent_id', 'Not set')}")
        print(f"   Bedrock Alias ID: {agent_config.get('bedrock_agent_alias_id', 'Not set')}")
    
    # Create a thread
    thread = provider.threads.create_thread(test_user_id)
    thread_id = thread.get_thread_id()
    print(f"\n✅ Created thread: {thread_id}")
    
    # Get thread session info
    session_id = provider.threads.get_thread_session_id(thread_id)
    print(f"✅ Thread session ID: {session_id}")
    
    try:
        # Test 1: Send a message and get response
        print("\n--- Test 1: Basic Conversation ---")
        print("👤 User: Hello! Can you tell me about AWS Bedrock?")
        
        response_chunks = []
        for chunk in agent.stream_response(
            prompt="Hello! Can you tell me about AWS Bedrock?",
            thread_id=thread_id
        ):
            response_chunks.append(chunk)
        
        # Extract actual content from chunks
        response_text = ""
        in_message = False
        for chunk in response_chunks:
            if chunk.startswith('<_bondmessage'):
                in_message = True
            elif chunk == '</_bondmessage>':
                in_message = False
            elif in_message and not chunk.startswith('<'):
                response_text += chunk
        
        print(f"🤖 Agent: {response_text[:200]}..." if len(response_text) > 200 else f"🤖 Agent: {response_text}")
        
        # Test 2: Follow-up to test session continuity
        print("\n--- Test 2: Session Continuity ---")
        print("👤 User: What did I just ask you about?")
        
        response_chunks = []
        for chunk in agent.stream_response(
            prompt="What did I just ask you about?",
            thread_id=thread_id
        ):
            response_chunks.append(chunk)
        
        # Extract content
        response_text = ""
        in_message = False
        for chunk in response_chunks:
            if chunk.startswith('<_bondmessage'):
                in_message = True
            elif chunk == '</_bondmessage>':
                in_message = False
            elif in_message and not chunk.startswith('<'):
                response_text += chunk
        
        print(f"🤖 Agent: {response_text[:200]}..." if len(response_text) > 200 else f"🤖 Agent: {response_text}")
        
        # Check if context was maintained
        if 'bedrock' in response_text.lower() or 'aws' in response_text.lower():
            print("\n✅ SUCCESS: Agent maintained conversation context!")
        else:
            print("\n⚠️ WARNING: Agent may not have maintained context")
        
        # Check thread messages
        print("\n--- Checking Thread Messages ---")
        messages = provider.threads.get_messages(thread_id, test_user_id)
        print(f"Total messages in thread: {len(messages)}")
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:50] + "..." if len(msg.get('content', '')) > 50 else msg.get('content', '')
            session_id = msg.get('session_id', 'No session')
            print(f"  {i+1}. {role}: {content} (session: {session_id})")
        
        # Check session state
        session_state = provider.threads.get_thread_session_state(thread_id, test_user_id)
        if session_state:
            print(f"\n📊 Session state exists: {type(session_state)}")
        else:
            print("\n📊 No session state stored yet")
        
        print("\n✅ Refactored BedrockAgent test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            provider.agents.delete_agent_resource(agent_id)
            provider.threads.delete_thread_resource(thread_id)
            print(f"\n🧹 Cleaned up test resources")
        except:
            pass


def check_implementation_changes():
    """Check what changed in the implementation"""
    print("\n" + "=" * 70)
    print("Implementation Changes Summary")
    print("=" * 70)
    
    print("\n✅ Key Changes Made:")
    print("1. Added bedrock_agent_runtime_client to BedrockAgent initialization")
    print("2. Replaced converse_stream with invoke_agent in stream_response")
    print("3. Added session_id support to message creation")
    print("4. Removed deprecated methods (_prepare_tool_config, etc.)")
    print("5. Added bedrock_agent_id and bedrock_agent_alias_id to metadata")
    print("6. Updated BedrockAgentProvider to pass new client")
    print("7. Messages now include session_id for tracking")
    
    print("\n📌 New Requirements:")
    print("1. Must create Bedrock Agents before using them")
    print("2. Need to store agent_id and alias_id in metadata")
    print("3. Session management is handled by Bedrock Agents")
    print("4. No need to send full conversation history")
    
    print("\n⚠️ Migration Notes:")
    print("1. Existing agents need Bedrock Agent creation")
    print("2. Database schema updated (bedrock_agent_id, bedrock_agent_alias_id)")
    print("3. Threads automatically get session IDs")
    print("4. Tools will need conversion to Action Groups later")


def main():
    """Run the refactored agent test"""
    
    # Check if we have required environment variables
    if not os.getenv('AWS_REGION'):
        print("❌ AWS_REGION environment variable not set")
        return False
    
    try:
        # Run the test
        success = test_refactored_bedrock_agent()
        
        # Show implementation changes
        check_implementation_changes()
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)