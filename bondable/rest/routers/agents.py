import os
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.agents import (
    AgentRef, AgentCreateRequest, AgentUpdateRequest, AgentResponse,
    AgentDetailResponse, ToolResourcesResponse, ToolResourceFilesList
)
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/agents", tags=["Agent"])
logger = logging.getLogger(__name__)


def _process_tool_resources(request_data, provider: Provider, user_id: str) -> dict:
    """Process tool resources for agent creation/update."""
    tool_resources_payload = {}
    
    if not request_data.tool_resources:
        return tool_resources_payload
    
    # Handle code interpreter files
    if (request_data.tool_resources.code_interpreter and 
        request_data.tool_resources.code_interpreter.file_ids):
        tool_resources_payload["code_interpreter"] = {
            "file_ids": request_data.tool_resources.code_interpreter.file_ids
        }
    
    # Handle file search files
    if (request_data.tool_resources.file_search and 
        request_data.tool_resources.file_search.file_ids):
        fs_file_ids = request_data.tool_resources.file_search.file_ids
        file_tuples_for_fs = []
        
        if fs_file_ids:
            file_path_dicts = provider.files.get_file_paths(file_ids=fs_file_ids)
            for fpd in file_path_dicts:
                if fpd and fpd.get('file_path'):
                    file_tuples_for_fs.append((fpd['file_path'], None))
                else:
                    logger.warning(f"File ID {fpd.get('file_id', 'N/A')} has no associated path. Skipping.")
        
        tool_resources_payload["file_search"] = {"files": file_tuples_for_fs}
    
    return tool_resources_payload


@router.get("", response_model=List[AgentRef])
async def get_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Get list of agents for the authenticated user."""
    try:
        agent_instances = provider.agents.list_agents(user_id=current_user.email)
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
        logger.error(f"Error fetching agents for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch agents.")


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request_data: AgentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Create a new agent."""
    logger.info(f"Create agent request for user {current_user.email} - MCP tools: {request_data.mcp_tools}, MCP resources: {request_data.mcp_resources}")
    try:
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.email)
        
        agent_def = AgentDefinition(
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            id=None,
            user_id=current_user.email,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or []
        )
        
        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.email)
        
        logger.info(f"Created agent '{agent_instance.get_name()}' with ID '{agent_instance.get_agent_id()}' for user {current_user.email}.")
        return AgentResponse(agent_id=agent_instance.get_agent_id(), name=agent_instance.get_name())
        
    except Exception as e:
        logger.error(f"Error creating agent '{request_data.name}' for user {current_user.email}: {e}", exc_info=True)
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
    logger.info(f"Update agent request for agent {agent_id}, user {current_user.email} - MCP tools: {request_data.mcp_tools}, MCP resources: {request_data.mcp_resources}")
    try:
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.email)
        
        agent_def = AgentDefinition(
            id=agent_id,
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            user_id=current_user.email,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or []
        )
        
        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.email)
        
        logger.info(f"Updated agent '{agent_instance.get_name()}' with ID '{agent_instance.get_agent_id()}' for user {current_user.email}.")
        return AgentResponse(agent_id=agent_instance.get_agent_id(), name=agent_instance.get_name())
        
    except Exception as e:
        logger.error(f"Error updating agent ID '{agent_id}' for user {current_user.email}: {e}", exc_info=True)
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

        if not provider.agents.can_user_access_agent(user_id=current_user.email, agent_id=agent_id):
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
                all_fs_files_data = provider.vectorstores.get_vector_store_file_paths(vector_store_ids=fs_vector_store_ids)
                processed_file_ids = {
                    fs_fp_data['file_id'] for fs_fp_data in all_fs_files_data
                    if fs_fp_data and fs_fp_data.get('file_id') and fs_fp_data.get('file_path')
                }
                response_tool_resources.file_search = ToolResourceFilesList(file_ids=list(processed_file_ids))

        return AgentDetailResponse(
            id=agent_instance.get_agent_id(),
            name=agent_def.name,
            description=agent_def.description,
            instructions=agent_def.instructions,
            model=agent_def.model,
            tools=agent_def.tools,
            tool_resources=response_tool_resources if (response_tool_resources.code_interpreter or response_tool_resources.file_search) else None,
            metadata=agent_def.metadata,
            mcp_tools=agent_def.mcp_tools if agent_def.mcp_tools else None,
            mcp_resources=agent_def.mcp_resources if agent_def.mcp_resources else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving agent details for ID '{agent_id}', user {current_user.email}: {e}", exc_info=True)
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

        if not provider.agents.can_user_access_agent(user_id=current_user.email, agent_id=agent_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # Delete the agent
        success = provider.agents.delete_agent(agent_id=agent_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete agent.")
        
        logger.info(f"Deleted agent with ID '{agent_id}' for user {current_user.email}.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent ID '{agent_id}' for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not delete agent: {str(e)}")