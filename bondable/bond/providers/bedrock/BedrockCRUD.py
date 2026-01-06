
import os
import uuid
import json
import time
import logging
import base64
import hashlib
from typing import List, Dict, Optional, Any
from botocore.exceptions import ClientError
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.bedrock.BedrockMCP import create_mcp_action_groups


LOGGER = logging.getLogger(__name__)
DEFAULT_TEMPERATURE = 0.0
# Ensure instructions meet minimum length requirement (40 chars for Bedrock)
MIN_INSTRUCTION_LENGTH = 40
DEFAULT_INSTRUCTION = "You are a helpful AI assistant. Be helpful, accurate, and concise in your responses."
AGENT_VERSION = 'DRAFT'


def _get_bedrock_agent_client() -> Any:
    from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
    bond_provider: BedrockProvider = Config.config().get_provider()
    return bond_provider.bedrock_agent_client

def get_bedrock_agent(bedrock_agent_id: str) -> str:
    return _get_bedrock_agent_client().get_agent(agentId=bedrock_agent_id)


def create_bedrock_agent(agent_id: str, agent_def: AgentDefinition, owner_user_id: Optional[str] = None) -> tuple[str, str]:
    """
    Create a Bedrock Agent for the Bond agent.

    Args:
        agent_id: Bond agent ID (used as Bedrock agent name for uniqueness)
        agent_def: Agent definition with configuration
        owner_user_id: User who owns this agent (needed for OAuth token lookup for MCP)

    Returns:
        Tuple of (bedrock_agent_id, bedrock_agent_alias_id)
    """

    bedrock_agent_client = _get_bedrock_agent_client()

    # Get IAM role from environment or use default
    agent_role_arn = os.getenv('BEDROCK_AGENT_ROLE_ARN')
    if not agent_role_arn:
        raise ValueError("BEDROCK_AGENT_ROLE_ARN environment variable must be set")

    instructions = DEFAULT_INSTRUCTION
    if agent_def.instructions:
        instructions = agent_def.instructions.ljust(MIN_INSTRUCTION_LENGTH)

    if agent_def.description is None or agent_def.description.strip() == "":
        agent_def.description = agent_def.name

    try:
        # Step 1: Create the agent
        LOGGER.debug(f"Creating Bedrock Agent with for bond agent {agent_id} with ARN {agent_role_arn}")

        # Use agent_id as the Bedrock agent name for guaranteed uniqueness
        # Bedrock agent names must match pattern: ([0-9a-zA-Z][_-]?){1,100}
        # Since agent_id is a UUID with format "bedrock_agent_<uuid>", we need to clean it
        bedrock_agent_name = agent_id.replace('-', '_')

        create_response = bedrock_agent_client.create_agent(
            agentName=bedrock_agent_name,
            agentResourceRoleArn=agent_role_arn,
            instruction=instructions,
            foundationModel=agent_def.model,
            description=agent_def.description,
            idleSessionTTLInSeconds=3600,  # 1 hour timeout
        )

        bedrock_agent_id = create_response['agent']['agentId']

        # Step 2: Wait for agent to be created
        _wait_for_resource_status('agent', bedrock_agent_id, ['NOT_PREPARED', 'PREPARED'])
        LOGGER.info(f"Successfully created Bedrock Agent: {bedrock_agent_id} for bond agent {agent_id}")

        # Step 3: Enable code interpreter (always enabled for all agents)
        LOGGER.debug(f"Enabling code interpreter for Bedrock Agent {bedrock_agent_id}")
        try:
            code_interpreter_response = bedrock_agent_client.create_agent_action_group(
                agentId=bedrock_agent_id,
                agentVersion=AGENT_VERSION,
                actionGroupName='CodeInterpreterActionGroup',
                parentActionGroupSignature='AMAZON.CodeInterpreter',
                actionGroupState='ENABLED'
            )
            LOGGER.debug(f"Enabled code interpreter: {code_interpreter_response['agentActionGroup']['actionGroupId']} for bond agent {agent_id}")
        except ClientError as e:
            LOGGER.warning(f"Failed to enable code interpreter: {e}")
            # Continue without code interpreter rather than failing

        # Step 4: Prepare the agent with code interpreter enabled
        bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
        _wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])

        # Step 5: Create MCP action groups if any MCP tools specified
        if agent_def.mcp_tools:
            create_mcp_action_groups(bedrock_agent_id, agent_def.mcp_tools, agent_def.mcp_resources or [], user_id=owner_user_id)
            bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
            _wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])
            LOGGER.debug(f"Enabled MCP tools for bond agent {agent_id}")

        # Step 6: Create alias
        alias_name = f"{bedrock_agent_name}_alias_{uuid.uuid4().hex[:8]}"
        LOGGER.debug(f"Creating alias {alias_name} for Bedrock Agent {bedrock_agent_id}")

        alias_response = bedrock_agent_client.create_agent_alias(
            agentId=bedrock_agent_id,
            agentAliasName=alias_name,
            description=f"Alias for Bond agent {agent_id}"
        )

        bedrock_agent_alias_id = alias_response['agentAlias']['agentAliasId']
        _wait_for_resource_status('alias', bedrock_agent_alias_id, ['PREPARED'], agent_id=bedrock_agent_id)

        LOGGER.info(f"Successfully created Bedrock Agent {bedrock_agent_id} with alias {bedrock_agent_alias_id}")
        return bedrock_agent_id, bedrock_agent_alias_id

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        LOGGER.error(f"Failed to create Bedrock Agent: {error_code} - {error_message}")
        raise ValueError(f"Failed to create Bedrock Agent: {error_message}")

    except Exception as e:
        LOGGER.error(f"Unexpected error creating Bedrock Agent: {e}")
        raise



def update_bedrock_agent(agent_def: AgentDefinition, bedrock_agent_id: str, bedrock_agent_alias_id: str, owner_user_id: Optional[str] = None) -> tuple[str, str]:
    """
    Update an existing Bedrock Agent.

    Args:
        agent_def: Updated agent definition
        bedrock_agent_id: Existing Bedrock agent ID
        bedrock_agent_alias_id: Existing Bedrock alias ID
        owner_user_id: User who owns this agent (needed for OAuth token lookup for MCP)

    Returns:
        Tuple of (bedrock_agent_id, bedrock_agent_alias_id) - may return new alias ID if recreated
    """
    bedrock_agent_client = _get_bedrock_agent_client()

    # Get IAM role from environment
    agent_role_arn = os.getenv('BEDROCK_AGENT_ROLE_ARN')
    if not agent_role_arn:
        raise ValueError("BEDROCK_AGENT_ROLE_ARN environment variable must be set")

    instructions = DEFAULT_INSTRUCTION
    if agent_def.instructions:
        instructions = agent_def.instructions.ljust(MIN_INSTRUCTION_LENGTH)

    bedrock_agent_name = agent_def.id.replace('-', '_')
    if agent_def.description is None or agent_def.description.strip() == "":
        agent_def.description = agent_def.name

    try:
        # Step 1: Update the agent configuration
        update_response = bedrock_agent_client.update_agent(
            agentId=bedrock_agent_id,
            agentName=bedrock_agent_name,
            agentResourceRoleArn=agent_role_arn,
            instruction=instructions,
            foundationModel=agent_def.model,
            description=agent_def.description,
            idleSessionTTLInSeconds=3600,  # 1 hour timeout
        )

        # Step 2: Wait for agent to be updated
        _wait_for_resource_status('agent', bedrock_agent_id, ['NOT_PREPARED', 'PREPARED'])
        LOGGER.info(f"Updated Bedrock Agent {bedrock_agent_id}")

        # Step 3: Handle MCP tools - need to check if action groups changed
        # First, get existing action groups
        existing_action_groups = []
        try:
            list_response = bedrock_agent_client.list_agent_action_groups(
                agentId=bedrock_agent_id,
                agentVersion=AGENT_VERSION
            )
            existing_action_groups = list_response.get('actionGroupSummaries', [])
        except ClientError as e:
            LOGGER.warning(f"Failed to list action groups: {e}")

        # Find MCP action group if it exists
        mcp_action_group_id = None
        for group in existing_action_groups:
            if group.get('actionGroupName') == 'MCPTools':
                mcp_action_group_id = group.get('actionGroupId')
                break

        # Update MCP tools if needed
        if agent_def.mcp_tools:
            if mcp_action_group_id:
                # Delete existing MCP action group to replace it
                try:
                    LOGGER.debug(f"Deleting existing MCP action group {mcp_action_group_id}")
                    bedrock_agent_client.delete_agent_action_group(
                        agentId=bedrock_agent_id,
                        agentVersion=AGENT_VERSION,
                        actionGroupId=mcp_action_group_id,
                        skipResourceInUseCheck=True  # Force deletion
                    )
                except ClientError as e:
                    LOGGER.warning(f"Failed to delete existing MCP action group: {e}")

            # Create new MCP action groups
            create_mcp_action_groups(bedrock_agent_id, agent_def.mcp_tools, agent_def.mcp_resources or [], user_id=owner_user_id)
        else:
            # Remove MCP action group if it exists but no MCP tools specified
            if mcp_action_group_id:
                # Note: We'll delete the action group after preparing the agent
                # Store the ID for later deletion
                LOGGER.debug(f"MCP action group {mcp_action_group_id} will be removed after agent preparation")

        # Step 4: Prepare the agent after updates
        LOGGER.debug(f"Preparing agent {bedrock_agent_id} after updates")
        bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
        _wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])

        # Step 4b: Delete MCP action group if marked for deletion
        if not agent_def.mcp_tools and mcp_action_group_id:
            try:
                LOGGER.debug(f"Now deleting MCP action group {mcp_action_group_id}")
                bedrock_agent_client.delete_agent_action_group(
                    agentId=bedrock_agent_id,
                    agentVersion=AGENT_VERSION,
                    actionGroupId=mcp_action_group_id,
                    skipResourceInUseCheck=True  # Force deletion
                )
                # Prepare agent again after deletion
                bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
                _wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])
            except ClientError as e:
                LOGGER.warning(f"Failed to delete MCP action group: {e}")

        # Step 5: Update the alias (aliases are immutable, so we might need to create a new one)
        # Check if we need to update the alias routing configuration
        try:
            alias_response = bedrock_agent_client.get_agent_alias(
                agentId=bedrock_agent_id,
                agentAliasId=bedrock_agent_alias_id
            )
            current_alias = alias_response.get('agentAlias', {})

            # Update alias routing if needed (to point to latest version)
            LOGGER.debug(f"Updating alias {bedrock_agent_alias_id} routing configuration")
            update_alias_response = bedrock_agent_client.update_agent_alias(
                agentId=bedrock_agent_id,
                agentAliasId=bedrock_agent_alias_id,
                agentAliasName=current_alias.get('agentAliasName', f"alias_{bedrock_agent_alias_id}"),
                description=f"Updated alias for Bond agent"
            )

            # Wait for alias to be prepared
            _wait_for_resource_status('alias', bedrock_agent_alias_id, ['PREPARED'], agent_id=bedrock_agent_id)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Alias doesn't exist, create a new one
                LOGGER.warning(f"Alias {bedrock_agent_alias_id} not found, creating new alias")
                alias_name = f"bedrock_agent_{uuid.uuid4().hex[:8]}_alias_{uuid.uuid4().hex[:8]}"

                alias_response = bedrock_agent_client.create_agent_alias(
                    agentId=bedrock_agent_id,
                    agentAliasName=alias_name,
                    description=f"New alias for updated Bond agent"
                )

                bedrock_agent_alias_id = alias_response['agentAlias']['agentAliasId']
                _wait_for_resource_status('alias', bedrock_agent_alias_id, ['PREPARED'], agent_id=bedrock_agent_id)
            else:
                LOGGER.error(f"Error updating alias: {e}")
                raise

        LOGGER.info(f"Successfully updated Bedrock Agent {bedrock_agent_id} with alias {bedrock_agent_alias_id}")
        return bedrock_agent_id, bedrock_agent_alias_id

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        LOGGER.error(f"Failed to update Bedrock Agent: {error_code} - {error_message}")
        raise ValueError(f"Failed to update Bedrock Agent: {error_message}")

    except Exception as e:
        LOGGER.error(f"Unexpected error updating Bedrock Agent: {e}")
        raise

def delete_bedrock_agent(bedrock_agent_id: str, bedrock_agent_alias_id: str):

    bedrock_agent_client = _get_bedrock_agent_client()

    # Delete the Bedrock Agent if it exists
    if bedrock_agent_id:
        try:
            # Delete alias first if it exists and is not the test alias
            if bedrock_agent_alias_id and bedrock_agent_alias_id != 'TSTALIASID':
                try:
                    bedrock_agent_client.delete_agent_alias(
                        agentId=bedrock_agent_id,
                        agentAliasId=bedrock_agent_alias_id
                    )
                    LOGGER.info(f"Deleted Bedrock Agent alias {bedrock_agent_alias_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        LOGGER.warning(f"Error deleting alias {bedrock_agent_alias_id}: {e}")

            # Delete the agent
            LOGGER.info(f"Deleting Bedrock Agent {bedrock_agent_id}")
            bedrock_agent_client.delete_agent(
                agentId=bedrock_agent_id,
                skipResourceInUseCheck=True  # Force delete even if in use
            )
            LOGGER.info(f"Successfully deleted Bedrock Agent {bedrock_agent_id}")

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                LOGGER.info(f"Bedrock Agent {bedrock_agent_id} already deleted")
            else:
                LOGGER.warning(f"Error deleting Bedrock Agent {bedrock_agent_id}: {e}")
                # Don't fail the whole operation if we can't delete the Bedrock Agent



def _wait_for_resource_status(resource_type: str, resource_id: str,
                              target_statuses: List[str], max_attempts: int = 30,
                              delay: int = 2, agent_id: Optional[str] = None):
    """
    Generic method to wait for a resource to reach target status.

    Args:
        resource_type: 'agent' or 'alias'
        resource_id: The resource ID to check
        target_statuses: List of acceptable statuses
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        agent_id: Required for alias resources
    """


    bedrock_agent_client = _get_bedrock_agent_client()

    failed_statuses = {
        'agent': ['CREATE_FAILED', 'PREPARE_FAILED'],
        'alias': ['FAILED']
    }

    for attempt in range(max_attempts):
        try:
            if resource_type == 'agent':
                response = bedrock_agent_client.get_agent(agentId=resource_id)
                current_status = response['agent']['agentStatus']
            else:  # alias
                response = bedrock_agent_client.get_agent_alias(
                    agentId=agent_id,
                    agentAliasId=resource_id
                )
                current_status = response['agentAlias']['agentAliasStatus']

            if current_status in target_statuses:
                LOGGER.debug(f"{resource_type.capitalize()} {resource_id} reached status: {current_status}")
                return

            if current_status in failed_statuses.get(resource_type, []):
                raise ValueError(f"{resource_type.capitalize()} {resource_id} failed with status: {current_status}")

            LOGGER.debug(f"{resource_type.capitalize()} {resource_id} status: {current_status}, waiting...")
            time.sleep(delay)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                LOGGER.debug(f"{resource_type.capitalize()} {resource_id} not found yet, waiting...")
                time.sleep(delay)
            else:
                raise

    raise TimeoutError(f"{resource_type.capitalize()} {resource_id} did not reach status {target_statuses} after {max_attempts} attempts")
