from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import LinkType

if TYPE_CHECKING:
    from app.models.card_claim import CardClaim
    from app.models.merchant import Merchant
    from app.models.user import User


class ShareLink(Base):
    __tablename__ = "share_links"
    __table_args__ = {"comment": "分享链接表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="链接ID")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, comment="创建用户ID"
    )
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True, index=True, comment="关联商户ID"
    )

    # 链接信息
    link_code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, comment="链接代码"
    )
    link_type: Mapped[LinkType] = mapped_column(
        Enum(LinkType), default=LinkType.referral, comment="链接类型"
    )
    name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="链接名称"
    )

    # 产品过滤（可选，JSON格式存储产品ID列表）
    product_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="限制的产品ID列表(JSON)"
    )

    # 统计
    click_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="点击次数"
    )
    conversion_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="转化次数"
    )
    total_sales_cents: Mapped[int] = mapped_column(
        Integer, default=0, comment="累计销售额(分)"
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)"
    )

    # 关系
    user: Mapped["User"] = relationship("User")
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="share_links")
    card_claims: Mapped[list["CardClaim"]] = relationship(
        "CardClaim", back_populates="share_link"
    )
