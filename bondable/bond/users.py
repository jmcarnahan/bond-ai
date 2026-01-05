from typing import Tuple, Optional
from datetime import datetime
import logging

from bondable.bond.providers.metadata import Metadata, User as UserModel

LOGGER = logging.getLogger(__name__)


class Users:
    """Handles user-related operations in the bondable layer."""
    
    def __init__(self, metadata: Metadata):
        self.metadata = metadata
    
    def get_or_create_user(self, user_id: str, email: str, name: str, sign_in_method: str) -> Tuple[str, bool]:
        """Get existing user or create new user in database using OAuth provider's user_id.
        
        Args:
            user_id: OAuth provider's user ID (sub field)
            email: User's email address
            name: User's display name
            sign_in_method: OAuth provider name (e.g., 'google', 'okta')
            
        Returns:
            Tuple of (user_id, is_new_user)
        """
        with self.metadata.get_db_session() as db_session:
            # First try to find by user_id
            existing_user = db_session.query(UserModel).filter_by(id=user_id).first()
            
            if existing_user:
                # Check if any updates are needed
                needs_update = False
                if email and existing_user.email != email:
                    existing_user.email = email
                    needs_update = True
                if name and existing_user.name != name:
                    existing_user.name = name
                    needs_update = True
                
                if needs_update:
                    existing_user.updated_at = datetime.now()
                    db_session.commit()
                    LOGGER.debug(f"Updated existing user {user_id} ({email})")
                else:
                    LOGGER.debug(f"No changes needed for user {user_id} ({email})")
                
                return existing_user.id, False
            else:
                # Check if there's an existing user with this email but different ID
                # This handles users logging in with a different OAuth provider (e.g., Cognito vs Okta)
                # We link by email - same email = same user, keep existing user ID
                email_user = db_session.query(UserModel).filter_by(email=email).first()
                if email_user:
                    # User exists with same email but different provider ID
                    # Keep the existing user ID to preserve foreign key relationships
                    LOGGER.info(f"User {email} logged in via {sign_in_method} (existing ID: {email_user.id}, new provider ID: {user_id})")

                    needs_update = False
                    # Update name if it's different
                    if name and email_user.name != name:
                        email_user.name = name
                        needs_update = True

                    # Optionally update sign_in_method to reflect the latest provider used
                    # (keeping the original sign_in_method is also valid - depends on requirements)
                    if sign_in_method and email_user.sign_in_method != sign_in_method:
                        LOGGER.info(f"Updating sign_in_method for {email} from {email_user.sign_in_method} to {sign_in_method}")
                        email_user.sign_in_method = sign_in_method
                        needs_update = True

                    if needs_update:
                        email_user.updated_at = datetime.now()
                        db_session.commit()

                    return email_user.id, False
                else:
                    # Create new user with OAuth provider's user_id
                    new_user = UserModel(
                        id=user_id,
                        email=email,
                        name=name,
                        sign_in_method=sign_in_method
                    )
                    db_session.add(new_user)
                    db_session.commit()
                    LOGGER.info(f"Created new user {user_id} ({email})")
                    return new_user.id, True

    def delete_user_by_email(self, email: str, provider=None) -> bool:
        """Delete user and all related data by email.

        Args:
            email: The email of the user to delete
            provider: The provider instance for proper resource cleanup

        Returns:
            bool: True if user was deleted successfully, False if user not found
        """
        from bondable.bond.providers.metadata import Group, GroupUser

        with self.metadata.get_db_session() as db_session:
            # First check if user exists
            user = db_session.query(UserModel).filter_by(email=email).first()
            if not user:
                LOGGER.warning(f"User with email {email} not found for deletion")
                return False

            user_id = user.id

            try:
                # 1. Use provider cleanup to properly delete all resources (agents, threads, files, vector stores)
                if provider:
                    LOGGER.info(f"Using provider cleanup for user {email}")
                    provider.cleanup(user_id)
                else:
                    LOGGER.warning(f"No provider provided for user cleanup - skipping resource cleanup for {email}")

                # 2. Remove user from all groups (group memberships)
                memberships_deleted = db_session.query(GroupUser).filter_by(user_id=user_id).delete()
                LOGGER.debug(f"Removed user {email} from {memberships_deleted} groups")

                # 3. Delete groups owned by user (this will also remove all members due to cascade)
                groups_deleted = db_session.query(Group).filter_by(owner_user_id=user_id).delete()
                LOGGER.debug(f"Deleted {groups_deleted} groups owned by user {email}")

                # 4. Finally, delete the user record itself
                db_session.delete(user)

                # Commit all changes
                db_session.commit()

                LOGGER.info(f"Successfully deleted user {email} (id: {user_id}) and all related data")
                return True

            except Exception as e:
                db_session.rollback()
                LOGGER.error(f"Error deleting user {email}: {e}", exc_info=True)
                raise
