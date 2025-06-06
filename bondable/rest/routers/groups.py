from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import logging
import uuid

from bondable.bond.providers.metadata import Group as GroupModel, GroupUser as GroupUserModel, User as UserModel
from bondable.rest.models.groups import Group, GroupCreate, GroupUpdate, GroupWithMembers, GroupMember
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/groups", tags=["Groups"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[Group])
async def get_user_groups(
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get all groups where the user is a member or owner."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        groups = db_session.query(GroupModel).join(
            GroupUserModel, GroupModel.id == GroupUserModel.group_id
        ).filter(GroupUserModel.user_id == current_user.user_id).all()
        
        owned_groups = db_session.query(GroupModel).filter(
            GroupModel.owner_user_id == current_user.user_id
        ).all()
        
        all_groups = {g.id: g for g in groups + owned_groups}.values()
        
        return [Group.from_orm(group) for group in all_groups]
    finally:
        db_session.close()


@router.get("/users", response_model=List[GroupMember])
async def get_all_users(
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get all users for group member selection."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        users = db_session.query(UserModel).all()
        return [
            GroupMember(user_id=user.id, email=user.email, name=user.name)
            for user in users
        ]
    finally:
        db_session.close()


@router.post("", response_model=Group, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Create a new group."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        new_group = GroupModel(
            id=str(uuid.uuid4()),
            name=group_data.name,
            description=group_data.description,
            owner_user_id=current_user.user_id
        )
        db_session.add(new_group)
        
        group_user = GroupUserModel(
            group_id=new_group.id,
            user_id=current_user.user_id
        )
        db_session.add(group_user)
        
        db_session.commit()
        db_session.refresh(new_group)
        
        return Group.from_orm(new_group)
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create group"
        )
    finally:
        db_session.close()


@router.get("/{group_id}", response_model=GroupWithMembers)
async def get_group(
    group_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Get group details with members."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = db_session.query(GroupUserModel).filter(
            GroupUserModel.group_id == group_id,
            GroupUserModel.user_id == current_user.user_id
        ).first() is not None
        
        if not is_member and group.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this group is forbidden"
            )
        
        members = db_session.query(UserModel).join(
            GroupUserModel, UserModel.id == GroupUserModel.user_id
        ).filter(GroupUserModel.group_id == group_id).all()
        
        group_data = Group.from_orm(group)
        member_data = [
            GroupMember(user_id=m.id, email=m.email, name=m.name) 
            for m in members
        ]
        
        return GroupWithMembers(**group_data.dict(), members=member_data)
    finally:
        db_session.close()


@router.put("/{group_id}", response_model=Group)
async def update_group(
    group_id: str,
    group_data: GroupUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Update group details (owner only)."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        if group.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group owner can update group"
            )
        
        if group_data.name is not None:
            group.name = group_data.name
        if group_data.description is not None:
            group.description = group_data.description
        
        db_session.commit()
        db_session.refresh(group)
        
        return Group.from_orm(group)
    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update group"
        )
    finally:
        db_session.close()


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Delete group (owner only)."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        if group.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group owner can delete group"
            )
        
        db_session.query(GroupUserModel).filter(GroupUserModel.group_id == group_id).delete()
        db_session.delete(group)
        db_session.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete group"
        )
    finally:
        db_session.close()


@router.post("/{group_id}/members/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: str,
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Add user to group (owner only)."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        if group.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group owner can add members"
            )
        
        user = db_session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        existing = db_session.query(GroupUserModel).filter(
            GroupUserModel.group_id == group_id,
            GroupUserModel.user_id == user_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this group"
            )
        
        group_user = GroupUserModel(group_id=group_id, user_id=user_id)
        db_session.add(group_user)
        db_session.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error adding group member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not add group member"
        )
    finally:
        db_session.close()


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: str,
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Remove user from group (owner only)."""
    db_session = bond_provider.metadata.get_db_session()
    try:
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        if group.owner_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group owner can remove members"
            )
        
        group_user = db_session.query(GroupUserModel).filter(
            GroupUserModel.group_id == group_id,
            GroupUserModel.user_id == user_id
        ).first()
        
        if not group_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this group"
            )
        
        db_session.delete(group_user)
        db_session.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error removing group member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not remove group member"
        )
    finally:
        db_session.close()