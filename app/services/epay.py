from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.epay_config import EpayConfig

SUPPORTED_EPAY_TYPES = {"alipay", "wxpay"}
SUPPORTED_EPAY_DEVICES = {"pc", "mobile", "qq", "wechat", "alipay"}


@dataclass(frozen=True)
class EpayRuntimeConfig:
    base_url: str
    pid: str
    merchant_key: str
    sign_type: str
    public_base_url: str
    notify_url: str
    return_url: str
    active: bool


def _clean(value: str | None) -> str:
    return (value or "").strip()


def get_epay_runtime_config(db: Session | None = None) -> EpayRuntimeConfig:
    if db is not None:
        row = db.execute(select(EpayConfig).order_by(EpayConfig.id.desc())).scalars().first()
        if row:
            return EpayRuntimeConfig(
                base_url=_clean(row.base_url),
                pid=_clean(row.pid),
                merchant_key=_clean(row.merchant_key),
                sign_type=_clean(row.sign_type).upper() or "MD5",
                public_base_url=_clean(row.public_base_url) or _clean(settings.public_base_url),
                notify_url=_clean(row.notify_url) or _clean(settings.epay_notify_url),
                return_url=_clean(row.return_url) or _clean(settings.epay_return_url),
                active=bool(row.active),
            )

    return EpayRuntimeConfig(
        base_url=_clean(settings.epay_base_url),
        pid=_clean(settings.epay_pid),
        merchant_key=_clean(settings.epay_key),
        sign_type=_clean(settings.epay_sign_type).upper() or "MD5",
        public_base_url=_clean(settings.public_base_url),
        notify_url=_clean(settings.epay_notify_url),
        return_url=_clean(settings.epay_return_url),
        active=True,
    )


def is_epay_configured(db: Session | None = None) -> bool:
    config = get_epay_runtime_config(db)
    return bool(config.active and config.base_url and config.pid and config.merchant_key)


def build_submit_endpoint(config: EpayRuntimeConfig | None = None) -> str:
    conf = config or get_epay_runtime_config()
    base = conf.base_url
    if not base:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未配置易支付地址")
    if base.endswith(".php"):
        return base
    return base.rstrip("/") + "/submit.php"


def normalize_pay_type(pay_type: str) -> str:
    normalized = (pay_type or "").strip().lower()
    if normalized not in SUPPORTED_EPAY_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付方式不支持")
    return normalized


def normalize_device(device: str | None) -> str:
    normalized = (device or "pc").strip().lower()
    if normalized not in SUPPORTED_EPAY_DEVICES:
        return "pc"
    return normalized


def generate_payment_order_no() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"P{now}{secrets.randbelow(1_000_000):06d}"


def money_cents_to_yuan(cents: int) -> str:
    amount = (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def money_yuan_to_cents(yuan: str) -> int:
    amount = Decimal(str(yuan)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def _signable_items(params: dict[str, object]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for k, v in params.items():
        if k in {"sign", "sign_type"}:
            continue
        if v is None:
            continue
        text = str(v)
        if text == "":
            continue
        items.append((k, text))
    items.sort(key=lambda x: x[0])
    return items


def build_sign_source(params: dict[str, object]) -> str:
    return "&".join(f"{k}={v}" for k, v in _signable_items(params))


def make_sign(params: dict[str, object], key: str) -> str:
    source = build_sign_source(params) + key
    return hashlib.md5(source.encode("utf-8")).hexdigest().lower()


def verify_sign(params: dict[str, object], key: str) -> bool:
    given = str(params.get("sign") or "").strip().lower()
    if not given:
        return False
    return make_sign(params, key) == given


def _ensure_absolute_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="回调地址必须是公网可访问的绝对URL")
    return url


def build_notify_url(config: EpayRuntimeConfig | None = None) -> str:
    conf = config or get_epay_runtime_config()
    custom = conf.notify_url
    if custom:
        return _ensure_absolute_url(custom)

    base = conf.public_base_url.rstrip("/")
    if not base:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="请配置 PUBLIC_BASE_URL 或 EPAY_NOTIFY_URL")
    return _ensure_absolute_url(f"{base}/api/v1/payments/notify/epay")


def build_return_url(order_no: str, config: EpayRuntimeConfig | None = None) -> str:
    conf = config or get_epay_runtime_config()
    custom = conf.return_url
    if custom:
        if "{order_no}" in custom:
            return _ensure_absolute_url(custom.replace("{order_no}", order_no))
        sep = "&" if "?" in custom else "?"
        return _ensure_absolute_url(f"{custom}{sep}epay_order_no={order_no}")

    base = conf.public_base_url.rstrip("/")
    if not base:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="请配置 PUBLIC_BASE_URL 或 EPAY_RETURN_URL")
    return _ensure_absolute_url(f"{base}/web/shop.html?epay_order_no={order_no}")


def build_submit_url(params: dict[str, object], config: EpayRuntimeConfig | None = None) -> str:
    endpoint = build_submit_endpoint(config)
    return endpoint + "?" + urlencode({k: str(v) for k, v in params.items() if v is not None})


def serialize_notify_payload(params: dict[str, object]) -> str:
    return json.dumps(params, ensure_ascii=False, separators=(",", ":"))
