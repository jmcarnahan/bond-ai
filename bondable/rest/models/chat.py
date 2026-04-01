import re

from pydantic import BaseModel, field_validator
from typing import Optional, List

# Safe-character pattern: blocks XSS payloads (< > " ' &) while allowing any reasonable ID format.
# XML escaping in _create_bond_message_tag / chat.py fallbacks is the primary XSS defense.
SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')

# Opaque file ID pattern: only bond_file_<hex> format allowed from clients.
# Blocks raw S3 URIs at the API boundary to prevent unauthorized cross-bucket access.
OPAQUE_FILE_ID_PATTERN = re.compile(r'^bond_file_[0-9a-f]+$')


class ChatAttachment(BaseModel):
    file_id: str
    suggested_tool: str  # "file_search" or "code_interpreter"

    @field_validator('file_id')
    @classmethod
    def validate_file_id(cls, v: str) -> str:
        if not v or not OPAQUE_FILE_ID_PATTERN.match(v):
            raise ValueError(
                'file_id must be an opaque file identifier (bond_file_<hex>)'
            )
        return v


class ChatRequest(BaseModel):
    thread_id: Optional[str] = None  # Can be None to create a new thread
    agent_id: str
    prompt: str
    attachments: Optional[List[ChatAttachment]] = None  # List of attachments with tool info
    hidden: bool = False  # True for introduction messages hidden from chat UI
    override_role: Optional[str] = None  # DEPRECATED: ignored by server, kept for backward compat

    @field_validator('thread_id')
    @classmethod
    def validate_thread_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not SAFE_ID_PATTERN.match(v):
            raise ValueError(
                'thread_id contains invalid characters'
            )
        return v

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not v or not SAFE_ID_PATTERN.match(v):
            raise ValueError(
                'agent_id contains invalid characters'
            )
        return v
