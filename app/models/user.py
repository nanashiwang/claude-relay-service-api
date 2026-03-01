from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.share_link import ShareLink


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="用户名(唯一)")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否管理员")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    is_merchant: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否商户")
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True, index=True, comment="关联商户ID"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )

    # 关系
    merchant: Mapped["Merchant"] = relationship(
        "Merchant", back_populates="user", uselist=False, foreign_keys=[merchant_id]
    )
    share_links: Mapped[list["ShareLink"]] = relationship(
        "ShareLink", back_populates="user", foreign_keys="ShareLink.user_id"
    )
