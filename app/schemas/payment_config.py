from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PaymentConfigOut(ORMModel):
    id: int
    name: str
    icon: str | None
    account_info: str
    instructions: str | None
    sort_order: int
    active: bool


class PaymentConfigIn(BaseModel):
    name: str = Field(..., max_length=64)
    icon: str | None = Field(None, max_length=64)
    account_info: str = Field(..., max_length=2000)
    instructions: str | None = Field(None, max_length=2000)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True


class PaymentConfigUpdateIn(BaseModel):
    name: str | None = Field(None, max_length=64)
    icon: str | None = Field(None, max_length=64)
    account_info: str | None = Field(None, max_length=2000)
    instructions: str | None = Field(None, max_length=2000)
    sort_order: int | None = Field(None, ge=0)
    active: bool | None = None
