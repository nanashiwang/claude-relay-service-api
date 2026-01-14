from __future__ import annotations

from datetime import datetime

from sqlalchemy import BINARY, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = {"comment": "用户API Key"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="API Key ID")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, comment="用户ID")

    name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="名称备注")
    key_prefix: Mapped[str] = mapped_column(String(16), index=True, comment="Key前缀(展示用)")
    key_hash: Mapped[bytes] = mapped_column(BINARY(32), unique=True, index=True, comment="Key SHA256(32字节)")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近使用时间(UTC)"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="吊销时间(UTC)")
