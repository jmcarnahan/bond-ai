"""
BedrockThreads - Thread management for AWS Bedrock provider with session support

This implementation stores conversation threads in our metadata database and manages
sessionId and sessionState for Bedrock Agents.
"""

from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.broker import BondMessage
from .BedrockMetadata import BedrockMetadata
import uuid
import logging
from typing import Dict, Optional, Any
import datetime

LOGGER = logging.getLogger(__name__)


class BedrockThreadsProvider(ThreadsProvider):
    """Thread management for Bedrock using metadata storage with session support"""
    
    def __init__(self, metadata: BedrockMetadata):
        self.metadata = metadata
        LOGGER.info("Initialized BedrockThreadsProvider with session support")
    
    def delete_thread_resource(self, thread_id: str) -> bool:
        """
        Delete a thread and all its messages.
        
        Args:
            thread_id: The thread ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First delete all messages in the thread
            # Note: We don't have user_id here, so we'll need to delete all messages for this thread
            session = self.metadata.get_db_session()
            try:
                # Get all unique users who have messages in this thread
                from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
                users_with_messages = session.query(BedrockMessage.user_id)\
                    .filter_by(thread_id=thread_id)\
                    .distinct()\
                    .all()
                
                # Delete messages for each user
                total_deleted = 0
                for (user_id,) in users_with_messages:
                    count = self.metadata.delete_thread_messages(thread_id, user_id)
                    total_deleted += count
                
                LOGGER.info(f"Deleted {total_deleted} messages from thread {thread_id}")
                
                # Delete the thread record from base threads table
                from bondable.bond.providers.metadata import Thread
                thread_count = session.query(Thread)\
                    .filter_by(thread_id=thread_id)\
                    .delete()
                session.commit()
                
                LOGGER.info(f"Deleted thread {thread_id} and all associated messages")
                return True
                
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error deleting thread {thread_id}: {e}")
                return False
            finally:
                session.close()
                
        except Exception as e:
            LOGGER.error(f"Error in delete_thread_resource: {e}")
            return False
    
    def create_thread_resource(self) -> str:
        """
        Create a new thread resource with session support.
        
        Returns:
            A new thread ID (format: thread_{session_id})
        """
        session_id = str(uuid.uuid4())  # Create session ID for Bedrock Agent
        thread_id = f"thread_{session_id}"  # Thread ID is based on session ID
        
        LOGGER.info(f"Created new thread ID: {thread_id} with session ID: {session_id}")
        
        # Note: The actual thread record with session_id will be created when the first message is added
        # This design ensures thread_id and session_id are always related
        
        return thread_id
    
    def has_messages(self, thread_id: str, last_message_id: Optional[str]) -> bool:
        """
        Check if thread has new messages after the given message ID.
        
        Args:
            thread_id: The thread to check
            last_message_id: The last message ID seen by the client
            
        Returns:
            True if there are new messages, False otherwise
        """
        # We need to check across all users who might have added messages
        # This is a limitation of not having user_id in the interface
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
                
                if not last_message_id:
                    # Check if thread has any messages
                    count = session.query(BedrockMessage)\
                        .filter_by(thread_id=thread_id)\
                        .count()
                    return count > 0
                
                # Get the message to find its index
                last_msg = session.query(BedrockMessage)\
                    .filter_by(id=last_message_id, thread_id=thread_id)\
                    .first()
                
                if not last_msg:
                    # Message not found, check if thread has any messages
                    count = session.query(BedrockMessage)\
                        .filter_by(thread_id=thread_id)\
                        .count()
                    return count > 0
                
                # Check if there are any messages with higher index for any user
                count = session.query(BedrockMessage)\
                    .filter_by(thread_id=thread_id)\
                    .filter(BedrockMessage.message_index > last_msg.message_index)\
                    .count()
                
                return count > 0
                
        except Exception as e:
            LOGGER.error(f"Error checking for new messages: {e}")
            # On error, assume there might be new messages
            return True
    
    def get_messages(self, thread_id: str, limit: int = 100) -> Dict[str, BondMessage]:
        """
        Get messages from a thread.
        
        Args:
            thread_id: The thread ID
            limit: Maximum number of messages to return
            
        Returns:
            Dictionary mapping message IDs to BondMessage objects
        """
        messages = {}
        
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
                
                # Get all messages for this thread, ordered by index
                # Since we don't have user_id, we get all messages
                query = session.query(BedrockMessage)\
                    .filter_by(thread_id=thread_id)\
                    .order_by(BedrockMessage.message_index.asc())\
                    .limit(limit)
                
                for msg in query.all():
                    # Convert content to text if it's a list with a single text item
                    content_text = ""
                    if isinstance(msg.content, list):
                        for content_item in msg.content:
                            if isinstance(content_item, dict) and 'text' in content_item:
                                content_text += content_item['text']
                    elif isinstance(msg.content, str):
                        content_text = msg.content
                    
                    # Extract attachments if any
                    attachments = []
                    if isinstance(msg.content, list):
                        for content_item in msg.content:
                            if isinstance(content_item, dict):
                                if 'image' in content_item:
                                    # Image attachment
                                    attachments.append({
                                        'type': 'image',
                                        'data': content_item['image']
                                    })
                                elif 'document' in content_item:
                                    # Document attachment
                                    attachments.append({
                                        'type': 'document',
                                        'data': content_item['document']
                                    })
                    
                    # Determine message type based on stored type or attachments
                    message_type = msg.type if msg.type else "text"
                    
                    # Extract agent_id from metadata if available
                    agent_id = None
                    if msg.message_metadata and isinstance(msg.message_metadata, dict):
                        agent_id = msg.message_metadata.get('agent_id')
                    
                    # BondMessage expects: thread_id, message_id, agent_id, type, role, is_error=False, is_done=False, content=None
                    bond_message = BondMessage(
                        thread_id=thread_id,
                        message_id=msg.id,
                        agent_id=agent_id,
                        type=message_type,
                        role=msg.role,
                        is_error=False,
                        is_done=True,  # These are completed messages from DB
                        content=content_text  # This initializes the clob with the content
                    )
                    
                    # Store additional attributes that aren't part of the constructor
                    bond_message.message_index = msg.message_index
                    bond_message.metadata = msg.message_metadata
                    bond_message.attachments = attachments if attachments else None
                    bond_message.session_id = msg.session_id  # Include session ID
                    bond_message.agent_id = agent_id  # Include agent ID
                    
                    messages[msg.id] = bond_message
                
                LOGGER.info(f"Retrieved {len(messages)} messages from thread {thread_id}")
                return messages
                
        except Exception as e:
            LOGGER.error(f"Error retrieving messages: {e}")
            return {}
    
    def add_message(self, thread_id: str, user_id: str, role: str, message_type: str,
                   content: str, attachments: Optional[list] = None,
                   metadata: Optional[Dict] = None, message_id: Optional[Dict] = None) -> str:
        """
        Add a message to a thread.
        
        This is a helper method not in the base interface but useful for Bedrock.
        
        Args:
            message_id: optional
            thread_id: Thread to add message to
            user_id: User who owns this message
            role: 'user' or 'assistant'
            message_type: 'text', 'image_file'
            content: Message content
            attachments: Optional attachments
            metadata: Optional metadata
            
        Returns:
            Message ID
        """
        # Extract session_id from thread_id (format: thread_{session_id})
        session_id = thread_id.replace('thread_', '') if thread_id.startswith('thread_') else None
        
        # Convert to Bedrock content format
        bedrock_content = []
        
        # Add text content
        if content:
            bedrock_content.append({"text": content})
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                if attachment.get('type') == 'image':
                    bedrock_content.append({
                        'image': attachment['data']
                    })
                elif attachment.get('type') == 'document':
                    bedrock_content.append({
                        'document': attachment['data']
                    })
        
        # Ensure thread exists in metadata with session_id
        session = self.metadata.get_db_session()
        try:
            from bondable.bond.providers.metadata import Thread
            thread = session.query(Thread)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .first()
            
            if not thread:
                # Create thread record with session_id
                thread = Thread(
                    thread_id=thread_id,
                    user_id=user_id,
                    name=f"Bedrock Thread {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    session_id=session_id,
                    session_state={}
                )
                session.add(thread)
                session.commit()
                LOGGER.info(f"Created thread record for {thread_id} with session {session_id}")
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error ensuring thread exists: {e}")
        finally:
            session.close()
        
        # Create the message with session_id
        return self.metadata.create_message(
            message_id=message_id,
            thread_id=thread_id,
            user_id=user_id,
            role=role,
            message_type=message_type,
            content=bedrock_content,
            metadata=metadata,
            session_id=session_id
        )
    
    def get_conversation_messages(self, thread_id: str, user_id: str) -> list:
        """
        Get messages formatted for Bedrock Converse API.
        
        Note: This method is deprecated when using Bedrock Agents.
        The agent maintains conversation history internally using sessionId.
        
        Args:
            thread_id: Thread ID
            user_id: User ID
            
        Returns:
            List of messages in Bedrock format
        """
        return self.metadata.get_conversation_messages(thread_id, user_id)
    
    # New methods for session management
    
    def get_thread_session_id(self, thread_id: str) -> Optional[str]:
        """Get the session ID for a thread"""
        # Extract from thread_id format: thread_{session_id}
        if thread_id and thread_id.startswith('thread_'):
            session_id = thread_id[7:]  # More efficient than replace
            if session_id:  # Validate it's not empty
                return session_id
        
        # Fallback: query from database
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.metadata import Thread
                thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id)\
                    .first()
                
                return thread.session_id if thread and hasattr(thread, 'session_id') else None
                
        except Exception as e:
            LOGGER.error(f"Error getting session ID for thread {thread_id}: {e}")
            return None
    
    def get_thread_session_state(self, thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the session state for a thread"""
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.metadata import Thread
                thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .first()
                
                return thread.session_state if thread else None
                
        except Exception as e:
            LOGGER.error(f"Error getting session state: {e}")
            return None
    
    def update_thread_session_state(self, thread_id: str, user_id: str, session_state: Dict[str, Any]) -> bool:
        """Update the session state for a thread"""
        session = self.metadata.get_db_session()
        try:
            from bondable.bond.providers.metadata import Thread
            thread = session.query(Thread)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .first()
            
            if thread:
                thread.session_state = session_state
                thread.updated_at = datetime.datetime.now()
                session.commit()
                LOGGER.info(f"Updated session state for thread {thread_id}")
                return True
            else:
                LOGGER.warning(f"Thread {thread_id} not found for session state update")
                return False
                
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error updating session state: {e}")
            return False
        finally:
            session.close()
    
    def get_thread_info(self, thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete thread information including session data"""
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.metadata import Thread
                thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .first()
                
                if thread:
                    return {
                        'thread_id': thread.thread_id,
                        'session_id': thread.session_id,
                        'session_state': thread.session_state,
                        'name': thread.name,
                        'created_at': thread.created_at,
                        'updated_at': thread.updated_at
                    }
                return None
                
        except Exception as e:
            LOGGER.error(f"Error getting thread info: {e}")
            return None