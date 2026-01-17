from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class ReferralRebate(Base):
    __tablename__ = "referral_rebates"
    __table_args__ = (
        UniqueConstraint("card_claim_id", name="uq_referral_rebate_claim"),
        {"comment": "推广返利记录"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="返利ID")
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="推广人用户ID")
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="被推广用户ID")
    card_claim_id: Mapped[int] = mapped_column(ForeignKey("card_claims.id"), index=True, comment="购卡记录ID")

    amount_cents: Mapped[int] = mapped_column(Integer, comment="返利金额(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
