from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import RequestStatus


class RefundRequest(Base):
    __tablename__ = "refund_requests"
    __table_args__ = {"comment": "退款申请"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="退款申请ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")

    amount_cents: Mapped[int] = mapped_column(Integer, comment="退款金额(分)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="退款原因/说明")

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.pending, index=True, comment="状态(pending/approved/rejected/canceled)"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审核时间(UTC)")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="审核人ID(管理员)"
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审核备注")
