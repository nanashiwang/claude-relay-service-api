from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import RequestStatus


class RechargeRequest(Base):
    __tablename__ = "recharge_requests"
    __table_args__ = {"comment": "充值申请"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="充值申请ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")

    amount_cents: Mapped[int] = mapped_column(Integer, comment="充值金额(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")

    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="支付方式")
    payment_reference: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="支付参考号/流水")
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.pending, index=True, comment="状态(pending/approved/rejected/canceled)"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审核时间(UTC)")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="审核人ID(管理员)"
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审核备注")
