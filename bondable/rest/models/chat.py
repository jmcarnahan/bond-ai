from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    agent_id: str
    prompt: str
    attachments: list[str] | None = None # List of file IDs for attachments, if any
