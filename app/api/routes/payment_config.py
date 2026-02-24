from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import EpayConfig, PaymentConfig
from app.schemas.epay_config import EpayConfigOut, EpayConfigUpdateIn
from app.schemas.payment_config import PaymentConfigIn, PaymentConfigOut, PaymentConfigUpdateIn

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
WEB_DIR = ROOT_DIR / "web"
PAYMENT_UPLOAD_DIR = WEB_DIR / "uploads" / "payments"
MAX_QR_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_QR_CONTENT_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
ALLOWED_QR_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _normalize_optional_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _get_current_epay_config(db: Session) -> EpayConfig | None:
    return db.execute(select(EpayConfig).order_by(EpayConfig.id.desc())).scalars().first()


@router.get("", response_model=list[PaymentConfigOut])
def list_payment_configs(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[PaymentConfig]:
    """获取支付配置列表"""
    query = select(PaymentConfig)
    if active_only:
        query = query.where(PaymentConfig.active == True)
    return db.execute(query.order_by(PaymentConfig.sort_order.asc(), PaymentConfig.id.asc())).scalars().all()


@router.post("", response_model=PaymentConfigOut)
def create_payment_config(
    payload: PaymentConfigIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> PaymentConfig:
    """创建支付配置"""
    config = PaymentConfig(**payload.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.patch("/{config_id}", response_model=PaymentConfigOut)
def update_payment_config(
    config_id: int,
    payload: PaymentConfigUpdateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> PaymentConfig:
    """更新支付配置"""
    config = db.get(PaymentConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}")
def delete_payment_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    """删除支付配置"""
    config = db.get(PaymentConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    db.delete(config)
    db.commit()
    return {"message": "已删除"}


@router.get("/epay", response_model=EpayConfigOut)
def get_epay_config(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EpayConfigOut:
    config = _get_current_epay_config(db)
    if config:
        return EpayConfigOut(
            id=config.id,
            source="db",
            base_url=config.base_url,
            pid=config.pid,
            merchant_key=config.merchant_key,
            sign_type=config.sign_type,
            public_base_url=config.public_base_url,
            notify_url=config.notify_url,
            return_url=config.return_url,
            active=config.active,
        )

    return EpayConfigOut(
        id=None,
        source="env",
        base_url=(settings.epay_base_url or "").strip(),
        pid=(settings.epay_pid or "").strip(),
        merchant_key=(settings.epay_key or "").strip(),
        sign_type=(settings.epay_sign_type or "MD5").strip().upper(),
        public_base_url=_normalize_optional_text(settings.public_base_url),
        notify_url=_normalize_optional_text(settings.epay_notify_url),
        return_url=_normalize_optional_text(settings.epay_return_url),
        active=bool((settings.epay_base_url or "").strip() and (settings.epay_pid or "").strip() and (settings.epay_key or "").strip()),
    )


@router.put("/epay", response_model=EpayConfigOut)
def save_epay_config(
    payload: EpayConfigUpdateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EpayConfigOut:
    base_url = (payload.base_url or "").strip()
    pid = (payload.pid or "").strip()
    merchant_key = (payload.merchant_key or "").strip()
    sign_type = (payload.sign_type or "MD5").strip().upper()
    if not base_url or not pid or not merchant_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="网关地址、商户ID、商户密钥不能为空")

    config = _get_current_epay_config(db)
    if not config:
        config = EpayConfig(
            base_url=base_url,
            pid=pid,
            merchant_key=merchant_key,
            sign_type=sign_type,
            public_base_url=_normalize_optional_text(payload.public_base_url),
            notify_url=_normalize_optional_text(payload.notify_url),
            return_url=_normalize_optional_text(payload.return_url),
            active=payload.active,
        )
        db.add(config)
    else:
        config.base_url = base_url
        config.pid = pid
        config.merchant_key = merchant_key
        config.sign_type = sign_type
        config.public_base_url = _normalize_optional_text(payload.public_base_url)
        config.notify_url = _normalize_optional_text(payload.notify_url)
        config.return_url = _normalize_optional_text(payload.return_url)
        config.active = payload.active
        db.add(config)

    db.commit()
    db.refresh(config)
    return EpayConfigOut(
        id=config.id,
        source="db",
        base_url=config.base_url,
        pid=config.pid,
        merchant_key=config.merchant_key,
        sign_type=config.sign_type,
        public_base_url=config.public_base_url,
        notify_url=config.notify_url,
        return_url=config.return_url,
        active=config.active,
    )


@router.post("/upload-qr")
def upload_payment_qr(
    file: UploadFile = File(...),
    _: object = Depends(require_admin),
) -> dict:
    """上传收款码图片并返回可访问的 URL（存储在 web/uploads/payments 下）"""
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

    PAYMENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"payment_qr_{uuid.uuid4().hex}{ext if ext != '.jpeg' else '.jpg'}"
    (PAYMENT_UPLOAD_DIR / saved_name).write_bytes(data)

    return {"url": f"/web/uploads/payments/{saved_name}"}
