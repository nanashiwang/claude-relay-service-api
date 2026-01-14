from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CardCodeStatus
from app.schemas.common import ORMModel


class ClaimIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)


class ClaimOut(BaseModel):
    claim_id: int
    sku: str
    cost_cents: int
    currency: str
    card_code: str
    balance_after_cents: int


class ClaimBatchIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=50)


class ClaimBatchOut(BaseModel):
    sku: str
    quantity: int
    unit_cost_cents: int
    total_cost_cents: int
    currency: str
    card_codes: list[str]
    balance_after_cents: int


class ApiKeyOut(ORMModel):
    id: int
    user_id: int
    name: str | None
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class ApiKeyCreateOut(BaseModel):
    id: int
    user_id: int
    name: str | None
    key_prefix: str
    api_key: str


class AdminCardCodeOut(BaseModel):
    id: int
    product_sku: str
    status: CardCodeStatus
    code: str
    order_id: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
