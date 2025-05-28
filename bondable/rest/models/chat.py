from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    agent_id: str
    prompt: str