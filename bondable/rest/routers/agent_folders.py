from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from bondable.rest.models.agent_folders import (
    FolderRef, FolderCreateRequest, FolderUpdateRequest, FolderAssignRequest,
    AgentReorderRequest, FolderReorderRequest
)
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/agent-folders", tags=["Agent Folders"])
LOGGER = logging.getLogger(__name__)


@router.get("", response_model=List[FolderRef])
async def get_folders(
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Get all folders for the current user."""
    try:
        folders = bond_provider.agent_folders.get_user_folders(current_user.user_id)
        return [FolderRef(**f) for f in folders]
    except Exception as e:
        LOGGER.error(f"Error fetching folders for user {current_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch folders."
        )


@router.post("", response_model=FolderRef, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: FolderCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Create a new folder."""
    name = request.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder name cannot be empty."
        )
    if len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder name cannot exceed 100 characters."
        )
    try:
        folder = bond_provider.agent_folders.create_folder(name=name, user_id=current_user.user_id)
        return FolderRef(**folder)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        LOGGER.error(f"Error creating folder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create folder."
        )


# NOTE: /assign must be defined BEFORE /{folder_id} to avoid path parameter capture
@router.put("/assign", response_model=dict)
async def assign_agent_to_folder(
    request: FolderAssignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Assign an agent to a folder, or remove from folder (folder_id=null)."""
    try:
        bond_provider.agent_folders.assign_agent(
            agent_id=request.agent_id,
            user_id=current_user.user_id,
            folder_id=request.folder_id
        )
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found."
        )
    except Exception as e:
        LOGGER.error(f"Error assigning agent {request.agent_id} to folder {request.folder_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not assign agent to folder."
        )


@router.put("/reorder-agents", response_model=dict)
async def reorder_agents(
    request: AgentReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Bulk reorder agents within a context (main screen or folder)."""
    try:
        if request.folder_id is not None:
            # Verify folder belongs to user
            folders = bond_provider.agent_folders.get_user_folders(current_user.user_id)
            if not any(f['id'] == request.folder_id for f in folders):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Folder not found."
                )
        bond_provider.agent_folders.reorder_agents(
            user_id=current_user.user_id,
            agent_ids=request.agent_ids
        )
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error reordering agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reorder agents."
        )


@router.put("/reorder-folders", response_model=dict)
async def reorder_folders(
    request: FolderReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Bulk reorder folders on the main screen."""
    try:
        bond_provider.agent_folders.reorder_folders(
            user_id=current_user.user_id,
            folder_ids=request.folder_ids
        )
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found."
        )
    except Exception as e:
        LOGGER.error(f"Error reordering folders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reorder folders."
        )


@router.put("/{folder_id}", response_model=FolderRef)
async def update_folder(
    folder_id: str,
    request: FolderUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Update a folder (rename or reorder)."""
    name = request.name.strip() if request.name is not None else None
    if name is not None and not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder name cannot be empty."
        )
    if name is not None and len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder name cannot exceed 100 characters."
        )
    try:
        folder = bond_provider.agent_folders.update_folder(
            folder_id=folder_id,
            user_id=current_user.user_id,
            name=name,
            sort_order=request.sort_order
        )
        return FolderRef(**folder)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found."
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        LOGGER.error(f"Error updating folder {folder_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update folder."
        )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider)
):
    """Delete a folder. Agents inside return to the main screen."""
    try:
        bond_provider.agent_folders.delete_folder(folder_id=folder_id, user_id=current_user.user_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found."
        )
    except Exception as e:
        LOGGER.error(f"Error deleting folder {folder_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete folder."
        )
