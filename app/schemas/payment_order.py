from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PaymentOrderStatus


class PaymentOrderCreateIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=50)
    pay_type: str = Field(default="alipay", min_length=3, max_length=16)
    device: str | None = Field(default=None, min_length=2, max_length=16)


class PaymentOrderCreateOut(BaseModel):
    order_no: str
    sku: str
    quantity: int
    total_price_cents: int
    currency: str
    pay_type: str
    pay_url: str


class PaymentOrderOut(BaseModel):
    order_no: str
    sku: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int
    currency: str
    pay_type: str
    status: PaymentOrderStatus
    trade_no: str | None
    card_codes: list[str]
    failure_reason: str | None
    created_at: datetime
    paid_at: datetime | None
    delivered_at: datetime | None
