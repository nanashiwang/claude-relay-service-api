from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.merchant_earning import MerchantEarning
    from app.models.share_link import ShareLink


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

    # 商户收益关联
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True, index=True, comment="收益商户ID"
    )
    merchant_earning_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchant_earnings.id"), nullable=True, comment="商户收益记录ID"
    )
    share_link_id: Mapped[int | None] = mapped_column(
        ForeignKey("share_links.id"), nullable=True, comment="来源分享链接ID"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")

    # 关系
    merchant: Mapped["Merchant"] = relationship("Merchant")
    merchant_earning: Mapped["MerchantEarning"] = relationship("MerchantEarning")
    share_link: Mapped["ShareLink"] = relationship("ShareLink", back_populates="card_claims")
