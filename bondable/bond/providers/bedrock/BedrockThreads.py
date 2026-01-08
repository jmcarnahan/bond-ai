"""
BedrockThreads - Thread management for AWS Bedrock provider with session support

This implementation stores conversation threads in our metadata database and manages
sessionId and sessionState for Bedrock Agents.
"""

from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.broker import BondMessage
from bondable.bond.config import Config
from bondable.bond.providers.metadata import Thread
from bondable.bond.providers.files import FileDetails
from bondable.bond.providers.provider import Provider
from .BedrockMetadata import BedrockMetadata, BedrockMessage
import uuid
import logging
from typing import Dict, Optional, Any, List
import datetime
import boto3
import json

LOGGER = logging.getLogger(__name__)


class BedrockThreadsProvider(ThreadsProvider):
    """Thread management for Bedrock using metadata storage with session support"""

    def __init__(self, bedrock_agent_runtime_client: boto3.client, provider: Provider, metadata: BedrockMetadata):
        self.metadata = metadata
        self.bedrock_agent_runtime_client = bedrock_agent_runtime_client
        self.bond_provider: Provider = provider
        LOGGER.info("Initialized BedrockThreadsProvider with session support")


    def _delete_thread_messages(self, thread_id: str, user_id: str) -> int:
        """Delete all messages in a thread"""
        session = self.metadata.get_db_session()
        try:
            count = session.query(BedrockMessage)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .delete()
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error deleting messages: {e}")
            raise
        finally:
            session.close()



    # Message Management Methods
    def _create_message(self, thread_id: str, user_id: str, role: str, message_type: str,
                      content: List[Dict], metadata: Optional[Dict] = None,
                      session_id: Optional[str] = None, message_id: Optional[str] = None) -> str:
        """Create a new message in a thread"""
        session = self.metadata.get_db_session()
        try:
            # Get the session_id from thread if not provided
            if not session_id:
                thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .first()
                if thread:
                    session_id = thread.session_id

            # Get the next message index for this thread
            max_index = session.query(BedrockMessage.message_index)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .order_by(BedrockMessage.message_index.desc())\
                .first()

            message_index = (max_index[0] + 1) if max_index else 0

            message = BedrockMessage(
                id=message_id or str(uuid.uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                type=message_type,
                content=content,
                message_index=message_index,
                message_metadata=metadata or {}
            )

            session.add(message)
            session.commit()

            LOGGER.info(f"Created message {message.id} in thread {thread_id} with session {session_id} - message index {message_index}")
            return message.id

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error creating message: {e}")
            raise
        finally:
            session.close()

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
            from bondable.bond.providers.metadata import Thread
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
                    count = self._delete_thread_messages(thread_id, user_id)
                    total_deleted += count

                # Before we delete the thread we need to delete the session in bedrock
                # session_id = self.get_thread_session_id(thread_id=thread_id)
                # if session_id is not None:
                #     try:
                #         response = self.bedrock_agent_runtime_client.delete_session(
                #             sessionIdentifier=session_id
                #         )
                #         LOGGER.info(f"Deleted Bedrock session {session_id} associated with thread {thread_id}: {response}")
                #     except Exception as bedrockExc:
                #         LOGGER.exception(f"Error deleting bedrock session {session_id}: {bedrockExc}")
                # else:
                #     LOGGER.error(f"Unable to delete bedrock session for thread: {session_id} - no session id")

                LOGGER.info(f"Deleted {total_deleted} messages from thread {thread_id}")
                return True

            except Exception as e:
                session.rollback()
                LOGGER.exception(f"Error deleting thread {thread_id}: {e}")
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
        session_id = uuid.uuid4().hex

        # response = self.bedrock_agent_runtime_client.create_session()
        # if response:
        #     session_id = response['sessionId']

        thread_id = f"thread_{session_id}"  # Thread ID is based on session ID
        LOGGER.info(f"Created new thread ID: {thread_id} with session ID: {session_id}")

        return thread_id

    def has_messages(self, thread_id: str, last_message_id: Optional[str] = None) -> bool:
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
                    attachments = []
                    if isinstance(msg.content, str):
                        content_text = msg.content
                    if isinstance(msg.content, list):
                        for content_item in msg.content:
                            if isinstance(content_item, dict):
                                if 'text' in content_item:
                                    content_text += content_item['text']
                                elif 'file' in content_item:
                                    attachments.append({
                                        'type': 'file',
                                        'data': content_item['file']
                                    })
                                else:
                                    LOGGER.warning(f"Unknown content item in message {msg.id}: {content_item}")
                            else:
                                LOGGER.warning(f"Unexpected content type in message {msg.id}: {type(content_item)}")
                    else:
                        content_text = str(msg.content)

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

                    LOGGER.debug(f"Get messages - message {msg.id}/{msg.role}/{message_type} - attachments: {attachments}")

                    # Store additional attributes that aren't part of the constructor
                    bond_message.metadata = msg.message_metadata or {}
                    bond_message.metadata['message_index'] = msg.message_index
                    bond_message.metadata['session_id'] = msg.session_id  # Include session ID
                    bond_message.metadata['agent_id'] = agent_id  # Include agent ID
                    bond_message.metadata['attachments'] = attachments if attachments else None

                    # bond_message.message_index = msg.message_index
                    # bond_message.attachments = attachments if attachments else None
                    # bond_message.session_id = msg.session_id  # Include session ID
                    # bond_message.agent_id = agent_id  # Include agent ID

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
            file_ids = [attachment['file_id'] for attachment in attachments if 'file_id' in attachment]
            file_details_list: FileDetails = self.bond_provider.files.get_file_details(file_ids=file_ids)
            for file_details in file_details_list:
                LOGGER.debug(f"Add messages - message {message_id} - attachments: {file_details}")
                bedrock_content.append({
                    'file': {
                        'file_id': file_details.file_id,
                        'file_path': file_details.file_path,
                        'file_hash': file_details.file_hash,
                        'mime_type': file_details.mime_type,
                        'owner_user_id': file_details.owner_user_id,
                        'file_size': file_details.file_size
                    }
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
        return self._create_message(
            message_id=message_id,
            thread_id=thread_id,
            user_id=user_id,
            role=role,
            message_type=message_type,
            content=bedrock_content,
            metadata=metadata,
            session_id=session_id
        )


    def get_thread_session_id(self, thread_id: str) -> Optional[str]:
        """Get the session ID for a thread"""
        # Query from database
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.metadata import Thread
                thread: Thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id)\
                    .first()

                if thread and thread.session_id:
                    return thread.session_id
                else:
                    LOGGER.debug(f"No session ID found for thread {thread_id} in metadata - falling back to thread_id format")

        except Exception as e:
            LOGGER.error(f"Error getting session ID for thread {thread_id}: {e}")
            return None

        # Fallback from thread_id format: thread_{session_id}
        if thread_id and thread_id.startswith('thread_'):
            session_id = thread_id[7:]  # More efficient than replace
            if session_id:  # Validate it's not empty
                return session_id

    def get_thread_session_state(self, thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the session state for a thread"""
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.metadata import Thread
                thread: Thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .first()

                return thread.session_state if thread else {}

        except Exception as e:
            LOGGER.error(f"Error getting session state: {e}")
            return None

    def update_thread_session(self, thread_id: str, user_id: str, session_id: str, session_state: Dict[str, Any]) -> bool:
        """Update the session state for a thread"""
        session = self.metadata.get_db_session()
        try:
            from bondable.bond.providers.metadata import Thread
            thread = session.query(Thread)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .first()

            if thread:
                thread.session_state = session_state
                thread.session_id = session_id
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

    def list_sessions(self, max_results=100):
        response = self.bedrock_agent_runtime_client.list_sessions(
            maxResults=max_results,
        )
        return response['sessionSummaries']

    def get_response_message_count(self, thread_id: str, role: str = 'assistant') -> int:
        """
        Get the count of assistant messages in a thread.

        Args:
            thread_id: The thread ID

        Returns:
            Count of messages with role 'assistant'
        """
        try:
            with self.metadata.get_db_session() as session:
                from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
                count = session.query(BedrockMessage)\
                    .filter_by(thread_id=thread_id, role=role)\
                    .count()
                return count
        except Exception as e:
            LOGGER.error(f"Error getting assistant message count for thread {thread_id}: {e}")
            return 0

    def update_message_feedback(self, message_id: str, user_id: str,
                                feedback_type: str, feedback_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Update feedback in message_metadata JSON field.

        Args:
            message_id: The message ID to update
            user_id: User providing feedback (must own the message)
            feedback_type: "up" or "down"
            feedback_message: Optional feedback text

        Returns:
            Updated feedback dict with type, message, and updated_at
        """
        from sqlalchemy.orm.attributes import flag_modified

        session = self.metadata.get_db_session()
        try:
            message = session.query(BedrockMessage)\
                .filter_by(id=message_id, user_id=user_id)\
                .first()

            if not message:
                raise ValueError(f"Message {message_id} not found for user {user_id}")

            # Get existing metadata or create new dict
            metadata = dict(message.message_metadata) if message.message_metadata else {}

            # Update feedback in metadata
            feedback = {
                'type': feedback_type,
                'message': feedback_message,
                'updated_at': datetime.datetime.now().isoformat()
            }
            metadata['feedback'] = feedback

            # Update the message metadata - assign new dict to trigger SQLAlchemy change detection
            message.message_metadata = metadata
            # Flag the JSON column as modified to ensure SQLAlchemy persists the change
            flag_modified(message, 'message_metadata')
            session.commit()

            LOGGER.info(f"Updated feedback for message {message_id}: {feedback_type}")
            return feedback

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error updating message feedback: {e}")
            raise
        finally:
            session.close()

    def delete_message_feedback(self, message_id: str, user_id: str) -> bool:
        """
        Remove feedback from message_metadata.

        Args:
            message_id: The message ID to update
            user_id: User removing feedback (must own the message)

        Returns:
            True if feedback was deleted, False if no feedback existed
        """
        from sqlalchemy.orm.attributes import flag_modified

        session = self.metadata.get_db_session()
        try:
            message = session.query(BedrockMessage)\
                .filter_by(id=message_id, user_id=user_id)\
                .first()

            if not message:
                raise ValueError(f"Message {message_id} not found for user {user_id}")

            # Get existing metadata as a new dict to avoid mutation issues
            metadata = dict(message.message_metadata) if message.message_metadata else {}

            # Remove feedback if it exists
            if 'feedback' in metadata:
                del metadata['feedback']
                message.message_metadata = metadata
                # Flag the JSON column as modified to ensure SQLAlchemy persists the change
                flag_modified(message, 'message_metadata')
                session.commit()
                LOGGER.info(f"Deleted feedback for message {message_id}")
                return True
            else:
                LOGGER.debug(f"No feedback to delete for message {message_id}")
                return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error deleting message feedback: {e}")
            raise
        finally:
            session.close()
