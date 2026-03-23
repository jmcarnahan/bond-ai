from pydantic import BaseModel
from typing import Optional, List


class FolderRef(BaseModel):
    id: str
    name: str
    agent_count: int = 0
    sort_order: int = 0


class FolderCreateRequest(BaseModel):
    name: str


class FolderUpdateRequest(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None


class FolderAssignRequest(BaseModel):
    agent_id: str
    folder_id: Optional[str] = None


class AgentReorderRequest(BaseModel):
    folder_id: Optional[str] = None
    agent_ids: List[str]


class FolderReorderRequest(BaseModel):
    folder_ids: List[str]
