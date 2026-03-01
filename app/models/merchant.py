from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import MerchantStatus

if TYPE_CHECKING:
    from app.models.merchant_earning import MerchantEarning
    from app.models.product import Product
    from app.models.share_link import ShareLink
    from app.models.user import User


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = {"comment": "商户表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="商户ID")
    user_id: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, comment="关联用户ID"
    )

    # 商户基本信息
    merchant_name: Mapped[str] = mapped_column(String(128), comment="商户名称")
    merchant_code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, comment="商户代码(用于链接)"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="商户描述")

    # 状态
    status: Mapped[MerchantStatus] = mapped_column(
        Enum(MerchantStatus), default=MerchantStatus.approved, index=True, comment="状态"
    )
    suspended_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="暂停原因"
    )

    # 返利配置
    platform_fee_percent: Mapped[int] = mapped_column(
        Integer, default=10, comment="平台抽成比例(0-100)"
    )

    # 统计
    total_sales_cents: Mapped[int] = mapped_column(
        Integer, default=0, comment="累计销售额(分)"
    )
    total_earnings_cents: Mapped[int] = mapped_column(
        Integer, default=0, comment="累计收益(分)"
    )
    total_orders: Mapped[int] = mapped_column(Integer, default=0, comment="累计订单数")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="merchant", uselist=False)
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="merchant", cascade="all, delete-orphan"
    )
    earnings: Mapped[list["MerchantEarning"]] = relationship(
        "MerchantEarning", back_populates="merchant", cascade="all, delete-orphan"
    )
    share_links: Mapped[list["ShareLink"]] = relationship(
        "ShareLink", back_populates="merchant", cascade="all, delete-orphan"
    )
