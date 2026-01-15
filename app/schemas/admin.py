from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    balance_cents: int
    currency: str
    created_at: datetime


class AdminApiKeyOut(BaseModel):
    id: int
    user_id: int
    name: str | None
    key_prefix: str
    is_active: bool
    created_at: datetime

