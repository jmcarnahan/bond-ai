from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ScheduledJobCreateRequest(BaseModel):
    agent_id: str
    name: str
    prompt: str
    schedule: str  # Cron expression
    timezone: str = "UTC"
    is_enabled: bool = True
    timeout_seconds: int = 300


class ScheduledJobUpdateRequest(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    schedule: Optional[str] = None
    timezone: Optional[str] = None
    is_enabled: Optional[bool] = None
    timeout_seconds: Optional[int] = None


class ScheduledJobResponse(BaseModel):
    id: str
    user_id: str
    agent_id: str
    name: str
    prompt: str
    schedule: str
    timezone: str
    is_enabled: bool
    status: str
    timeout_seconds: int
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
    last_thread_id: Optional[str] = None
    next_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduledJobRunResponse(BaseModel):
    thread_id: str
    thread_name: str
    created_at: Optional[datetime] = None
    status: Optional[str] = None
