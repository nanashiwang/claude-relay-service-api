from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = {"comment": "钱包表"}

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="用户ID(同users.id)")
    balance_cents: Mapped[int] = mapped_column(Integer, default=0, comment="余额(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
