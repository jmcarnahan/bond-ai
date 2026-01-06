from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    email: str
    name: Optional[str] = None
    provider: str
    user_id: str
    # Okta-specific metadata fields
    okta_sub: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    locale: Optional[str] = None
