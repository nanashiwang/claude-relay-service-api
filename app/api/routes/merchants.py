"""
商户管理API路由

提供商户申请、查询、统计等接口
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import Merchant, User
from app.schemas.merchant import (
    MerchantApplyIn,
    MerchantEarningOut,
    MerchantOut,
    MerchantStatsOut,
    MerchantUpdateIn,
)
from app.services.merchant import (
    activate_merchant,
    create_merchant,
    get_merchant_by_code,
    get_merchant_by_user,
    get_merchant_earnings,
    get_merchant_stats,
    suspend_merchant,
)

router = APIRouter(prefix="/merchants", tags=["商户"])


@router.post("/apply", response_model=MerchantOut)
def apply_merchant(
    data: MerchantApplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Merchant:
    """
    申请成为商户（自动通过审核）

    - **merchant_name**: 商户名称
    - **description**: 商户描述（可选）
    """
    try:
        merchant = create_merchant(
            db,
            user=user,
            merchant_name=data.merchant_name,
            description=data.description,
        )
        return merchant
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=MerchantOut)
def get_my_merchant(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Merchant:
    """获取我的商户信息"""
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="您还不是商户")

    merchant = db.get(Merchant, user.merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户信息不存在")

    return merchant


@router.patch("/me", response_model=MerchantOut)
def update_my_merchant(
    data: MerchantUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Merchant:
    """更新我的商户信息"""
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您还不是商户")

    merchant = db.get(Merchant, user.merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户信息不存在")

    if data.description is not None:
        merchant.description = data.description

    if data.platform_fee_percent is not None:
        merchant.platform_fee_percent = data.platform_fee_percent

    db.commit()
    db.refresh(merchant)

    return merchant


@router.get("/me/stats", response_model=MerchantStatsOut)
def get_my_merchant_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """获取我的商户统计数据"""
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您还不是商户")

    stats = get_merchant_stats(db, user.merchant_id)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户信息不存在")

    return stats


@router.get("/me/earnings", response_model=list[MerchantEarningOut])
def get_my_earnings(
    skip: int = 0,
    limit: int = 100,
    settled_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list:
    """获取我的收益记录"""
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您还不是商户")

    return get_merchant_earnings(db, user.merchant_id, skip=skip, limit=limit, settled_only=settled_only)


@router.get("/{merchant_id}", response_model=MerchantOut)
def get_merchant_public(
    merchant_id: int,
    db: Session = Depends(get_db),
) -> Merchant:
    """获取商户详情（公开）"""
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户不存在")

    return merchant


@router.get("/code/{merchant_code}", response_model=MerchantOut)
def get_merchant_by_code_public(
    merchant_code: str,
    db: Session = Depends(get_db),
) -> Merchant:
    """根据商户代码获取商户详情（公开）"""
    merchant = get_merchant_by_code(db, merchant_code)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户不存在")

    return merchant


@router.get("/{merchant_id}/products", response_model=list)
def get_merchant_products(
    merchant_id: int,
    db: Session = Depends(get_db),
) -> list:
    """获取商户的商品列表（公开）"""
    from sqlalchemy import select
    from app.models import Product

    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商户不存在")

    products = db.execute(
        select(Product).where(
            Product.merchant_id == merchant_id,
            Product.active == True,
        )
    ).scalars().all()

    return products


# ==================== 管理员接口 ====================

admin_router = APIRouter(prefix="/admin/merchants", tags=["商户管理"])


@admin_router.get("", response_model=list[MerchantOut])
def list_merchants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[Merchant]:
    """获取所有商户列表（管理员）"""
    from sqlalchemy import select

    return list(
        db.execute(
            select(Merchant)
            .order_by(Merchant.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )


@admin_router.post("/{merchant_id}/suspend", response_model=MerchantOut)
def suspend_merchant_admin(
    merchant_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Merchant:
    """暂停商户（管理员）"""
    try:
        return suspend_merchant(db, merchant_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@admin_router.post("/{merchant_id}/activate", response_model=MerchantOut)
def activate_merchant_admin(
    merchant_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Merchant:
    """激活商户（管理员）"""
    try:
        return activate_merchant(db, merchant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
