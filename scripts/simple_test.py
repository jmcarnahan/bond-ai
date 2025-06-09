#!/usr/bin/env python3
"""
Simple script to create an agent, send a message, and clean up.
Run with: poetry run python simple_agent_test.py
"""

import logging
import threading
import sys

from bondable.bond.config import Config
from bondable.bond.cache import bond_cache_clear
from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.agent import Agent
from bondable.bond.providers.threads import Thread
from bondable.bond.broker import Broker, BrokerConnectionEmpty

# Set up logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

USER_ID = "DEMO_USER"


def display_message(message):
    """Display received messages in a readable format."""
    if message.role == 'system':
        LOGGER.debug(f"Received system message, ignoring {message.message_id}")
        return
    
    if message.type == "text":
        print(f"[{message.role}] {message.clob.get_content()}")
    elif message.type in ["image_file", "image"]:
        print(f"[{message.role}] [Image received]")
        content = message.clob.get_content()
        if content.startswith('data:image'):
            print("  Image data detected (base64 encoded)")
        else:
            print(f"  {content}")
    else:
        print(f"[{message.role}] [{message.type}] {message.clob.get_content()}")


def main():
    """Main function to run the agent test."""
    print("🤖 Starting simple agent test...")
    
    # Clear cache and get config
    bond_cache_clear()
    config = Config.config()
    provider: Provider = config.get_provider()
    
    agent: Agent = None
    thread: Thread = None
    
    try:
        # Create agent
        print("📋 Creating agent...")
        agent = provider.agents.create_or_update_agent(
            AgentDefinition(
                name='Demo Agent',
                description='A helpful assistant for demonstration purposes',
                instructions='You are a helpful assistant. Answer questions clearly and concisely.',
                user_id=USER_ID,
                model="gpt-4.1-nano",
            ),
            user_id=USER_ID,
        )
        print(f"✅ Agent created: {agent.get_agent_id()}")

        # Create thread
        print("🧵 Creating thread...")
        thread = provider.threads.create_thread(user_id=USER_ID, name="Demo Thread")
        print(f"✅ Thread created: {thread.thread_id}")

        # Connect to broker
        print("🔌 Connecting to broker...")
        broker = Broker.broker()
        conn = broker.connect(thread_id=thread.thread_id, subscriber_id=USER_ID)
        print("✅ Connected to broker")

        # Send message
        message = "Hello! Can you tell me a short joke?"
        print(f"💬 Sending message: '{message}'")
        agent.broadcast_message(message, thread_id=thread.thread_id)
        
        # Start response thread
        sys_thread = threading.Thread(
            target=agent.broadcast_response, 
            args=(None, thread.thread_id), 
            daemon=True
        )
        sys_thread.start()

        # Listen for responses
        print("👂 Listening for responses...")
        while True:
            try:
                bond_msg = conn.wait_for_message(timeout=10)
                if bond_msg is None:
                    print("⏰ Timeout waiting for message")
                    break
                
                display_message(bond_msg)
                
                if bond_msg.is_done:
                    print("✅ Conversation complete")
                    break
                    
            except BrokerConnectionEmpty:
                continue
            except Exception as e:
                LOGGER.error(f"❌ Error receiving message: {e}")
                break

        sys_thread.join(timeout=5)
        conn.close()
        print("🔐 Connection closed")

    except Exception as e:
        print(f"❌ Error during execution: {e}")
        return 1
    
    finally:
        # Cleanup
        print("🧹 Cleaning up...")
        try:
            if agent is not None:
                provider.agents.delete_agent(agent.get_agent_id())
                print("✅ Agent deleted")
        except Exception as e:
            print(f"⚠️  Error deleting agent: {e}")
        
        try:
            if thread is not None:
                provider.threads.delete_thread(thread_id=thread.thread_id, user_id=USER_ID)
                print("✅ Thread deleted")
        except Exception as e:
            print(f"⚠️  Error deleting thread: {e}")
    
    print("🎉 Demo complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
