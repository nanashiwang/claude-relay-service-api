from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card_claim import CardClaim
    from app.models.merchant import Merchant
    from app.models.product import Product


class MerchantEarning(Base):
    __tablename__ = "merchant_earnings"
    __table_args__ = {"comment": "商户收益记录表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="收益ID")
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id"), index=True, comment="商户ID"
    )

    # 关联订单
    card_claim_id: Mapped[int] = mapped_column(
        ForeignKey("card_claims.id"), index=True, comment="卡密提取记录ID"
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), comment="产品ID"
    )

    # 金额
    sales_amount_cents: Mapped[int] = mapped_column(Integer, comment="销售金额(分)")
    earnings_cents: Mapped[int] = mapped_column(Integer, comment="商户收益(分)")
    platform_fee_cents: Mapped[int] = mapped_column(
        Integer, default=0, comment="平台抽成(分)"
    )
    referral_rebate_cents: Mapped[int] = mapped_column(
        Integer, default=0, comment="推荐返利(分)"
    )

    # 状态
    is_settled: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已结算"
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="结算时间(UTC)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)"
    )

    # 关系
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="earnings")
    card_claim: Mapped["CardClaim"] = relationship("CardClaim")
    product: Mapped["Product"] = relationship("Product")
