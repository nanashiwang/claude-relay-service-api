from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ProductKind
from app.schemas.common import ORMModel


class ProductOut(ORMModel):
    id: int
    sku: str
    provider: str
    kind: ProductKind
    duration_days: int | None
    usage_usd: int | None
    name: str
    price_cents: int
    discount_percent: int | None
    currency: str
    active: bool


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    price_cents: int | None = Field(default=None, ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    active: bool | None = None
