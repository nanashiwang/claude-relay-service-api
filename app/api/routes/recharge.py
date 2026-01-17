from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import RechargeRequest
from app.schemas.recharge import RechargeCreateIn, RechargeOut
from app.services.notification import notify_recharge_event

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
WEB_DIR = ROOT_DIR / "web"
RECHARGE_UPLOAD_DIR = WEB_DIR / "uploads" / "recharges"
MAX_PROOF_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_PROOF_CONTENT_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
ALLOWED_PROOF_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@router.post("", response_model=RechargeOut)
def create_recharge_request(
    payload: RechargeCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)
) -> RechargeRequest:
    req = RechargeRequest(
        user_id=user.id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        payment_proof_url=payload.payment_proof_url,
        note=payload.note,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    notify_recharge_event(db, req, event="created", requester_name=user.username)
    return req


@router.get("", response_model=list[RechargeOut])
def list_recharge_requests(db: Session = Depends(get_db), user=Depends(get_current_user)) -> list[RechargeRequest]:
    return (
        db.execute(select(RechargeRequest).where(RechargeRequest.user_id == user.id).order_by(RechargeRequest.id.desc()))
        .scalars()
        .all()
    )


@router.post("/upload-proof")
def upload_recharge_proof(
    file: UploadFile = File(...),
    _: object = Depends(get_current_user),
) -> dict:
    """上传充值截图并返回可访问 URL"""
    if not WEB_DIR.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="web 目录不存在，无法保存文件")

    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    if ext not in ALLOWED_PROOF_EXTS:
        ext = ALLOWED_PROOF_CONTENT_TYPES.get(content_type, "")
    if ext not in ALLOWED_PROOF_EXTS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持PNG/JPG/WEBP 图片")

    data = file.file.read() or b""
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    if len(data) > MAX_PROOF_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大（最大5MB）")

    RECHARGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"recharge_proof_{uuid.uuid4().hex}{ext if ext != '.jpeg' else '.jpg'}"
    (RECHARGE_UPLOAD_DIR / saved_name).write_bytes(data)

    return {"url": f"/web/uploads/recharges/{saved_name}"}
