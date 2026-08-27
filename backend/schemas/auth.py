from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr

APIKeyScope = Literal["read", "write", "admin"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class APIKeyCreate(BaseModel):
    name: str
    scope: APIKeyScope = "write"


class APIKeyOut(BaseModel):
    id: UUID
    name: str
    key: str | None = None
    prefix: str
    scope: str

    class Config:
        from_attributes = True
