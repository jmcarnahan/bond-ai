from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    agent_id: str
    prompt: str

    # attachments are more than just fileIds. They can include tools and other metadata.
    # TODO: Define a more complex type for attachments if needed.
    attachments: list[str] | None = None 
