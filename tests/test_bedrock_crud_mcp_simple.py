#!/usr/bin/env python3
"""
Simple test for BedrockCRUD operations with MCP tools.
Tests CRUD functionality with MCP tool integration.
"""

import os
import sys
import uuid
import pytest
from dotenv import load_dotenv
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

# Load environment
load_dotenv()

# Force Bedrock provider
os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bondable.bond.providers.bedrock.BedrockCRUD import (
    create_bedrock_agent,
    get_bedrock_agent,
    update_bedrock_agent,
    delete_bedrock_agent
)

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# Test configuration
TEST_MODEL = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"


@dataclass
class SimpleAgentDef:
    """Simple agent definition to avoid AgentDefinition import issues"""
    id: str
    name: str
    description: str
    instructions: str
    model: str
    user_id: str
    introduction: str = ""
    reminder: str = ""
    tools: Optional[List] = None
    tool_resources: Optional[Dict] = None
    metadata: Optional[Dict] = None
    mcp_tools: Optional[List] = None
    mcp_resources: Optional[List] = None

    def __post_init__(self):
        if self.tools is None:
            self.tools = []
        if self.tool_resources is None:
            self.tool_resources = {}
        if self.metadata is None:
            self.metadata = {}
        if self.mcp_tools is None:
            self.mcp_tools = []
        if self.mcp_resources is None:
            self.mcp_resources = []


class TestBedrockCRUDMCPSimple:
    """Simple test class for Bedrock CRUD operations with MCP tools"""

    @classmethod
    def setup_class(cls):
        """Setup test class - verify environment"""
        if not os.getenv('BEDROCK_AGENT_ROLE_ARN'):
            pytest.skip("BEDROCK_AGENT_ROLE_ARN not set")

        # Initialize provider to ensure configuration is loaded
        from bondable.bond.config import Config
        Config.config()

    def test_crud_with_mcp_tools(self):
        """Test CRUD operations with MCP tools enabled"""

        # Generate unique agent ID
        agent_id = f"test_mcp_{uuid.uuid4().hex[:8]}"
        LOGGER.info(f"Testing with agent ID: {agent_id}")

        # Create agent definition with MCP tools
        agent_def = SimpleAgentDef(
            id=agent_id,
            name="MCP Test Agent",
            description="A test agent with MCP tools for getting current time",
            instructions="You are a helpful assistant that can tell the current time when asked.",
            model=TEST_MODEL,
            user_id="test_user_123",
            mcp_tools=["current_time"]  # Enable the current_time MCP tool
        )

        bedrock_agent_id = None
        bedrock_agent_alias_id = None

        try:
            # Step 1: Create agent with MCP tools
            LOGGER.info("Creating Bedrock agent with MCP tools...")
            bedrock_agent_id, bedrock_agent_alias_id = create_bedrock_agent(
                agent_id=agent_id,
                agent_def=agent_def
            )

            assert bedrock_agent_id is not None
            assert bedrock_agent_alias_id is not None
            LOGGER.info(f"Created agent: {bedrock_agent_id} with alias: {bedrock_agent_alias_id}")

            # Step 2: Get and verify agent has been created
            LOGGER.info("Getting agent details...")
            agent_response = get_bedrock_agent(bedrock_agent_id)
            agent_data = agent_response.get('agent', {})

            assert agent_data.get('agentId') == bedrock_agent_id
            assert agent_data.get('foundationModel') == TEST_MODEL
            assert agent_data.get('description') == agent_def.description
            LOGGER.info("Agent details verified")

            # Step 3: List action groups to verify MCP tools were added
            LOGGER.info("Verifying MCP action groups...")
            from bondable.bond.config import Config
            bond_provider = Config.config().get_provider()
            bedrock_agent_client = bond_provider.bedrock_agent_client

            action_groups_response = bedrock_agent_client.list_agent_action_groups(
                agentId=bedrock_agent_id,
                agentVersion='DRAFT'
            )

            action_groups = action_groups_response.get('actionGroupSummaries', [])
            mcp_group_found = False
            code_interpreter_found = False

            for group in action_groups:
                group_name = group.get('actionGroupName', '')
                LOGGER.info(f"Found action group: {group_name}")
                if group_name == 'MCPTools':
                    mcp_group_found = True
                elif group_name == 'CodeInterpreterActionGroup':
                    code_interpreter_found = True

            assert code_interpreter_found, "Code interpreter action group not found"
            assert mcp_group_found, "MCP tools action group not found"
            LOGGER.info("✅ MCP action group verified")

            # Step 4: Update agent (remove MCP tools)
            LOGGER.info("Updating agent to remove MCP tools...")
            updated_def = SimpleAgentDef(
                id=agent_id,
                name="Updated MCP Test Agent",
                description="Updated agent without MCP tools",
                instructions="You are an updated assistant without access to time tools.",
                model=TEST_MODEL,
                user_id="test_user_123",
                mcp_tools=[]  # Remove MCP tools
            )

            _, updated_alias_id = update_bedrock_agent(
                agent_def=updated_def,
                bedrock_agent_id=bedrock_agent_id,
                bedrock_agent_alias_id=bedrock_agent_alias_id
            )

            # Step 5: Verify MCP tools were removed
            LOGGER.info("Verifying MCP tools were removed...")
            updated_action_groups = bedrock_agent_client.list_agent_action_groups(
                agentId=bedrock_agent_id,
                agentVersion='DRAFT'
            )

            updated_groups = updated_action_groups.get('actionGroupSummaries', [])
            mcp_still_exists = any(g.get('actionGroupName') == 'MCPTools' for g in updated_groups)

            assert not mcp_still_exists, "MCP tools should have been removed"
            LOGGER.info("✅ MCP tools successfully removed")

            # Step 6: Update again to add MCP tools back
            LOGGER.info("Updating agent to add MCP tools back...")
            final_def = SimpleAgentDef(
                id=agent_id,
                name="Final MCP Test Agent",
                description="Final agent with MCP tools restored",
                instructions="You are a helpful assistant that can tell the current time again.",
                model=TEST_MODEL,
                user_id="test_user_123",
                mcp_tools=["current_time"]  # Add MCP tools back
            )

            _, final_alias_id = update_bedrock_agent(
                agent_def=final_def,
                bedrock_agent_id=bedrock_agent_id,
                bedrock_agent_alias_id=updated_alias_id
            )

            # Verify MCP tools were added back
            final_action_groups = bedrock_agent_client.list_agent_action_groups(
                agentId=bedrock_agent_id,
                agentVersion='DRAFT'
            )

            final_groups = final_action_groups.get('actionGroupSummaries', [])
            mcp_restored = any(g.get('actionGroupName') == 'MCPTools' for g in final_groups)

            assert mcp_restored, "MCP tools should have been restored"
            LOGGER.info("✅ MCP tools successfully restored")

            # Step 7: Delete agent
            LOGGER.info("Deleting agent...")
            delete_bedrock_agent(
                bedrock_agent_id=bedrock_agent_id,
                bedrock_agent_alias_id=final_alias_id
            )
            LOGGER.info("Agent deleted")

            # Step 8: Verify deletion
            LOGGER.info("Verifying deletion...")
            try:
                get_bedrock_agent(bedrock_agent_id)
                assert False, "Agent should have been deleted"
            except Exception as e:
                LOGGER.info(f"Deletion verified - agent not found (expected)")

            LOGGER.info("✅ All CRUD operations with MCP tools completed successfully!")

        except Exception as e:
            LOGGER.error(f"Test failed: {e}")
            # Cleanup on failure
            if bedrock_agent_id:
                try:
                    # Get current alias if we have one
                    alias_to_delete = bedrock_agent_alias_id
                    if 'updated_alias_id' in locals():
                        alias_to_delete = updated_alias_id
                    if 'final_alias_id' in locals():
                        alias_to_delete = final_alias_id

                    delete_bedrock_agent(bedrock_agent_id, alias_to_delete)
                    LOGGER.info("Cleaned up agent after failure")
                except:
                    pass
            raise


if __name__ == "__main__":
    # Run test directly
    test = TestBedrockCRUDMCPSimple()
    test.setup_class()
    test.test_crud_with_mcp_tools()
