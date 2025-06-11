from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import logging

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.chat import ChatRequest
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/chat", tags=["Chat"])
LOGGER = logging.getLogger(__name__)


@router.post("")
async def chat(
    request_body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Stream chat responses for a specific thread and agent."""
    LOGGER.info(f"Chat request: thread_id={request_body.thread_id}, agent_id={request_body.agent_id}, override_role={request_body.override_role}")
    
    # Handle thread creation if thread_id is None
    thread_id = request_body.thread_id
    if thread_id is None:
        LOGGER.info(f"No thread_id provided, creating new thread for user {current_user.user_id} ({current_user.email})")
        
        # Use prompt for thread name only if it's a user message, otherwise use generic name
        if request_body.override_role == "user":
            thread_name = request_body.prompt[:30] + "..." if len(request_body.prompt) > 30 else request_body.prompt
        else:
            # For system messages (introduction), use generic name
            thread_name = "New Conversation"
        
        try:
            new_thread = provider.threads.create_thread(user_id=current_user.user_id, name=thread_name)
            thread_id = new_thread.thread_id
            LOGGER.info(f"Created new thread: {thread_id} with name: {thread_name}")
        except Exception as e:
            LOGGER.error(f"Failed to create thread for user {current_user.user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create new thread: {str(e)}"
            )
    else:
        # Check if this is a user message and the thread name needs updating
        if request_body.override_role == "user":
            try:
                existing_thread = provider.threads.get_thread(thread_id, current_user.user_id)
                if existing_thread and existing_thread.name == "New Conversation":
                    new_thread_name = request_body.prompt[:30] + "..." if len(request_body.prompt) > 30 else request_body.prompt
                    provider.threads.update_thread(thread_id, current_user.user_id, new_thread_name)
                    LOGGER.info(f"Updated thread {thread_id} name from 'New Conversation' to: {new_thread_name}")
            except Exception as e:
                LOGGER.error(f"Failed to update thread name for {thread_id}: {e}", exc_info=True)
                # Don't fail the request, just log the error
    
    if request_body.override_role == "system":
        LOGGER.info(f"System message (introduction) being sent: {request_body.prompt[:100]}...")
    
    # Build resolved attachments with appropriate tools based on suggested_tool
    resolved_attachements = []
    if request_body.attachments:
        for attachment in request_body.attachments:
            tool_type = attachment.suggested_tool if attachment.suggested_tool in ["file_search", "code_interpreter"] else "file_search"
            resolved_attachements.append({
                "file_id": attachment.file_id, 
                "tools": [{"type": tool_type}]
            })

    try:
        # Get the agent instance
        agent_instance = provider.agents.get_agent(agent_id=request_body.agent_id)
        if not agent_instance:
            LOGGER.warning(f"Agent {request_body.agent_id} not found for chat.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # Validate user access to agent
        if not provider.agents.can_user_access_agent(user_id=current_user.user_id, agent_id=request_body.agent_id):
            LOGGER.warning(f"User {current_user.user_id} ({current_user.email}) attempted to access agent {request_body.agent_id} without permission for chat.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # Stream response generator
        def stream_response_generator():
            for response_chunk in agent_instance.stream_response(
                thread_id=thread_id,
                prompt=request_body.prompt,
                attachments=resolved_attachements,
                override_role=request_body.override_role
            ):
                yield response_chunk

        return StreamingResponse(stream_response_generator(), media_type="text/event-stream")
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error during chat streaming for thread {thread_id}, agent {request_body.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not stream chat responses.")