from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str
    captcha_code: str = Field(min_length=4, max_length=8)
    captcha_id: str = Field(min_length=6, max_length=64)
    captcha_expires: int
    captcha_token: str = Field(min_length=8, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CaptchaOut(BaseModel):
    captcha_id: str
    captcha_expires: int
    captcha_token: str
    captcha_svg: str


class UserOut(ORMModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
