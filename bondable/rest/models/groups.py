from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class Group(GroupBase):
    id: str
    owner_user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class GroupMember(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    
    
class GroupWithMembers(Group):
    members: List[GroupMember] = []