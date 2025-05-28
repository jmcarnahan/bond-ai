from pydantic import BaseModel
from typing import Optional


class ThreadRef(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class CreateThreadRequest(BaseModel):
    name: Optional[str] = None


class MessageRef(BaseModel):
    id: str
    type: str
    role: str
    content: str