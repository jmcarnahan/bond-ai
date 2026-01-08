from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ThreadRef(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreateThreadRequest(BaseModel):
    name: Optional[str] = None


class MessageRef(BaseModel):
    id: str
    type: str
    role: str
    content: str
    image_data: Optional[str] = None  # Base64 image data for image_file types
    agent_id: Optional[str] = None
    is_error: bool = False
    metadata: Optional[dict] = None
    feedback_type: Optional[str] = None  # "up", "down", or None
    feedback_message: Optional[str] = None


class MessageFeedbackRequest(BaseModel):
    feedback_type: str  # "up" or "down"
    feedback_message: Optional[str] = None


class MessageFeedbackResponse(BaseModel):
    message_id: str
    feedback_type: str
    feedback_message: Optional[str]
    updated_at: datetime
