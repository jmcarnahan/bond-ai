#!/usr/bin/env python3
"""
Simple test to verify BedrockAgent can handle images from code interpreter.
This test creates an agent and requests it to generate a chart.
"""

import os
import sys
import json
import base64
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition


def test_image_generation():
    """Test that agent can generate and stream images"""
    print("=== Testing Bedrock Agent Image Generation ===\n")
    
    # Set provider to Bedrock
    os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'
    
    # Get provider
    config = Config.config()
    provider = config.get_provider()
    print(f"Provider: {type(provider).__name__}")
    print(f"Default model: {provider.get_default_model()}\n")
    
    # Create agent
    agent_def = AgentDefinition(
        user_id="test-image-user",
        name="Chart Generator",
        description="An agent that generates charts",
        instructions="You are a helpful assistant that can create visualizations using code interpreter.",
        model=provider.get_default_model()
    )
    
    agent = provider.agents.create_or_update_agent(
        agent_def=agent_def,
        user_id="test-image-user"
    )
    agent_id = agent.get_agent_id()
    print(f"Created agent: {agent_id}")
    
    # Create thread
    thread = provider.threads.create_thread(
        user_id="test-image-user",
        name="Image Test Thread"
    )
    thread_id = thread.thread_id
    print(f"Created thread: {thread_id}\n")
    
    try:
        # Request image generation
        prompt = "Using code interpreter, create a simple bar chart showing sales data for 5 products (Product A: 100, Product B: 150, Product C: 80, Product D: 120, Product E: 90)"
        print(f"Prompt: {prompt}\n")
        print("Streaming response...\n")
        
        # Track messages
        messages = []
        current_message = None
        full_text = ""
        
        for chunk in agent.stream_response(thread_id=thread_id, prompt=prompt):
            if chunk.startswith('<_bondmessage'):
                # New message starting
                if 'type="message"' in chunk:
                    print("\n[TEXT MESSAGE START]")
                    current_message = {"type": "message", "content": ""}
                elif 'type="image_file"' in chunk:
                    print("\n[IMAGE MESSAGE START]")
                    current_message = {"type": "image_file", "content": ""}
                elif 'type="file_link"' in chunk:
                    print("\n[FILE LINK MESSAGE START]")
                    current_message = {"type": "file_link", "content": ""}
            elif chunk == '</_bondmessage>':
                # Message ending
                if current_message:
                    messages.append(current_message)
                    if current_message["type"] == "message":
                        print(f"\n[TEXT MESSAGE END] Length: {len(current_message['content'])} chars")
                    elif current_message["type"] == "image_file":
                        print(f"\n[IMAGE MESSAGE END] Data URL length: {len(current_message['content'])} chars")
                    elif current_message["type"] == "file_link":
                        print(f"\n[FILE LINK MESSAGE END] Content: {current_message['content']}")
                    current_message = None
            elif current_message is not None:
                # Message content
                current_message["content"] += chunk
                if current_message["type"] == "message":
                    # Print text content as it arrives
                    print(chunk, end='', flush=True)
                    full_text += chunk
        
        print(f"\n\n=== Summary ===")
        print(f"Total messages received: {len(messages)}")
        
        # Analyze messages
        text_messages = [m for m in messages if m["type"] == "message"]
        image_messages = [m for m in messages if m["type"] == "image_file"]
        file_messages = [m for m in messages if m["type"] == "file_link"]
        
        print(f"Text messages: {len(text_messages)}")
        print(f"Image messages: {len(image_messages)}")
        print(f"File link messages: {len(file_messages)}")
        
        # Verify images
        if image_messages:
            print("\n=== Image Analysis ===")
            for i, img_msg in enumerate(image_messages):
                content = img_msg["content"]
                if content.startswith("data:image/"):
                    # Extract MIME type
                    mime_end = content.find(";base64,")
                    if mime_end > 0:
                        mime_type = content[5:mime_end]  # Skip "data:"
                        print(f"Image {i+1}: MIME type = {mime_type}")
                        
                        # Verify base64 data
                        try:
                            base64_data = content[mime_end + 8:]  # Skip ";base64,"
                            image_bytes = base64.b64decode(base64_data)
                            print(f"  Size: {len(image_bytes)} bytes")
                            
                            # Save image for manual inspection
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"test_output_{timestamp}_image_{i+1}.png"
                            with open(filename, 'wb') as f:
                                f.write(image_bytes)
                            print(f"  Saved to: {filename}")
                        except Exception as e:
                            print(f"  ERROR: Invalid base64 data - {e}")
                else:
                    print(f"Image {i+1}: ERROR - Not a valid data URL")
        else:
            print("\n⚠️  No images received!")
        
        # Check if response makes sense
        print("\n=== Response Quality Check ===")
        if full_text:
            text_lower = full_text.lower()
            chart_words = ["chart", "graph", "plot", "visualization", "bar", "created", "generated"]
            found_words = [w for w in chart_words if w in text_lower]
            if found_words:
                print(f"✓ Response mentions chart-related words: {', '.join(found_words)}")
            else:
                print("⚠️  Response doesn't mention chart-related words")
        
        return len(image_messages) > 0
        
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        provider.threads.delete_thread(thread_id=thread_id, user_id="test-image-user")
        print(f"Deleted thread: {thread_id}")
        provider.agents.delete_agent(agent_id=agent_id)
        print(f"Deleted agent: {agent_id}")


if __name__ == "__main__":
    try:
        success = test_image_generation()
        if success:
            print("\n✅ Test PASSED - Images were successfully generated and streamed")
            sys.exit(0)
        else:
            print("\n❌ Test FAILED - No images were generated")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)