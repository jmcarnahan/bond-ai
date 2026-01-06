#!/usr/bin/env python3
"""
Create a Bedrock agent with MCP tools for testing.

Usage:
    poetry run python scripts/create_mcp_agent.py
"""

from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition

# Get provider
config = Config.config()
provider = config.get_provider()

print("Creating Bedrock Agent with MCP Tools...")
print()

# Define agent with MCP tools
agent_def = AgentDefinition(
    name="MCP Test Agent",
    description="Test agent with MCP tools for authentication testing",
    instructions="You are a helpful assistant that can use MCP tools. When greeting users, use the greet tool to show authentication information.",
    introduction="Hello! I'm an MCP-enabled agent. I can use tools like greet, current_time, get_user_profile, and more. Try asking me to greet someone!",
    reminder="Use MCP tools when appropriate.",
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    user_id="default",  # Default agent accessible to all users
    mcp_tools=["greet", "current_time", "get_user_profile", "fetch_protected_data", "validate_auth"],
    mcp_resources=[],
    tools=[],
    tool_resources={}
)

# Create agent
print(f"Agent Name: {agent_def.name}")
print(f"MCP Tools: {', '.join(agent_def.mcp_tools)}")
print()

agent = provider.agents.create_agent(agent_def)

print(f"✅ Agent Created Successfully!")
print(f"   Agent ID: {agent.get_agent_id()}")
print(f"   Bedrock Agent ID: {agent.bedrock_agent_id if hasattr(agent, 'bedrock_agent_id') else 'N/A'}")
print()
print("Next Steps:")
print("1. Open the UI at http://localhost:5000")
print("2. Login with Okta (testuser2@bondai.com)")
print("3. Select the 'MCP Test Agent'")
print("4. Ask: 'Please greet Alice'")
print("5. The response should show: 'Hello, Alice! (Authenticated as testuser2@bondai.com)'")
print()
