from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class ProductTierDiscount(Base):
    __tablename__ = "product_tier_discounts"
    __table_args__ = (
        UniqueConstraint("product_id", "min_quantity", name="uq_product_tier_discounts_product_qty"),
        {"comment": "产品阶梯折扣"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="主键ID")
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, comment="产品ID")
    min_quantity: Mapped[int] = mapped_column(Integer, comment="最小购买数量(含)")
    discount_percent: Mapped[int] = mapped_column(Integer, comment="折扣百分比(1-99)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")

    product: Mapped["Product"] = relationship("Product", back_populates="tier_discounts")
