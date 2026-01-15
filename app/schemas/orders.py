from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OrderOut(BaseModel):
    id: int
    user_id: int
    product_sku: str
    price_cents: int
    currency: str
    card_code: str
    created_at: datetime

