from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models import Announcement
from app.schemas.announcement import AnnouncementOut, AnnouncementUpdateIn
from app.services.announcement import DEFAULT_ANNOUNCEMENT_CONTENT, DEFAULT_ANNOUNCEMENT_TITLE

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
WEB_DIR = ROOT_DIR / "web"
ANNOUNCEMENT_UPLOAD_DIR = WEB_DIR / "uploads" / "announcements"
MAX_QR_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_QR_CONTENT_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
ALLOWED_QR_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _get_current_announcement(db: Session) -> Announcement | None:
    return db.execute(select(Announcement).order_by(Announcement.id.asc())).scalar_one_or_none()


@router.get("", response_model=AnnouncementOut)
def get_announcement(db: Session = Depends(get_db)) -> AnnouncementOut:
    """获取当前公告（无需登录）"""
    announcement = _get_current_announcement(db)
    if announcement:
        return announcement

    return AnnouncementOut(
        id=0,
        title=DEFAULT_ANNOUNCEMENT_TITLE,
        content=DEFAULT_ANNOUNCEMENT_CONTENT,
        group_qr_url=None,
        active=True,
    )


@router.patch("", response_model=AnnouncementOut)
def update_announcement(
    payload: AnnouncementUpdateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Announcement:
    """更新公告（管理员）"""
    announcement = _get_current_announcement(db)
    if not announcement:
        announcement = Announcement(
            title=DEFAULT_ANNOUNCEMENT_TITLE,
            content=DEFAULT_ANNOUNCEMENT_CONTENT,
            active=True,
        )
        db.add(announcement)
        db.flush()

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(announcement, field, value)

    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


@router.post("/upload-qr")
def upload_announcement_qr(
    file: UploadFile = File(...),
    _: object = Depends(require_admin),
) -> dict:
    """上传公告二维码图片并返回可访问 URL"""
    if not WEB_DIR.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="web 目录不存在，无法保存文件")

    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    if ext not in ALLOWED_QR_EXTS:
        ext = ALLOWED_QR_CONTENT_TYPES.get(content_type, "")
    if ext not in ALLOWED_QR_EXTS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 PNG/JPG/WEBP 图片")

    data = file.file.read() or b""
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    if len(data) > MAX_QR_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大（最大 5MB）")

    ANNOUNCEMENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"announcement_qr_{uuid.uuid4().hex}{ext if ext != '.jpeg' else '.jpg'}"
    (ANNOUNCEMENT_UPLOAD_DIR / saved_name).write_bytes(data)

    return {"url": f"/web/uploads/announcements/{saved_name}"}
