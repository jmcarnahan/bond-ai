from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from bondable.rest.models.groups import Group, GroupCreate, GroupUpdate, GroupWithMembers, GroupMember
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/groups", tags=["Groups"])
LOGGER = logging.getLogger(__name__)


@router.get("", response_model=List[Group])
async def get_user_groups(
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get all groups where the user is a member or owner."""
    try:
        groups = bond_provider.groups.get_user_groups(current_user.user_id)
        return [Group(**group) for group in groups]
    except Exception as e:
        LOGGER.error(f"Error fetching groups for user {current_user.user_id} ({current_user.email}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch groups"
        )


@router.get("/users", response_model=List[GroupMember])
async def get_all_users(
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get all users for group member selection."""
    try:
        users = bond_provider.groups.get_all_users()
        return [GroupMember(**user) for user in users]
    except Exception as e:
        LOGGER.error(f"Error fetching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch users"
        )


@router.post("", response_model=Group, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Create a new group."""
    try:
        group_id = bond_provider.groups.create_group(
            name=group_data.name,
            description=group_data.description,
            owner_user_id=current_user.user_id
        )

        # Get the created group to return
        group = bond_provider.groups.get_group(group_id, current_user.user_id)
        return Group(**group)
    except Exception as e:
        LOGGER.error(f"Error creating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create group"
        )


@router.get("/{group_id}", response_model=GroupWithMembers)
async def get_group(
    group_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get group details with members."""
    try:
        group = bond_provider.groups.get_group(group_id, current_user.user_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )

        members = bond_provider.groups.get_group_members(group_id, current_user.user_id)
        if members is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this group is forbidden"
            )

        member_data = [GroupMember(**member) for member in members]
        return GroupWithMembers(**group, members=member_data)
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error fetching group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch group"
        )


@router.put("/{group_id}", response_model=Group)
async def update_group(
    group_id: str,
    group_data: GroupUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Update group details (owner only)."""
    try:
        success = bond_provider.groups.update_group(
            group_id=group_id,
            user_id=current_user.user_id,
            name=group_data.name,
            description=group_data.description
        )

        if not success:
            # Check if group exists first
            group = bond_provider.groups.get_group(group_id, current_user.user_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only group owner can update group"
                )

        # Get updated group to return
        updated_group = bond_provider.groups.get_group(group_id, current_user.user_id)
        return Group(**updated_group)
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error updating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update group"
        )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Delete group (owner only)."""
    try:
        success = bond_provider.groups.delete_group(group_id, current_user.user_id)

        if not success:
            # Check if group exists first
            group = bond_provider.groups.get_group(group_id, current_user.user_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only group owner can delete group"
                )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete group"
        )


@router.post("/{group_id}/members/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: str,
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Add user to group (owner only)."""
    try:
        success = bond_provider.groups.manage_group_member(
            group_id=group_id,
            user_id=current_user.user_id,
            member_user_id=user_id,
            action="add"
        )

        if not success:
            # Check what failed - group exists? user exists? already member? permission?
            group = bond_provider.groups.get_group(group_id, current_user.user_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group not found"
                )

            # Check if user is owner
            if group["owner_user_id"] != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only group owner can add members"
                )

            # Could be user not found or already a member
            all_users = bond_provider.groups.get_all_users()
            user_exists = any(u["user_id"] == user_id for u in all_users)
            if not user_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User is already a member of this group"
                )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error adding group member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not add group member"
        )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: str,
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Remove user from group (owner only)."""
    try:
        success = bond_provider.groups.manage_group_member(
            group_id=group_id,
            user_id=current_user.user_id,
            member_user_id=user_id,
            action="remove"
        )

        if not success:
            # Check what failed
            group = bond_provider.groups.get_group(group_id, current_user.user_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group not found"
                )

            # Check if user is owner
            if group["owner_user_id"] != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only group owner can remove members"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User is not a member of this group"
                )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error removing group member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not remove group member"
        )
