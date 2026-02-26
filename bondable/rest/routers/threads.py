from typing import Annotated, List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.threads import ThreadRef, CreateThreadRequest, UpdateThreadRequest, PaginatedThreadsResponse, MessageRef, MessageFeedbackRequest, MessageFeedbackResponse
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/threads", tags=["Thread"])
LOGGER = logging.getLogger(__name__)


def _resolve_agent_name(provider: Provider, agent_id: str) -> Optional[str]:
    """Resolve an agent ID to its display name. Returns None if not found or on error."""
    try:
        agent = provider.agents.get_agent(agent_id=agent_id)
        return agent.get_name() if agent else None
    except Exception as e:
        LOGGER.warning(f"Failed to resolve agent name for {agent_id}: {e}")
        return None


@router.get("", response_model=PaginatedThreadsResponse)
async def get_threads(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider),
    offset: int = 0,
    limit: int = 20,
    exclude_empty: bool = True
):
    """Get paginated list of threads for the authenticated user."""
    try:
        offset = max(offset, 0)
        limit = min(max(limit, 1), 100)
        thread_data_list = provider.threads.get_current_threads(
            user_id=current_user.user_id,
            count=limit,
            offset=offset,
            exclude_empty=exclude_empty,
        )
        total = provider.threads.get_thread_count(
            user_id=current_user.user_id,
            exclude_empty=exclude_empty,
        )
        # Batch-resolve agent names for threads with last_agent_id
        agent_name_cache: dict[str, str | None] = {}
        agent_ids = {td['last_agent_id'] for td in thread_data_list if td.get('last_agent_id')}
        for aid in agent_ids:
            agent_name_cache[aid] = _resolve_agent_name(provider, aid)

        threads = [
            ThreadRef(
                id=thread_data['thread_id'],
                name=thread_data['name'],
                description=thread_data.get('description'),
                created_at=thread_data.get('created_at'),
                updated_at=thread_data.get('updated_at'),
                last_agent_id=thread_data.get('last_agent_id'),
                last_agent_name=agent_name_cache.get(thread_data.get('last_agent_id')) if thread_data.get('last_agent_id') else None,
            )
            for thread_data in thread_data_list
        ]
        return PaginatedThreadsResponse(
            threads=threads,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < total,
        )
    except Exception as e:
        LOGGER.error(f"Error fetching threads for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch threads.")


@router.post("", response_model=ThreadRef, status_code=status.HTTP_201_CREATED)
async def create_thread(
    request_body: CreateThreadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Create a new thread for the authenticated user."""
    try:
        created_thread_orm = provider.threads.create_thread(
            user_id=current_user.user_id,
            name=request_body.name
        )

        LOGGER.info(f"User {current_user.user_id} ({current_user.email}) created new thread with ID: {created_thread_orm.thread_id} and name: {created_thread_orm.name}")
        return ThreadRef(
            id=created_thread_orm.thread_id,
            name=created_thread_orm.name,
            description=None
        )
    except Exception as e:
        LOGGER.error(f"Error creating thread for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create new thread.")


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_empty_threads(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Delete all empty threads (no user messages) for the authenticated user."""
    try:
        deleted_count = provider.threads.delete_empty_threads(user_id=current_user.user_id)
        LOGGER.info(f"User {current_user.user_id} ({current_user.email}) cleaned up {deleted_count} empty threads")
        return {"deleted": deleted_count}
    except Exception as e:
        LOGGER.error(f"Error cleaning up empty threads for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not cleanup empty threads.")


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Delete a specific thread for the authenticated user."""
    try:
        deleted = provider.threads.delete_thread(thread_id=thread_id, user_id=current_user.user_id)
        if deleted:
            LOGGER.info(f"User {current_user.user_id} ({current_user.email}) successfully initiated deletion for thread with ID: {thread_id}")
        else:
            LOGGER.warning(f"Attempt to delete thread {thread_id} by user {current_user.user_id} ({current_user.email}) did not result in deletion.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found or not accessible for deletion by this user."
            )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting thread {thread_id} for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete thread.")


@router.put("/{thread_id}", response_model=ThreadRef)
async def update_thread(
    thread_id: str,
    request_body: UpdateThreadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Update a thread's name for the authenticated user."""
    try:
        name = request_body.trimmed_name
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread name cannot be empty."
            )
        updated = provider.threads.update_thread(
            thread_id=thread_id,
            user_id=current_user.user_id,
            name=name,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found or not accessible by this user."
            )
        thread = provider.threads.get_thread(thread_id=thread_id, user_id=current_user.user_id)
        LOGGER.info(f"User {current_user.user_id} ({current_user.email}) renamed thread {thread_id} to '{name}'")
        # Resolve agent name if last_agent_id is set
        last_agent_name = _resolve_agent_name(provider, thread.last_agent_id) if thread.last_agent_id else None
        return ThreadRef(
            id=thread.thread_id,
            name=thread.name,
            description=None,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_agent_id=thread.last_agent_id,
            last_agent_name=last_agent_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error updating thread {thread_id} for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update thread.")


@router.get("/{thread_id}/messages", response_model=List[MessageRef])
async def get_messages(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider),
    limit: Optional[int] = 100
):
    """Get messages for a specific thread."""
    try:
        messages_dict: Dict[str, Any] = provider.threads.get_messages(thread_id=thread_id, limit=limit)

        message_refs = []
        for msg_obj in messages_dict.values():
            # Skip system messages - they should not be returned to the client
            msg_role = getattr(msg_obj, 'role', 'assistant')
            if msg_role == 'system':
                LOGGER.debug(f"Filtering out system message: {getattr(msg_obj, 'message_id', 'unknown')}")
                continue

            actual_content = ""
            if hasattr(msg_obj, 'clob') and msg_obj.clob:
                actual_content = msg_obj.clob.get_content()

            # Handle image messages properly
            message_type = getattr(msg_obj, 'type', 'text')
            image_data = None

            if message_type == 'image_file' and actual_content:
                # Extract base64 data from data URL
                if actual_content.startswith('data:image/png;base64,'):
                    image_data = actual_content[len('data:image/png;base64,'):]
                    actual_content = '[Image]'
                elif actual_content.startswith('data:image/jpeg;base64,'):
                    image_data = actual_content[len('data:image/jpeg;base64,'):]
                    actual_content = '[Image]'
                elif actual_content.startswith('data:image/'):
                    # Handle other image formats - extract the base64 part after the comma
                    comma_index = actual_content.find(',')
                    if comma_index != -1 and comma_index < len(actual_content) - 1:
                        image_data = actual_content[comma_index + 1:]
                        actual_content = '[Image]'

            # Extract agent_id - BondMessage objects have agent_id attribute directly
            metadata = getattr(msg_obj, 'metadata', {}) or {}
            agent_id = metadata.get('agent_id')

            # Extract feedback from metadata
            feedback = metadata.get('feedback', {}) or {}
            feedback_type = feedback.get('type')
            feedback_message = feedback.get('message')

            message_refs.append(MessageRef(
                id=getattr(msg_obj, 'message_id', getattr(msg_obj, 'id', "unknown_id")),
                type=message_type,
                role=msg_role,
                content=actual_content,
                image_data=image_data,
                agent_id=agent_id,
                metadata=metadata,
                feedback_type=feedback_type,
                feedback_message=feedback_message
            ))
        return message_refs

    except Exception as e:
        LOGGER.error(f"Error fetching messages for thread {thread_id}: {e}", exc_info=True)
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found or messages not accessible."
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch messages.")


@router.put("/{thread_id}/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def update_message_feedback(
    thread_id: str,
    message_id: str,
    request: MessageFeedbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Update or create feedback for a specific message."""
    try:
        # Validate feedback_type
        if request.feedback_type not in ('up', 'down'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feedback_type must be 'up' or 'down'"
            )

        feedback = provider.threads.update_message_feedback(
            message_id=message_id,
            user_id=current_user.user_id,
            feedback_type=request.feedback_type,
            feedback_message=request.feedback_message
        )

        LOGGER.info(f"User {current_user.user_id} ({current_user.email}) updated feedback for message {message_id}: {request.feedback_type}")

        return MessageFeedbackResponse(
            message_id=message_id,
            feedback_type=feedback['type'],
            feedback_message=feedback.get('message'),
            updated_at=datetime.fromisoformat(feedback['updated_at'])
        )

    except ValueError as e:
        LOGGER.warning(f"Message not found for feedback update: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error updating feedback for message {message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update feedback.")


@router.delete("/{thread_id}/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_feedback(
    thread_id: str,
    message_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Delete feedback for a specific message."""
    try:
        deleted = provider.threads.delete_message_feedback(
            message_id=message_id,
            user_id=current_user.user_id
        )

        if deleted:
            LOGGER.info(f"User {current_user.user_id} ({current_user.email}) deleted feedback for message {message_id}")
        else:
            LOGGER.debug(f"No feedback to delete for message {message_id}")

    except ValueError as e:
        LOGGER.warning(f"Message not found for feedback deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        LOGGER.error(f"Error deleting feedback for message {message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete feedback.")
