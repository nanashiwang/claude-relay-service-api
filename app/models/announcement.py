from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = {"comment": "公告配置表"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="公告ID")
    title: Mapped[str] = mapped_column(String(128), default="平台公告", comment="公告标题")
    content: Mapped[str] = mapped_column(Text, comment="公告内容(纯文本/换行)")
    group_qr_url: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="入群二维码图片URL")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="创建时间(UTC)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间(UTC)"
    )
