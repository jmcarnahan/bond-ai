from pydantic import BaseModel
from typing import Optional


class FileUploadResponse(BaseModel):
    provider_file_id: str
    file_name: str
    message: str


class FileDeleteResponse(BaseModel):
    provider_file_id: str
    status: str
    message: Optional[str] = None