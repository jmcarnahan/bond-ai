from bondable.bond.providers.metadata import Metadata, AgentFolder, AgentFolderAssignment, UserAgentSortOrder
from typing import List, Dict, Optional
from sqlalchemy import func
import logging
import uuid

LOGGER = logging.getLogger(__name__)


class AgentFolders:

    def __init__(self, metadata: Metadata):
        self.metadata = metadata

    def get_user_folders(self, user_id: str) -> List[Dict]:
        """Get all folders for a user with agent counts."""
        with self.metadata.get_db_session() as session:
            try:
                folders = session.query(
                    AgentFolder,
                    func.count(AgentFolderAssignment.agent_id).label('agent_count')
                ).outerjoin(
                    AgentFolderAssignment,
                    AgentFolder.id == AgentFolderAssignment.folder_id
                ).filter(
                    AgentFolder.user_id == user_id
                ).group_by(
                    AgentFolder.id
                ).order_by(
                    AgentFolder.sort_order, AgentFolder.name
                ).all()

                return [
                    {
                        "id": folder.id,
                        "name": folder.name,
                        "agent_count": count,
                        "sort_order": folder.sort_order,
                    }
                    for folder, count in folders
                ]
            except Exception as e:
                LOGGER.error(f"Error getting folders for user {user_id}: {e}")
                raise

    def create_folder(self, name: str, user_id: str) -> Dict:
        """Create a new folder. Raises ValueError on duplicate name."""
        with self.metadata.get_db_session() as session:
            try:
                existing = session.query(AgentFolder).filter(
                    AgentFolder.name == name,
                    AgentFolder.user_id == user_id
                ).first()
                if existing:
                    raise ValueError(f"Folder with name '{name}' already exists")

                folder_id = f"fld_{uuid.uuid4()}"
                max_order = session.query(func.max(AgentFolder.sort_order)).filter(
                    AgentFolder.user_id == user_id
                ).scalar() or 0

                folder = AgentFolder(
                    id=folder_id,
                    name=name,
                    user_id=user_id,
                    sort_order=max_order + 1,
                )
                session.add(folder)
                session.commit()
                return {
                    "id": folder_id,
                    "name": name,
                    "agent_count": 0,
                    "sort_order": max_order + 1,
                }
            except ValueError:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error creating folder: {e}")
                raise

    def update_folder(self, folder_id: str, user_id: str, name: Optional[str] = None, sort_order: Optional[int] = None) -> Dict:
        """Update folder name or sort_order. Returns updated folder dict. Raises KeyError if not found."""
        with self.metadata.get_db_session() as session:
            try:
                folder = session.query(AgentFolder).filter(
                    AgentFolder.id == folder_id,
                    AgentFolder.user_id == user_id
                ).first()
                if not folder:
                    raise KeyError(f"Folder not found: {folder_id}")

                if name is not None:
                    # Check for duplicate name
                    existing = session.query(AgentFolder).filter(
                        AgentFolder.name == name,
                        AgentFolder.user_id == user_id,
                        AgentFolder.id != folder_id
                    ).first()
                    if existing:
                        raise ValueError(f"Folder with name '{name}' already exists")
                    folder.name = name

                if sort_order is not None:
                    folder.sort_order = sort_order

                session.commit()

                count = session.query(func.count(AgentFolderAssignment.agent_id)).filter(
                    AgentFolderAssignment.folder_id == folder_id,
                    AgentFolderAssignment.user_id == user_id
                ).scalar() or 0

                return {
                    "id": folder.id,
                    "name": folder.name,
                    "agent_count": count,
                    "sort_order": folder.sort_order,
                }
            except (KeyError, ValueError):
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error updating folder {folder_id}: {e}")
                raise

    def delete_folder(self, folder_id: str, user_id: str) -> None:
        """Delete a folder. Assignments are cascade-deleted. Raises KeyError if not found."""
        with self.metadata.get_db_session() as session:
            try:
                folder = session.query(AgentFolder).filter(
                    AgentFolder.id == folder_id,
                    AgentFolder.user_id == user_id
                ).first()
                if not folder:
                    raise KeyError(f"Folder not found: {folder_id}")

                # Manually delete assignments first (SQLite may not support CASCADE)
                session.query(AgentFolderAssignment).filter(
                    AgentFolderAssignment.folder_id == folder_id,
                    AgentFolderAssignment.user_id == user_id
                ).delete()

                session.delete(folder)
                session.commit()
            except KeyError:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error deleting folder {folder_id}: {e}")
                raise

    def assign_agent(self, agent_id: str, user_id: str, folder_id: Optional[str]) -> None:
        """Assign an agent to a folder, or remove from folder if folder_id is None.
        Also resets the agent's sort_order so it appears at the end of the new context."""
        with self.metadata.get_db_session() as session:
            try:
                # Reset sort order when moving between contexts (main screen <-> folder)
                # so the agent appears at the end of its new context
                session.query(UserAgentSortOrder).filter(
                    UserAgentSortOrder.agent_id == agent_id,
                    UserAgentSortOrder.user_id == user_id
                ).delete()

                if folder_id is None:
                    # Remove assignment (agent returns to main screen)
                    session.query(AgentFolderAssignment).filter(
                        AgentFolderAssignment.agent_id == agent_id,
                        AgentFolderAssignment.user_id == user_id
                    ).delete()
                    session.commit()
                    return

                # Verify folder belongs to user
                folder = session.query(AgentFolder).filter(
                    AgentFolder.id == folder_id,
                    AgentFolder.user_id == user_id
                ).first()
                if not folder:
                    raise KeyError(f"Folder not found: {folder_id}")

                # Upsert: check if assignment exists
                existing = session.query(AgentFolderAssignment).filter(
                    AgentFolderAssignment.agent_id == agent_id,
                    AgentFolderAssignment.user_id == user_id
                ).first()

                if existing:
                    existing.folder_id = folder_id
                else:
                    assignment = AgentFolderAssignment(
                        agent_id=agent_id,
                        user_id=user_id,
                        folder_id=folder_id,
                    )
                    session.add(assignment)

                session.commit()
            except KeyError:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error assigning agent {agent_id} to folder {folder_id}: {e}")
                raise

    def get_user_folder_assignments(self, user_id: str) -> Dict[str, str]:
        """Get a mapping of agent_id -> folder_id for a user."""
        with self.metadata.get_db_session() as session:
            try:
                assignments = session.query(AgentFolderAssignment).filter(
                    AgentFolderAssignment.user_id == user_id
                ).all()
                return {a.agent_id: a.folder_id for a in assignments}
            except Exception as e:
                LOGGER.error(f"Error getting folder assignments for user {user_id}: {e}")
                raise

    def get_user_agent_sort_orders(self, user_id: str) -> Dict[str, int]:
        """Get a mapping of agent_id -> sort_order for a user."""
        with self.metadata.get_db_session() as session:
            try:
                rows = session.query(UserAgentSortOrder).filter(
                    UserAgentSortOrder.user_id == user_id
                ).all()
                return {r.agent_id: r.sort_order for r in rows}
            except Exception as e:
                LOGGER.error(f"Error getting agent sort orders for user {user_id}: {e}")
                raise

    def reorder_agents(self, user_id: str, agent_ids: List[str]) -> None:
        """Set sort_order for a list of agents. agent_ids[0] gets sort_order=0, etc."""
        with self.metadata.get_db_session() as session:
            try:
                for index, agent_id in enumerate(agent_ids):
                    existing = session.query(UserAgentSortOrder).filter(
                        UserAgentSortOrder.user_id == user_id,
                        UserAgentSortOrder.agent_id == agent_id
                    ).first()
                    if existing:
                        existing.sort_order = index
                    else:
                        session.add(UserAgentSortOrder(
                            user_id=user_id,
                            agent_id=agent_id,
                            sort_order=index,
                        ))
                session.commit()
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error reordering agents for user {user_id}: {e}")
                raise

    def reorder_folders(self, user_id: str, folder_ids: List[str]) -> None:
        """Set sort_order for a list of folders. folder_ids[0] gets sort_order=0, etc."""
        with self.metadata.get_db_session() as session:
            try:
                for index, folder_id in enumerate(folder_ids):
                    folder = session.query(AgentFolder).filter(
                        AgentFolder.id == folder_id,
                        AgentFolder.user_id == user_id
                    ).first()
                    if not folder:
                        raise KeyError(f"Folder not found: {folder_id}")
                    folder.sort_order = index
                session.commit()
            except KeyError:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error reordering folders for user {user_id}: {e}")
                raise
