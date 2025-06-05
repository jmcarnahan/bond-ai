from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    email: str
    name: Optional[str] = None
    provider: Optional[str] = "google"  # OAuth2 provider used for authentication