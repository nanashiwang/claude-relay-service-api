from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class EpayConfig(Base):
    __tablename__ = "epay_configs"
    __table_args__ = {"comment": "易支付配置表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="配置ID")
    base_url: Mapped[str] = mapped_column(String(255), comment="易支付网关地址")
    pid: Mapped[str] = mapped_column(String(64), comment="商户ID")
    merchant_key: Mapped[str] = mapped_column(String(255), comment="商户密钥")
    sign_type: Mapped[str] = mapped_column(String(16), default="MD5", comment="签名类型")

    public_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="对外访问基地址")
    notify_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="异步回调地址")
    return_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="同步跳转地址")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
