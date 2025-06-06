from pydantic import BaseModel
from typing import Optional, List


class ChatAttachment(BaseModel):
    file_id: str
    suggested_tool: str  # "file_search" or "code_interpreter"


class ChatRequest(BaseModel):
    thread_id: str
    agent_id: str
    prompt: str
    attachments: Optional[List[ChatAttachment]] = None  # List of attachments with tool info
