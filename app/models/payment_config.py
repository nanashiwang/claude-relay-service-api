from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class PaymentConfig(Base):
    """支付配置表 - 管理员可配置的收款方式"""
    __tablename__ = "payment_configs"
    __table_args__ = {"comment": "支付配置表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="配置ID")
    name: Mapped[str] = mapped_column(String(64), comment="支付方式名称(如: 支付宝/微信/银���卡)")
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="图标类型(alipay/wechat/bank)")
    account_info: Mapped[str] = mapped_column(Text, comment="收款账号信息(支持HTML)")
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True, comment="支付说明(支持HTML)")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示顺序(数字越小越靠前)")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
