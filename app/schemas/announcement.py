from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AnnouncementOut(ORMModel):
    id: int
    title: str
    content: str
    group_qr_url: str | None
    active: bool


class AnnouncementUpdateIn(BaseModel):
    title: str | None = None
    content: str | None = None
    group_qr_url: str | None = None
    active: bool | None = None
