from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ProductKind
from app.schemas.common import ORMModel


class ProductTierDiscountOut(ORMModel):
    min_quantity: int
    discount_percent: int


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
    tier_discounts: list[ProductTierDiscountOut] = Field(default_factory=list)
    currency: str
    active: bool


class ProductTierDiscountIn(BaseModel):
    min_quantity: int = Field(..., ge=1)
    discount_percent: int = Field(..., ge=1, le=99)


class ProductCreateIn(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(..., min_length=1, max_length=16)
    kind: ProductKind
    duration_days: int | None = Field(default=None, ge=1)
    usage_usd: int | None = Field(default=None, ge=1)
    name: str = Field(..., min_length=1, max_length=128)
    price_cents: int = Field(..., ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    tier_discounts: list[ProductTierDiscountIn] = Field(default_factory=list)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    active: bool = True

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "ProductCreateIn":
        if self.kind == ProductKind.day and self.duration_days is None:
            raise ValueError("kind=day 时必须提供 duration_days")
        if self.kind == ProductKind.usage and self.usage_usd is None:
            raise ValueError("kind=usage 时必须提供 usage_usd")
        return self


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    price_cents: int | None = Field(default=None, ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    tier_discounts: list[ProductTierDiscountIn] | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    active: bool | None = None
