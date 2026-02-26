from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class ProductProvider(Base):
    __tablename__ = "product_providers"
    __table_args__ = {"comment": "产品供应商板块"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="供应商ID")
    key: Mapped[str] = mapped_column(String(16), unique=True, index=True, comment="标准化标识(小写)")
    name: Mapped[str] = mapped_column(String(16), unique=True, index=True, comment="显示名称")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间(UTC)",
    )
