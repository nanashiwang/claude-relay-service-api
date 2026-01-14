from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import WalletTxKind


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint("reference_type", "reference_id", name="uq_wallet_tx_reference"),
        {"comment": "钱包流水"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="流水ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")

    amount_cents: Mapped[int] = mapped_column(Integer, comment="变动金额(分，可负)")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种(ISO-4217)")
    balance_after_cents: Mapped[int] = mapped_column(Integer, comment="变动后余额(分)")

    kind: Mapped[WalletTxKind] = mapped_column(Enum(WalletTxKind), comment="类型(recharge/purchase/refund/adjustment)")
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="关联类型")
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联ID")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, comment="创建时间(UTC)")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="操作人ID(管理员)"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
