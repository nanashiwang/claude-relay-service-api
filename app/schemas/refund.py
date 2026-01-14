from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import RequestStatus
from app.schemas.common import ORMModel

MAX_AMOUNT_CENTS = 2_000_000_000  # 防止 int32 溢出/异常(约 20,000,000.00)


class RefundCreateIn(BaseModel):
    amount_cents: int = Field(ge=1, le=MAX_AMOUNT_CENTS)
    currency: str = Field(default="CNY", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    reason: str | None = Field(default=None, max_length=2000)


class RefundOut(ORMModel):
    id: int
    user_id: int
    amount_cents: int
    currency: str
    reason: str | None
    status: RequestStatus
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    review_note: str | None
