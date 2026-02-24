from __future__ import annotations

from pydantic import BaseModel, Field


class EpayConfigOut(BaseModel):
    id: int | None = None
    source: str = "db"
    base_url: str = ""
    pid: str = ""
    merchant_key: str = ""
    sign_type: str = "MD5"
    public_base_url: str | None = None
    notify_url: str | None = None
    return_url: str | None = None
    active: bool = True


class EpayConfigUpdateIn(BaseModel):
    base_url: str = Field(..., min_length=5, max_length=255)
    pid: str = Field(..., min_length=1, max_length=64)
    merchant_key: str = Field(..., min_length=1, max_length=255)
    sign_type: str = Field(default="MD5", min_length=3, max_length=16)
    public_base_url: str | None = Field(default=None, max_length=255)
    notify_url: str | None = Field(default=None, max_length=1000)
    return_url: str | None = Field(default=None, max_length=1000)
    active: bool = True
