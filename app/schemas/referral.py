from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ReferralBindIn(BaseModel):
    code: str = Field(min_length=2, max_length=64)


class ReferralSummaryOut(BaseModel):
    referral_code: str
    referrer_username: str | None
    referred_count: int
    total_rebate_cents: int
    currency: str


class ReferralRebateOut(ORMModel):
    id: int
    referred_user_id: int
    referred_username: str
    card_claim_id: int
    amount_cents: int
    currency: str
    created_at: datetime
