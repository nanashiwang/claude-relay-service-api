from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import WalletTxKind
from app.schemas.common import ORMModel


class WalletOut(ORMModel):
    user_id: int
    balance_cents: int
    currency: str


class WalletTransactionOut(ORMModel):
    id: int
    amount_cents: int
    currency: str
    balance_after_cents: int
    kind: WalletTxKind
    reference_type: str | None
    reference_id: int | None
    created_at: datetime
    note: str | None


class AdminAdjustIn(BaseModel):
    amount_cents: int
    note: str | None = None
