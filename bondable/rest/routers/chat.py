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
logger = logging.getLogger(__name__)


@router.post("")
async def chat(
    request_body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Stream chat responses for a specific thread and agent."""

    # TODO: Temp workaround until attachments are fully understood. (Logic to define tools entry)
    resolved_attachements = [{ "file_id": fileId, "tools": [{"type": "file_search"}] } 
                             for fileId in request_body.attachments] if request_body.attachments else []

    try:
        # Get the agent instance
        agent_instance = provider.agents.get_agent(agent_id=request_body.agent_id)
        if not agent_instance:
            logger.warning(f"Agent {request_body.agent_id} not found for chat.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # Validate user access to agent
        if not provider.agents.can_user_access_agent(user_id=current_user.email, agent_id=request_body.agent_id):
            logger.warning(f"User {current_user.email} attempted to access agent {request_body.agent_id} without permission for chat.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # Stream response generator
        def stream_response_generator():
            for response_chunk in agent_instance.stream_response(
                thread_id=request_body.thread_id,
                prompt=request_body.prompt,
                attachments=resolved_attachements
            ):
                yield response_chunk

        return StreamingResponse(stream_response_generator(), media_type="text/event-stream")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during chat streaming for thread {request_body.thread_id}, agent {request_body.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not stream chat responses.")