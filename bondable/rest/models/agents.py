from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AgentRef(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolResourceFilesList(BaseModel):
    file_ids: List[str] = Field(default_factory=list)


class ToolResourcesRequest(BaseModel):
    code_interpreter: Optional[ToolResourceFilesList] = None
    file_search: Optional[ToolResourceFilesList] = None


class ToolResourcesResponse(BaseModel):
    code_interpreter: Optional[ToolResourceFilesList] = None
    file_search: Optional[ToolResourceFilesList] = None


class AgentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    introduction: Optional[str] = None
    reminder: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mcp_tools: Optional[List[str]] = None
    mcp_resources: Optional[List[str]] = None
    group_ids: Optional[List[str]] = Field(default_factory=list)
    file_storage: Optional[str] = 'direct'  # 'direct' | 'knowledge_base'


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    introduction: Optional[str] = None
    reminder: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mcp_tools: Optional[List[str]] = None
    mcp_resources: Optional[List[str]] = None
    file_storage: Optional[str] = None  # 'direct' | 'knowledge_base'


class AgentResponse(BaseModel):
    agent_id: str
    name: str


class AgentDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    introduction: Optional[str] = None
    reminder: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesResponse] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mcp_tools: Optional[List[str]] = None
    mcp_resources: Optional[List[str]] = None
    file_storage: Optional[str] = 'direct'  # 'direct' | 'knowledge_base'


class ModelInfo(BaseModel):
    name: str
    description: str
    is_default: bool = False
