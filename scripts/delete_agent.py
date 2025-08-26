#!/usr/bin/env python3
"""
Script to delete an agent by ID using the Bond AI agent provider.

Usage:
    python scripts/delete_agent.py --agent-id <agent_id>
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def delete_agent(agent_id: str) -> bool:
    """
    Delete an agent by its ID.
    
    Args:
        agent_id: The ID of the agent to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Determine provider based on agent ID format
        import os
        if agent_id.startswith('bedrock_agent_'):
            os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'
            logger.info("Detected Bedrock agent ID, using Bedrock provider")
        elif agent_id.startswith('asst_'):
            os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.openai.OAIAProvider.OAIAProvider'
            logger.info("Detected OpenAI agent ID, using OpenAI provider")
        
        # Initialize configuration and provider
        config = Config.config()
        provider = config.get_provider()
        
        logger.info(f"Attempting to delete agent with ID: {agent_id}")
        
        # Delete the agent directly without checking existence first
        # This avoids issues with reconstructing AgentDefinition for agents with missing resources
        result = provider.agents.delete_agent(agent_id)
        
        if result:
            logger.info(f"Successfully deleted agent with ID: {agent_id}")
        else:
            logger.warning(f"Agent with ID '{agent_id}' may not exist or was already deleted")
            
        return result
        
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Delete an agent by ID")
    parser.add_argument(
        "--agent-id",
        required=True,
        help="The ID of the agent to delete"
    )
    
    args = parser.parse_args()
    
    # Delete the agent
    success = delete_agent(args.agent_id)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()