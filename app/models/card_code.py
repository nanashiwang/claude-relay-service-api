from __future__ import annotations

from datetime import datetime

from sqlalchemy import BINARY, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import CardCodeStatus


class CardCode(Base):
    __tablename__ = "card_codes"
    __table_args__ = {"comment": "卡密库存"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="卡密ID")
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, comment="产品ID")

    code: Mapped[str] = mapped_column(Text, comment="卡密内容")
    code_sha256: Mapped[bytes] = mapped_column(BINARY(32), unique=True, index=True, comment="卡密SHA256(去重)")

    status: Mapped[CardCodeStatus] = mapped_column(
        Enum(CardCodeStatus), default=CardCodeStatus.available, index=True, comment="状态(available/claimed/voided)"
    )

    imported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="导入人ID(管理员)")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="导入时间(UTC)")

    claimed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="提取用户ID")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="提取时间(UTC)")
