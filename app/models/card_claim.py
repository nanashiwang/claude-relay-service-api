from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class CardClaim(Base):
    __tablename__ = "card_claims"
    __table_args__ = {"comment": "卡密提取记录"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="提取记录ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True, comment="API Key ID(可空)")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, comment="产品ID")
    card_code_id: Mapped[int] = mapped_column(ForeignKey("card_codes.id"), unique=True, comment="卡密ID(唯一)")

    cost_cents: Mapped[int] = mapped_column(Integer, comment="扣费金额(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")
