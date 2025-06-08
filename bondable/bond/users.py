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
                # This handles migration from email-based to user_id-based identification
                email_user = db_session.query(UserModel).filter_by(email=email).first()
                if email_user:
                    # Update the existing user's ID to the OAuth provider's user_id
                    LOGGER.info(f"Migrating user {email} from ID {email_user.id} to OAuth ID {user_id}")
                    email_user.id = user_id
                    email_user.updated_at = datetime.now()
                    
                    # Also update name if it's different
                    if name and email_user.name != name:
                        email_user.name = name
                    
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