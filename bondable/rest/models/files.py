from pydantic import BaseModel
from typing import Optional, List


class FileUploadResponse(BaseModel):
    provider_file_id: str
    file_name: str
    mime_type: str
    suggested_tool: str
    message: str


class FileDeleteResponse(BaseModel):
    provider_file_id: str
    status: str
    message: Optional[str] = None


class FileDetailsResponse(BaseModel):
    file_id: str
    file_path: str
    file_hash: str
    mime_type: str
    owner_user_id: str
