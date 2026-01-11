import os
import uuid
from typing import Annotated, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import logging
from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.agents import (
    AgentRef, AgentCreateRequest, AgentUpdateRequest, AgentResponse,
    AgentDetailResponse, ToolResourcesResponse, ToolResourceFilesList, ModelInfo
)
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/agents", tags=["Agent"])
LOGGER = logging.getLogger(__name__)




def _process_tool_resources(request_data, provider: Provider, user_id: str) -> dict:
    """Process tool resources for agent creation/update."""
    tool_resources_payload = {}

    if not request_data.tool_resources:
        return tool_resources_payload

    # Handle code interpreter files
    # Note: We check for `is not None` to distinguish between:
    # - file_ids=None (not provided, preserve existing)
    # - file_ids=[] (explicitly empty, clear all files)
    if (request_data.tool_resources.code_interpreter and
        request_data.tool_resources.code_interpreter.file_ids is not None):
        tool_resources_payload["code_interpreter"] = {
            "file_ids": request_data.tool_resources.code_interpreter.file_ids
        }

    # Handle file search files
    # Note: We check for `is not None` to distinguish between:
    # - file_ids=None (not provided, preserve existing)
    # - file_ids=[] (explicitly empty, clear all files)
    if (request_data.tool_resources.file_search and
        request_data.tool_resources.file_search.file_ids is not None):
        tool_resources_payload["file_search"] = {
            "file_ids": request_data.tool_resources.file_search.file_ids
        }

        # fs_file_ids = request_data.tool_resources.file_search.file_ids
        # file_tuples_for_fs = []

        # # For already uploaded files, pass tuples of (file_id, None)
        # for file_id in fs_file_ids:
        #     file_tuples_for_fs.append((file_id, None))

        # tool_resources_payload["file_search"] = {"files": file_tuples_for_fs}

    return tool_resources_payload


@router.get("", response_model=List[AgentRef])
async def get_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Get list of agents for the authenticated user."""
    try:
        agent_instances = provider.agents.list_agents(user_id=current_user.user_id)
        return [
            AgentRef(
                id=agent.get_agent_id(),
                name=agent.get_name(),
                description=agent.get_description(),
                metadata=agent.get_metadata(),
            )
            for agent in agent_instances
        ]
    except Exception as e:
        LOGGER.error(f"Error fetching agents for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch agents.")


@router.get("/models", response_model=List[ModelInfo])
async def get_available_models(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Get list of available models that can be used by agents."""
    try:
        models = provider.agents.get_available_models()
        return [ModelInfo(**model) for model in models]
    except Exception as e:
        LOGGER.error(f"Error fetching available models: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch available models.")


@router.get("/default", response_model=AgentResponse)
async def get_default_agent(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Get the default agent, creating one if it doesn't exist."""
    try:
        default_agent = provider.agents.get_default_agent()
        if not default_agent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get or create default agent"
            )

        return AgentResponse(
            agent_id=default_agent.get_agent_id(),
            name=default_agent.get_name()
        )
    except Exception as e:
        LOGGER.error(f"Error getting default agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting default agent: {str(e)}"
        )


@router.get("/available-groups", response_model=List[dict])
async def get_available_groups_for_agent(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider),
    agent_id: str = None  # Optional - for editing existing agents
):
    """Get groups available for agent association (groups user owns/belongs to, excluding those already associated)."""
    try:
        available_groups = provider.groups.get_available_groups_for_agent(
            user_id=current_user.user_id,
            agent_id=agent_id
        )
        return available_groups
    except Exception as e:
        LOGGER.error(f"Error fetching available groups for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch available groups.")


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request_data: AgentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Create a new agent."""
    LOGGER.info(f"Create agent request for user {current_user.user_id} ({current_user.email}) - MCP tools: {request_data.mcp_tools}, MCP resources: {request_data.mcp_resources}")
    try:
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.user_id)
        LOGGER.debug(f"CREATE_AGENT: tool_resources_payload after processing: {tool_resources_payload}")

        # Log complete request data for debugging
        LOGGER.debug("=== AGENT CREATE REQUEST DEBUG ===")
        LOGGER.debug(f"User: {current_user.user_id} ({current_user.email})")
        LOGGER.debug(f"Request data:")
        LOGGER.debug(f"  - name: {request_data.name}")
        LOGGER.debug(f"  - description: {request_data.description}")
        LOGGER.debug(f"  - instructions: {request_data.instructions[:200]}..." if request_data.instructions and len(request_data.instructions) > 200 else f"  - instructions: {request_data.instructions}")
        LOGGER.debug(f"  - model: {request_data.model}")
        LOGGER.debug(f"  - tools: {request_data.tools}")
        LOGGER.debug(f"  - mcp_tools: {request_data.mcp_tools}")
        LOGGER.debug(f"  - mcp_resources: {request_data.mcp_resources}")
        LOGGER.debug(f"  - metadata: {request_data.metadata}")
        LOGGER.debug("=================================")

        agent_def = AgentDefinition(
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            introduction=request_data.introduction or "",  # New field
            reminder=request_data.reminder or "",  # New field
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            id=None,
            user_id=current_user.user_id,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or [],
            file_storage=request_data.file_storage or 'direct'
        )

        # Log critical values for KB upload debugging
        LOGGER.debug(f"CREATE_AGENT: AgentDefinition file_storage='{agent_def.file_storage}', tool_resources={agent_def.tool_resources}")

        # Log the created agent definition
        LOGGER.debug("=== AGENT DEFINITION CREATED ===")
        LOGGER.debug(f"AgentDefinition object:")
        LOGGER.debug(f"  - name: {agent_def.name}")
        LOGGER.debug(f"  - model: {agent_def.model}")
        LOGGER.debug(f"  - mcp_tools: {agent_def.mcp_tools}")
        LOGGER.debug(f"  - mcp_resources: {agent_def.mcp_resources}")
        LOGGER.debug(f"  - tools: {agent_def.tools}")
        LOGGER.debug("================================")

        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.user_id)

        # Create default group for the agent and associate them
        try:
            group_id = provider.groups.create_default_group_and_associate(
                agent_name=request_data.name,
                agent_id=agent_instance.get_agent_id(),
                user_id=current_user.user_id
            )
            LOGGER.info(f"Created and associated default group '{group_id}' for agent '{agent_instance.get_name()}'")
        except Exception as group_error:
            LOGGER.error(f"Failed to create default group for agent '{request_data.name}': {group_error}")
            # Don't fail the agent creation if group creation fails, just log the error

        # Associate agent with additional selected groups
        if request_data.group_ids:
            try:
                for group_id in request_data.group_ids:
                    provider.groups.associate_agent_with_group(
                        agent_id=agent_instance.get_agent_id(),
                        group_id=group_id
                    )
                LOGGER.info(f"Associated agent '{agent_instance.get_agent_id()}' with {len(request_data.group_ids)} additional groups")
            except Exception as group_error:
                LOGGER.error(f"Failed to associate agent with additional groups: {group_error}")
                # Don't fail the agent creation if additional group associations fail

        LOGGER.info(f"Created agent '{agent_instance.get_name()}' with ID '{agent_instance.get_agent_id()}' for user {current_user.user_id} ({current_user.email}).")
        return AgentResponse(agent_id=agent_instance.get_agent_id(), name=agent_instance.get_name())

    except Exception as e:
        LOGGER.error(f"Error creating agent '{request_data.name}' for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not create agent: {str(e)}")


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request_data: AgentUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Update an existing agent."""
    LOGGER.info(f"Update agent request for agent {agent_id}, user {current_user.user_id} ({current_user.email}) - MCP tools: {request_data.mcp_tools}, MCP resources: {request_data.mcp_resources}")
    LOGGER.info(f"Update request - introduction: '{request_data.introduction[:50] if request_data.introduction else 'None'}'...")
    LOGGER.info(f"Update request - reminder: '{request_data.reminder[:50] if request_data.reminder else 'None'}'...")

    # Log tool_resources for debugging
    LOGGER.debug(f"Update agent {agent_id} - tool_resources: {request_data.tool_resources}")

    try:
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.user_id)
        LOGGER.debug(f"Processed tool_resources_payload: {tool_resources_payload}")

        # Log complete request data for debugging
        LOGGER.debug("=== AGENT UPDATE REQUEST DEBUG ===")
        LOGGER.debug(f"Agent ID: {agent_id}")
        LOGGER.debug(f"User: {current_user.user_id} ({current_user.email})")
        LOGGER.debug(f"Request data:")
        LOGGER.debug(f"  - name: {request_data.name}")
        LOGGER.debug(f"  - description: {request_data.description}")
        LOGGER.debug(f"  - instructions: {request_data.instructions[:200]}..." if request_data.instructions and len(request_data.instructions) > 200 else f"  - instructions: {request_data.instructions}")
        LOGGER.debug(f"  - model: {request_data.model}")
        LOGGER.debug(f"  - tools: {request_data.tools}")
        LOGGER.debug(f"  - mcp_tools: {request_data.mcp_tools}")
        LOGGER.debug(f"  - mcp_resources: {request_data.mcp_resources}")
        LOGGER.debug(f"  - metadata: {request_data.metadata}")
        LOGGER.debug("=================================")

        # Get existing agent to preserve file_storage if not provided
        existing_file_storage = 'direct'
        if request_data.file_storage is None:
            existing_agent = provider.agents.get_agent(agent_id=agent_id)
            if existing_agent:
                existing_def = existing_agent.get_agent_definition()
                existing_file_storage = getattr(existing_def, 'file_storage', 'direct')

        agent_def = AgentDefinition(
            id=agent_id,
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            introduction=request_data.introduction or "",  # New field
            reminder=request_data.reminder or "",  # New field
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            user_id=current_user.user_id,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or [],
            file_storage=request_data.file_storage if request_data.file_storage else existing_file_storage
        )

        # Log the created agent definition
        LOGGER.debug("=== AGENT DEFINITION UPDATED ===")
        LOGGER.debug(f"AgentDefinition object:")
        LOGGER.debug(f"  - id: {agent_def.id}")
        LOGGER.debug(f"  - name: {agent_def.name}")
        LOGGER.debug(f"  - model: {agent_def.model}")
        LOGGER.debug(f"  - mcp_tools: {agent_def.mcp_tools}")
        LOGGER.debug(f"  - mcp_resources: {agent_def.mcp_resources}")
        LOGGER.debug(f"  - tools: {agent_def.tools}")
        LOGGER.debug("================================")

        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.user_id)

        LOGGER.info(f"Updated agent '{agent_instance.get_name()}' with ID '{agent_instance.get_agent_id()}' for user {current_user.user_id} ({current_user.email}).")
        return AgentResponse(agent_id=agent_instance.get_agent_id(), name=agent_instance.get_name())

    except Exception as e:
        LOGGER.error(f"Error updating agent ID '{agent_id}' for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not update agent: {str(e)}")


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_details(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Get detailed information for a specific agent."""
    try:
        agent_instance = provider.agents.get_agent(agent_id=agent_id)
        if not agent_instance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # Check if this is a default agent (accessible to all users)
        is_default_agent = False
        try:
            # Check if this agent is the default agent by comparing with the default agent ID
            default_agent = provider.agents.get_default_agent()
            is_default_agent = default_agent and default_agent.get_agent_id() == agent_id
        except Exception as e:
            LOGGER.error(f"Error checking if agent {agent_id} is default: {e}")

        # Validate user access to agent (skip validation for default agents)
        if not is_default_agent and not provider.agents.can_user_access_agent(user_id=current_user.user_id, agent_id=agent_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        agent_def = agent_instance.get_agent_definition()
        response_tool_resources = ToolResourcesResponse()

        # Process code_interpreter files
        if agent_def.tool_resources and "code_interpreter" in agent_def.tool_resources:
            ci_file_ids = agent_def.tool_resources["code_interpreter"].get("file_ids", [])
            if ci_file_ids:
                response_tool_resources.code_interpreter = ToolResourceFilesList(file_ids=ci_file_ids)

        # Process file_search files (vector stores)
        if agent_def.tool_resources and "file_search" in agent_def.tool_resources:
            fs_vector_store_ids = agent_def.tool_resources["file_search"].get("vector_store_ids", [])
            if fs_vector_store_ids:
                all_fs_files_data = provider.vectorstores.get_vector_store_file_details(vector_store_ids=fs_vector_store_ids)
                processed_file_ids = set()
                for vector_store_id, file_details_list in all_fs_files_data.items():
                    for file_details in file_details_list:
                        if file_details and file_details.file_id:
                            processed_file_ids.add(file_details.file_id)
                response_tool_resources.file_search = ToolResourceFilesList(file_ids=list(processed_file_ids))

        LOGGER.debug(f"Returning agent details - introduction: '{agent_def.introduction[:50] if agent_def.introduction else 'None'}'...")
        LOGGER.debug(f"Returning agent details - reminder: '{agent_def.reminder[:50] if agent_def.reminder else 'None'}'...")

        return AgentDetailResponse(
            id=agent_instance.get_agent_id(),
            name=agent_def.name,
            description=agent_def.description,
            instructions=agent_def.instructions,
            introduction=agent_def.introduction,
            reminder=agent_def.reminder,
            model=agent_def.model,
            tools=agent_def.tools,
            tool_resources=response_tool_resources if (response_tool_resources.code_interpreter or response_tool_resources.file_search) else None,
            metadata=agent_def.metadata,
            mcp_tools=agent_def.mcp_tools if agent_def.mcp_tools else None,
            mcp_resources=agent_def.mcp_resources if agent_def.mcp_resources else None,
            file_storage=getattr(agent_def, 'file_storage', 'direct')
        )

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error retrieving agent details for ID '{agent_id}', user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not retrieve agent details: {str(e)}")


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Delete an agent."""
    try:
        # Check if agent exists and user has access
        agent_instance = provider.agents.get_agent(agent_id=agent_id)
        if not agent_instance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        if not provider.agents.can_user_access_agent(user_id=current_user.user_id, agent_id=agent_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # Delete the agent
        success = provider.agents.delete_agent(agent_id=agent_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete agent.")

        LOGGER.info(f"Deleted agent with ID '{agent_id}' for user {current_user.user_id} ({current_user.email}).")

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting agent ID '{agent_id}' for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not delete agent: {str(e)}")
