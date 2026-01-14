from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import ProductKind


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"comment": "产品表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="产品ID")
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="SKU(唯一)")
    provider: Mapped[str] = mapped_column(String(16), index=True, comment="供应商(codex/gemini/claude)")
    kind: Mapped[ProductKind] = mapped_column(Enum(ProductKind), index=True, comment="类型(day/usage)")

    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="天数(kind=day)")
    usage_usd: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="面额USD(kind=usage)")

    name: Mapped[str] = mapped_column(String(128), comment="名称")

    price_cents: Mapped[int] = mapped_column(Integer, default=0, comment="价格(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否上架")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
