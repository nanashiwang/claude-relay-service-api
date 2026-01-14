from __future__ import annotations

import enum


class ProductKind(str, enum.Enum):
    day = "day"
    usage = "usage"


class CardCodeStatus(str, enum.Enum):
    available = "available"
    claimed = "claimed"
    voided = "voided"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    canceled = "canceled"


class WalletTxKind(str, enum.Enum):
    recharge = "recharge"
    purchase = "purchase"
    refund = "refund"
    adjustment = "adjustment"

