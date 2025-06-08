from pydantic import BaseModel
from typing import Optional, List


class ChatAttachment(BaseModel):
    file_id: str
    suggested_tool: str  # "file_search" or "code_interpreter"


class ChatRequest(BaseModel):
    thread_id: Optional[str] = None  # Can be None to create a new thread
    agent_id: str
    prompt: str
    attachments: Optional[List[ChatAttachment]] = None  # List of attachments with tool info
    override_role: Optional[str] = "user"  # Default to "user", can be "system" for introduction messages
