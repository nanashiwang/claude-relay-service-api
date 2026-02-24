from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import PaymentOrderStatus


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = {"comment": "在线支付订单"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="支付订单ID")
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="商户订单号")

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, comment="产品ID")
    product_sku: Mapped[str] = mapped_column(String(64), index=True, comment="产品SKU")
    product_name: Mapped[str] = mapped_column(String(128), comment="产品名称")

    quantity: Mapped[int] = mapped_column(Integer, comment="购买数量")
    unit_price_cents: Mapped[int] = mapped_column(Integer, comment="单价(分)")
    total_price_cents: Mapped[int] = mapped_column(Integer, comment="总价(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")

    pay_type: Mapped[str] = mapped_column(String(16), comment="支付方式")
    status: Mapped[PaymentOrderStatus] = mapped_column(
        Enum(PaymentOrderStatus), default=PaymentOrderStatus.pending, index=True, comment="订单状态"
    )
    trade_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="三方订单号")

    delivery_codes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="发货卡密(换行分隔)")
    notify_payload: Mapped[str | None] = mapped_column(Text, nullable=True, comment="回调原始参数(JSON)")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付成功时间(UTC)")
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="自动发货时间(UTC)"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
