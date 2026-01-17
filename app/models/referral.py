from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referrals_referred"),
        {"comment": "推广关系"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="推广ID")
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="推广人用户ID")
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="被推广用户ID")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
