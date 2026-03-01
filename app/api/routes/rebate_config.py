from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import User
from app.schemas.merchant import (
    MerchantRebateConfigUpdateIn,
    RebateConfigOut,
    RebateConfigUpdateIn,
)

router = APIRouter(prefix="/rebate-config", tags=["rebate-config"])

_default_rebate_percent = 5
_default_platform_fee_percent = 10


@router.get("", response_model=RebateConfigOut)
def get_rebate_config_public() -> dict:
    return {
        "rebate_percent": _default_rebate_percent,
        "platform_fee_percent": _default_platform_fee_percent,
    }


@router.get("/me", response_model=RebateConfigOut)
def get_my_rebate_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    platform_fee_percent = _default_platform_fee_percent

    if user.is_merchant and user.merchant_id:
        from app.models import Merchant

        merchant = db.get(Merchant, user.merchant_id)
        if merchant:
            platform_fee_percent = merchant.platform_fee_percent

    return {
        "rebate_percent": _default_rebate_percent,
        "platform_fee_percent": platform_fee_percent,
    }


@router.patch("/me", response_model=RebateConfigOut)
def update_my_rebate_config(
    data: MerchantRebateConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您还不是商户")

    from app.models import Merchant

    merchant = db.get(Merchant, user.merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户信息不存在")

    merchant.platform_fee_percent = data.platform_fee_percent
    db.commit()

    return {
        "rebate_percent": _default_rebate_percent,
        "platform_fee_percent": merchant.platform_fee_percent,
    }


admin_router = APIRouter(prefix="/admin/rebate-config", tags=["rebate-config-admin"])


@admin_router.get("", response_model=RebateConfigOut)
def get_admin_rebate_config(
    _admin: User = Depends(require_admin),
) -> dict:
    return {
        "rebate_percent": _default_rebate_percent,
        "platform_fee_percent": _default_platform_fee_percent,
    }


@admin_router.patch("", response_model=RebateConfigOut)
def update_rebate_config_admin(
    data: RebateConfigUpdateIn,
    _admin: User = Depends(require_admin),
) -> dict:
    global _default_rebate_percent, _default_platform_fee_percent

    _default_rebate_percent = data.rebate_percent
    _default_platform_fee_percent = data.platform_fee_percent

    return {
        "rebate_percent": _default_rebate_percent,
        "platform_fee_percent": _default_platform_fee_percent,
    }
