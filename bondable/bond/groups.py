from bondable.bond.providers.metadata import Metadata, Group as GroupModel, GroupUser as GroupUserModel, AgentGroup as AgentGroupModel, User as UserModel
from typing import List, Dict, Optional
import logging
import uuid

LOGGER = logging.getLogger(__name__)


class Groups:
    
    def __init__(self, metadata: Metadata):
        self.metadata = metadata

    def _get_group_dict(self, group: GroupModel) -> Dict:
        """Convert GroupModel to dictionary."""
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "owner_user_id": group.owner_user_id,
            "created_at": group.created_at,
            "updated_at": group.updated_at
        }

    def _get_user_dict(self, user: UserModel) -> Dict:
        """Convert UserModel to dictionary."""
        return {
            "user_id": user.id,
            "email": user.email,
            "name": user.name
        }

    def _can_user_access_group(self, db_session, group_id: str, user_id: str) -> bool:
        """Check if user can access group (is member or owner)."""
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if not group:
            return False
        
        if group.owner_user_id == user_id:
            return True
            
        is_member = db_session.query(GroupUserModel).filter(
            GroupUserModel.group_id == group_id,
            GroupUserModel.user_id == user_id
        ).first() is not None
        
        return is_member

    def _can_user_modify_group(self, db_session, group_id: str, user_id: str) -> bool:
        """Check if user can modify group (is owner)."""
        group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
        return group and group.owner_user_id == user_id

    def create_group(self, name: str, description: Optional[str], owner_user_id: str) -> str:
        """Create a new group and return the group ID."""
        with self.metadata.get_db_session() as db_session:
            try:
                group_id = f"grp_{uuid.uuid4()}"
                new_group = GroupModel(
                    id=group_id,
                    name=name,
                    description=description,
                    owner_user_id=owner_user_id
                )
                db_session.add(new_group)
                
                # Add the owner as a group member
                group_user = GroupUserModel(
                    group_id=group_id,
                    user_id=owner_user_id
                )
                db_session.add(group_user)
                
                db_session.commit()
                LOGGER.info(f"Created group '{name}' with ID '{group_id}' for user '{owner_user_id}'")
                return group_id
            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error creating group '{name}': {e}")
                raise e

    def get_user_groups(self, user_id: str) -> List[Dict]:
        """Get all groups where the user is a member or owner."""
        with self.metadata.get_db_session() as db_session:
            # Single query to get all groups user has access to
            groups = db_session.query(GroupModel).outerjoin(
                GroupUserModel, GroupModel.id == GroupUserModel.group_id
            ).filter(
                (GroupModel.owner_user_id == user_id) |
                (GroupUserModel.user_id == user_id)
            ).distinct().all()
            
            return [self._get_group_dict(group) for group in groups]

    def get_group(self, group_id: str, user_id: str) -> Optional[Dict]:
        """Get group details if user has access."""
        with self.metadata.get_db_session() as db_session:
            if not self._can_user_access_group(db_session, group_id, user_id):
                return None
                
            group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
            return self._get_group_dict(group) if group else None

    def get_group_members(self, group_id: str, user_id: str) -> Optional[List[Dict]]:
        """Get group members if user has access."""
        with self.metadata.get_db_session() as db_session:
            if not self._can_user_access_group(db_session, group_id, user_id):
                return None
                
            members = db_session.query(UserModel).join(
                GroupUserModel, UserModel.id == GroupUserModel.user_id
            ).filter(GroupUserModel.group_id == group_id).all()
            
            return [self._get_user_dict(member) for member in members]

    def update_group(self, group_id: str, user_id: str, name: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Update group details (owner only)."""
        with self.metadata.get_db_session() as db_session:
            try:
                if not self._can_user_modify_group(db_session, group_id, user_id):
                    return False
                
                group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
                if name is not None:
                    group.name = name
                if description is not None:
                    group.description = description
                
                db_session.commit()
                LOGGER.info(f"Updated group '{group_id}' by user '{user_id}'")
                return True
            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error updating group '{group_id}': {e}")
                raise e

    def delete_group(self, group_id: str, user_id: str) -> bool:
        """Delete group (owner only)."""
        with self.metadata.get_db_session() as db_session:
            try:
                if not self._can_user_modify_group(db_session, group_id, user_id):
                    return False
                
                group = db_session.query(GroupModel).filter(GroupModel.id == group_id).first()
                
                # Delete all group memberships and agent associations
                db_session.query(GroupUserModel).filter(GroupUserModel.group_id == group_id).delete()
                db_session.query(AgentGroupModel).filter(AgentGroupModel.group_id == group_id).delete()
                db_session.delete(group)
                db_session.commit()
                
                LOGGER.info(f"Deleted group '{group_id}' by user '{user_id}'")
                return True
            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error deleting group '{group_id}': {e}")
                raise e

    def manage_group_member(self, group_id: str, user_id: str, member_user_id: str, action: str) -> bool:
        """Add or remove user from group (owner only)."""
        with self.metadata.get_db_session() as db_session:
            try:
                if not self._can_user_modify_group(db_session, group_id, user_id):
                    return False
                
                if action == "add":
                    # Check if user exists and not already a member
                    user_exists = db_session.query(UserModel).filter(UserModel.id == member_user_id).first()
                    if not user_exists:
                        return False
                    
                    existing = db_session.query(GroupUserModel).filter(
                        GroupUserModel.group_id == group_id,
                        GroupUserModel.user_id == member_user_id
                    ).first()
                    
                    if existing:
                        return False  # Already a member
                    
                    group_user = GroupUserModel(group_id=group_id, user_id=member_user_id)
                    db_session.add(group_user)
                    
                elif action == "remove":
                    group_user = db_session.query(GroupUserModel).filter(
                        GroupUserModel.group_id == group_id,
                        GroupUserModel.user_id == member_user_id
                    ).first()
                    
                    if not group_user:
                        return False
                    
                    db_session.delete(group_user)
                else:
                    return False
                
                db_session.commit()
                LOGGER.info(f"{action.capitalize()}ed user '{member_user_id}' {'to' if action == 'add' else 'from'} group '{group_id}' by user '{user_id}'")
                return True
            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error {action}ing user '{member_user_id}' {'to' if action == 'add' else 'from'} group '{group_id}': {e}")
                raise e

    def get_available_groups_for_agent(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict]:
        """Get groups available for agent association."""
        with self.metadata.get_db_session() as db_session:
            # Get all groups where user is owner or member
            user_groups_query = db_session.query(GroupModel).outerjoin(
                GroupUserModel, GroupModel.id == GroupUserModel.group_id
            ).filter(
                (GroupModel.owner_user_id == user_id) |
                (GroupUserModel.user_id == user_id)
            ).distinct()
            
            # Exclude groups already associated with the agent
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
                    "is_owner": group.owner_user_id == user_id
                }
                for group in available_groups
            ]

    def create_default_group_and_associate(self, agent_name: str, agent_id: str, user_id: str) -> str:
        """Create a default group for the agent and associate it."""
        group_id = self.create_group(f"{agent_name} Default Group", None, user_id)
        self.associate_agent_with_group(agent_id, group_id)
        return group_id

    def associate_agent_with_group(self, agent_id: str, group_id: str) -> bool:
        """Associate an agent with a group."""
        with self.metadata.get_db_session() as db_session:
            try:
                # Check if association already exists
                existing = db_session.query(AgentGroupModel).filter(
                    AgentGroupModel.agent_id == agent_id,
                    AgentGroupModel.group_id == group_id
                ).first()
                
                if existing:
                    return True
                
                agent_group = AgentGroupModel(agent_id=agent_id, group_id=group_id)
                db_session.add(agent_group)
                db_session.commit()
                
                LOGGER.info(f"Associated agent '{agent_id}' with group '{group_id}'")
                return True
            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error associating agent '{agent_id}' with group '{group_id}': {e}")
                raise e

    def get_all_users(self) -> List[Dict]:
        """Get all users for group member selection."""
        with self.metadata.get_db_session() as db_session:
            users = db_session.query(UserModel).all()
            return [self._get_user_dict(user) for user in users]