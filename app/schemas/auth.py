from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool

