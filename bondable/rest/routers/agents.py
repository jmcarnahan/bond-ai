import os
import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from bondable.bond.definition import AgentDefinition
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.metadata import Group as GroupModel, GroupUser as GroupUserModel, AgentGroup as AgentGroupModel
from bondable.rest.models.auth import User
from bondable.rest.models.agents import (
    AgentRef, AgentCreateRequest, AgentUpdateRequest, AgentResponse,
    AgentDetailResponse, ToolResourcesResponse, ToolResourceFilesList
)
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/agents", tags=["Agent"])
logger = logging.getLogger(__name__)


def _create_default_group_and_associate(agent_name: str, agent_id: str, user_id: str, provider: Provider) -> str:
    """Create a default group for the agent, associate the agent with it, and return the group ID."""
    db_session = provider.metadata.get_db_session()
    try:
        group_name = f"{agent_name} Default Group"
        
        new_group = GroupModel(
            id=str(uuid.uuid4()),
            name=group_name,
            description=None,  # No description as requested
            owner_user_id=user_id
        )
        db_session.add(new_group)
        
        # Add the owner as a group member
        group_user = GroupUserModel(
            group_id=new_group.id,
            user_id=user_id
        )
        db_session.add(group_user)
        
        # Associate the agent with the group
        agent_group = AgentGroupModel(
            agent_id=agent_id,
            group_id=new_group.id
        )
        db_session.add(agent_group)
        
        db_session.commit()
        db_session.refresh(new_group)
        
        logger.info(f"Created default group '{group_name}' with ID '{new_group.id}' and associated with agent '{agent_id}'")
        return new_group.id
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating default group and association for agent '{agent_name}': {e}")
        raise e
    finally:
        db_session.close()


def _associate_agent_with_group(agent_id: str, group_id: str, provider: Provider) -> None:
    """Associate an agent with a group."""
    db_session = provider.metadata.get_db_session()
    try:
        agent_group = AgentGroupModel(
            agent_id=agent_id,
            group_id=group_id
        )
        db_session.add(agent_group)
        db_session.commit()
        
        logger.info(f"Associated agent '{agent_id}' with group '{group_id}'")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error associating agent '{agent_id}' with group '{group_id}': {e}")
        raise e
    finally:
        db_session.close()


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
        logger.error(f"Error fetching agents for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch agents.")


@router.get("/available-groups", response_model=List[dict])
async def get_available_groups_for_agent(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider),
    agent_id: str = None  # Optional - for editing existing agents
):
    """Get groups available for agent association (groups user owns/belongs to, excluding those already associated)."""
    db_session = provider.metadata.get_db_session()
    try:
        # Get all groups where user is owner or member
        user_groups_query = db_session.query(GroupModel).outerjoin(
            GroupUserModel, GroupModel.id == GroupUserModel.group_id
        ).filter(
            (GroupModel.owner_user_id == current_user.user_id) |
            (GroupUserModel.user_id == current_user.user_id)
        ).distinct()
        
        # If editing existing agent, exclude groups already associated
        if agent_id:
            associated_group_ids = db_session.query(AgentGroupModel.group_id).filter(
                AgentGroupModel.agent_id == agent_id
            ).subquery()
            user_groups_query = user_groups_query.filter(
                ~GroupModel.id.in_(associated_group_ids)
            )
        
        available_groups = user_groups_query.all()
        
        return [
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "is_owner": group.owner_user_id == current_user.user_id
            }
            for group in available_groups
        ]
    except Exception as e:
        logger.error(f"Error fetching available groups for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch available groups.")
    finally:
        db_session.close()


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request_data: AgentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Create a new agent."""
    logger.info(f"Create agent request for user {current_user.email} - MCP tools: {request_data.mcp_tools}, MCP resources: {request_data.mcp_resources}")
    try:
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.user_id)
        
        agent_def = AgentDefinition(
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            id=None,
            user_id=current_user.user_id,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or []
        )
        
        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.user_id)
        
        # Create default group for the agent and associate them
        try:
            group_id = _create_default_group_and_associate(
                agent_name=request_data.name,
                agent_id=agent_instance.get_agent_id(),
                user_id=current_user.user_id,
                provider=provider
            )
            logger.info(f"Created and associated default group '{group_id}' for agent '{agent_instance.get_name()}'")
        except Exception as group_error:
            logger.error(f"Failed to create default group for agent '{request_data.name}': {group_error}")
            # Don't fail the agent creation if group creation fails, just log the error
        
        # Associate agent with additional selected groups
        if request_data.group_ids:
            try:
                for group_id in request_data.group_ids:
                    _associate_agent_with_group(
                        agent_id=agent_instance.get_agent_id(),
                        group_id=group_id,
                        provider=provider
                    )
                logger.info(f"Associated agent '{agent_instance.get_agent_id()}' with {len(request_data.group_ids)} additional groups")
            except Exception as group_error:
                logger.error(f"Failed to associate agent with additional groups: {group_error}")
                # Don't fail the agent creation if additional group associations fail
        
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
        tool_resources_payload = _process_tool_resources(request_data, provider, current_user.user_id)
        
        agent_def = AgentDefinition(
            id=agent_id,
            name=request_data.name,
            description=request_data.description or "",  # Ensure description is never None
            instructions=request_data.instructions or "",  # Ensure instructions is never None
            tools=request_data.tools,
            tool_resources=tool_resources_payload,
            metadata=request_data.metadata,
            model=request_data.model or provider.get_default_model(),
            user_id=current_user.user_id,
            mcp_tools=request_data.mcp_tools or [],
            mcp_resources=request_data.mcp_resources or []
        )
        
        agent_instance = provider.agents.create_or_update_agent(agent_def=agent_def, user_id=current_user.user_id)
        
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

        if not provider.agents.can_user_access_agent(user_id=current_user.user_id, agent_id=agent_id):
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