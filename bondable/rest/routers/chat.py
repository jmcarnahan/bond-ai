from typing import Annotated
import asyncio
import queue
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import logging

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.chat import ChatRequest
from bondable.rest.dependencies.auth import get_current_user_with_token
from bondable.rest.dependencies.providers import get_bond_provider
from bondable.utils.logging_utils import safe_id
from bondable.rest.routers.files import _resolve_file_id
from xml.sax.saxutils import escape as xml_escape  # nosec B406 - used for output encoding, not parsing

router = APIRouter(prefix="/chat", tags=["Chat"])
LOGGER = logging.getLogger(__name__)

_KEEPALIVE_COMMENT = "<!-- keepalive -->\n"
_KEEPALIVE_INTERVAL = 15  # seconds
_SENTINEL = object()


async def async_keepalive_wrapper(sync_gen, keepalive_interval=_KEEPALIVE_INTERVAL):
    """
    Wrap a synchronous generator in an async generator that yields
    ``<!-- keepalive -->`` XML comments when no data arrives within
    *keepalive_interval* seconds.  This prevents infrastructure (e.g.
    App Runner) from killing idle HTTP connections during long Bedrock
    operations like tool calls.

    XML comments are transparent to the frontend's regex extractor
    (strips tags) and the XML parser (ignores comments).
    """
    q: queue.Queue = queue.Queue()

    def _drain_sync_gen():
        try:
            for item in sync_gen:
                q.put(item)
        except Exception as exc:
            q.put(exc)
        finally:
            q.put(_SENTINEL)

    # Run the sync generator in a background thread
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, _drain_sync_gen)

    try:
        while True:
            # Poll the queue with short sleeps so we can yield keepalives
            waited = 0.0
            poll_interval = 0.1
            item = None
            while True:
                try:
                    item = q.get_nowait()
                    break
                except queue.Empty:
                    if waited >= keepalive_interval:
                        yield _KEEPALIVE_COMMENT
                        waited = 0.0
                    else:
                        await asyncio.sleep(poll_interval)
                        waited += poll_interval

            if item is _SENTINEL:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # Wait for the background thread to finish
        await fut


@router.post("")
async def chat(
    request_body: ChatRequest,
    user_and_token: Annotated[tuple[User, str], Depends(get_current_user_with_token)],
    provider: Provider = Depends(get_bond_provider)
):
    """Stream chat responses for a specific thread and agent."""
    current_user, jwt_token = user_and_token

    # Handle thread creation if thread_id is None
    thread_id = request_body.thread_id
    if thread_id is None:
        LOGGER.info("No thread_id provided, creating new thread")

        # Use prompt for thread name only if it's a visible user message, otherwise use generic name
        if not request_body.hidden:
            thread_name = request_body.prompt[:30] + "..." if len(request_body.prompt) > 30 else request_body.prompt
        else:
            # For hidden messages (introduction), use generic name
            thread_name = "New Conversation"

        try:
            new_thread = provider.threads.create_thread(user_id=current_user.user_id, name=thread_name)
            thread_id = new_thread.thread_id
            LOGGER.info(f"Created new thread: {thread_id} with name: {thread_name}")
        except Exception as e:
            LOGGER.error("Failed to create thread: %s", type(e).__name__, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create new thread. Please try again."
            )
    else:
        # Check if this is a visible user message and the thread name needs updating
        if not request_body.hidden:
            try:
                existing_thread = provider.threads.get_thread(thread_id, current_user.user_id)
                if existing_thread and existing_thread.name == "New Conversation":
                    new_thread_name = request_body.prompt[:30] + "..." if len(request_body.prompt) > 30 else request_body.prompt
                    provider.threads.update_thread(thread_id, current_user.user_id, new_thread_name)
                    LOGGER.info(f"Updated thread {thread_id} name from 'New Conversation' to: {new_thread_name}")
            except Exception as e:
                LOGGER.error(f"Failed to update thread name for {thread_id}: {e}", exc_info=True)
                # Don't fail the request, just log the error

    if request_body.hidden:
        LOGGER.info(f"Hidden message (introduction) being sent: {request_body.prompt[:100]}...")

    # Build resolved attachments with appropriate tools based on suggested_tool
    resolved_attachements = []
    if request_body.attachments:
        for attachment in request_body.attachments:
            try:
                resolved_fid = _resolve_file_id(attachment.file_id, provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid attachment file ID format: {attachment.file_id}"
                )
            tool_type = attachment.suggested_tool if attachment.suggested_tool in ["file_search", "code_interpreter"] else "file_search"
            resolved_attachements.append({
                "file_id": resolved_fid,
                "tools": [{"type": tool_type}]
            })

    try:
        # Get the agent instance
        agent_instance = provider.agents.get_agent(agent_id=request_body.agent_id)
        if not agent_instance:
            LOGGER.warning(f"Agent {request_body.agent_id} not found for chat.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # Debug agent instance details
        LOGGER.debug(f"Chat Message Details:")
        LOGGER.debug(f"  Agent Name: {agent_instance.get_name()}")
        if hasattr(agent_instance, 'model'):
            LOGGER.debug(f"  Agent Model: {agent_instance.model}")
        if hasattr(agent_instance, 'bedrock_agent_id'):
            LOGGER.debug(f"  Bedrock Agent ID: {agent_instance.bedrock_agent_id}")
        if hasattr(agent_instance, 'bedrock_agent_alias_id'):
            LOGGER.debug(f"  Bedrock Alias ID: {agent_instance.bedrock_agent_alias_id}")

        # Check if this is a default agent (accessible to all users)
        is_default_agent = False
        try:
            # Check if this agent is the default agent by comparing with the default agent ID
            default_agent = provider.agents.get_default_agent()
            is_default_agent = default_agent and default_agent.get_agent_id() == request_body.agent_id
        except Exception as e:
            LOGGER.error(f"Error checking if agent {request_body.agent_id} is default: {e}")

        # Validate user access to agent (skip validation for default agents)
        if not is_default_agent and not provider.agents.can_user_access_agent(user_id=current_user.user_id, agent_id=request_body.agent_id):
            LOGGER.warning("Unauthorized access attempt on agent %s", safe_id(request_body.agent_id))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # T27: Check if user has read-only permission — if so, disable external MCP tools
        if not is_default_agent:
            user_perm = provider.agents.get_user_agent_permission(current_user.user_id, request_body.agent_id)
            if user_perm == 'can_use_read_only':
                # Temporarily override agent metadata to block write tools
                if hasattr(agent_instance, 'metadata') and isinstance(agent_instance.metadata, dict):
                    agent_instance.metadata['allow_write_tools'] = False
                    LOGGER.info(f"Read-only user {current_user.user_id} — MCP tools disabled for agent {request_body.agent_id}")

        # Track the last agent used on this thread (non-blocking)
        try:
            provider.threads.update_thread_last_agent(thread_id, current_user.user_id, request_body.agent_id)
        except Exception as e:
            LOGGER.error(f"Failed to update last_agent_id: {e}", exc_info=True)

        # Stream response generator with safety net to ensure frontend always gets a response
        def stream_response_generator():
            bond_message_open = False
            has_yielded_bond_message = False
            has_yielded_done = False
            has_yielded_assistant_content = False
            current_is_assistant = False
            try:
                for response_chunk in agent_instance.stream_response(
                    thread_id=thread_id,
                    prompt=request_body.prompt,
                    attachments=resolved_attachements,
                    hidden=request_body.hidden,
                    current_user=current_user,
                    jwt_token=jwt_token
                ):
                    # Track bond message state for safety net guarantees
                    if isinstance(response_chunk, str):
                        if response_chunk.startswith('<_bondmessage '):
                            bond_message_open = True
                            has_yielded_bond_message = True
                            if 'is_done="true"' in response_chunk:
                                has_yielded_done = True
                            # Track if this is an assistant content message
                            current_is_assistant = 'role="assistant"' in response_chunk
                        elif response_chunk == '</_bondmessage>':
                            bond_message_open = False
                            current_is_assistant = False
                        elif current_is_assistant and response_chunk.strip():
                            has_yielded_assistant_content = True
                    yield response_chunk

                # --- Post-stream guarantees (only reached if no exception) ---

                # Content guarantee: if bond messages were sent but no assistant
                # text content was delivered, emit a fallback so the UI isn't empty
                if has_yielded_bond_message and not has_yielded_assistant_content:
                    LOGGER.warning(
                        f"Stream for thread {thread_id}, agent {request_body.agent_id} "
                        f"completed with bond messages but no assistant content"
                    )
                    if bond_message_open:
                        yield '</_bondmessage>'
                        bond_message_open = False
                    fallback_id = str(uuid.uuid4())
                    yield (
                        f'<_bondmessage '
                        f'id="{fallback_id}" '
                        f'thread_id="{xml_escape(str(thread_id))}" '
                        f'agent_id="{xml_escape(str(request_body.agent_id))}" '
                        f'type="error" '
                        f'role="system" '
                        f'is_error="true" '
                        f'is_done="true">'
                    )
                    yield "The agent was unable to generate a response. Please try again."
                    yield '</_bondmessage>'
                    has_yielded_done = True

                # Done guarantee: if bond messages were sent but no is_done="true"
                # signal was emitted, add one so the frontend knows streaming is finished
                if has_yielded_bond_message and not has_yielded_done:
                    if bond_message_open:
                        yield '</_bondmessage>'
                        bond_message_open = False
                    done_id = str(uuid.uuid4())
                    yield (
                        f'<_bondmessage '
                        f'id="{done_id}" '
                        f'thread_id="{xml_escape(str(thread_id))}" '
                        f'agent_id="{xml_escape(str(request_body.agent_id))}" '
                        f'type="text" '
                        f'role="system" '
                        f'is_error="false" '
                        f'is_done="true">'
                    )
                    yield "Done."
                    yield '</_bondmessage>'

            except Exception as e:
                LOGGER.exception(
                    f"Error during chat streaming for thread {thread_id}, "
                    f"agent {request_body.agent_id}: {e}"
                )
                try:
                    # Close any open bond message tag before emitting the error message
                    if bond_message_open:
                        yield '</_bondmessage>'

                    # Build a user-facing error message that includes exception details
                    # so users can relay what they saw. Details are also logged above.
                    error_type = type(e).__name__
                    error_detail = str(e)
                    # Truncate very long error messages to avoid flooding the UI
                    if len(error_detail) > 300:
                        error_detail = error_detail[:300] + "..."
                    user_error_msg = (
                        f"An unexpected error occurred while processing your request "
                        f"({error_type}: {error_detail}). Please try again."
                    )

                    # Emit a complete error bond message so the frontend always shows something
                    error_id = str(uuid.uuid4())
                    agent_id = request_body.agent_id
                    yield (
                        f'<_bondmessage '
                        f'id="{error_id}" '
                        f'thread_id="{xml_escape(str(thread_id))}" '
                        f'agent_id="{xml_escape(str(agent_id))}" '
                        f'type="error" '
                        f'role="system" '
                        f'is_error="true" '
                        f'is_done="true">'
                    )
                    yield user_error_msg
                    yield '</_bondmessage>'
                except Exception as inner_e:
                    # Fallback: if even the error handler fails, yield a minimal message
                    LOGGER.critical(
                        f"Error handler itself failed for thread {thread_id}: {inner_e}",
                        exc_info=True
                    )
                    try:
                        yield (
                            '<_bondmessage '
                            'id="error-fallback" '
                            f'thread_id="{xml_escape(str(thread_id or "unknown"))}" '
                            f'agent_id="{xml_escape(str(request_body.agent_id or "unknown"))}" '
                            'type="error" '
                            'role="system" '
                            'is_error="true" '
                            'is_done="true">'
                        )
                        yield "An internal error occurred. Please try again."
                        yield '</_bondmessage>'
                    except Exception:
                        LOGGER.critical("All error handlers failed for chat stream")

        return StreamingResponse(
            async_keepalive_wrapper(stream_response_generator()),
            media_type="text/event-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error("Error during chat streaming for thread %s, agent %s: %s", safe_id(thread_id), safe_id(request_body.agent_id), type(e).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not stream chat responses.")
