"""
商户服务

提供商户相关的业务逻辑
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Merchant, User
from app.models.enums import MerchantStatus


def generate_merchant_code() -> str:
    """生成唯一的商户代码"""
    alphabet = string.ascii_lowercase + string.digits
    while True:
        code = "m_" + "".join(secrets.choice(alphabet) for _ in range(8))
        # 在实际使用时会检查唯一性
        return code


def create_merchant(
    db: Session,
    user: User,
    merchant_name: str,
    description: str | None = None,
    platform_fee_percent: int = 10,
) -> Merchant:
    """
    创建商户（自动通过审核）

    Args:
        db: 数据库会话
        user: 用户对象
        merchant_name: 商户名称
        description: 商户描述
        platform_fee_percent: 平台抽成比例

    Returns:
        创建的商户对象
    """
    # 检查用户是否已经是商户
    if user.is_merchant:
        raise ValueError("用户已经是商户")

    # 检查商户代码唯一性
    merchant_code = generate_merchant_code()
    while db.execute(
        select(Merchant.id).where(Merchant.merchant_code == merchant_code)
    ).first():
        merchant_code = generate_merchant_code()

    # 创建商户
    merchant = Merchant(
        user_id=user.id,
        merchant_name=merchant_name,
        merchant_code=merchant_code,
        description=description,
        status=MerchantStatus.approved,
        platform_fee_percent=platform_fee_percent,
    )
    db.add(merchant)
    db.flush()

    # 更新用户信息
    user.is_merchant = True
    user.merchant_id = merchant.id

    db.commit()
    db.refresh(merchant)

    return merchant


def get_merchant_by_user(db: Session, user_id: int) -> Merchant | None:
    """根据用户ID获取商户"""
    return db.execute(
        select(Merchant).where(Merchant.user_id == user_id)
    ).scalar_one_or_none()


def get_merchant_by_code(db: Session, merchant_code: str) -> Merchant | None:
    """根据商户代码获取商户"""
    return db.execute(
        select(Merchant).where(
            Merchant.merchant_code == merchant_code,
            Merchant.status == MerchantStatus.approved,
        )
    ).scalar_one_or_none()


def suspend_merchant(
    db: Session, merchant_id: int, reason: str | None = None
) -> Merchant:
    """
    暂停商户

    Args:
        db: 数据库会话
        merchant_id: 商户ID
        reason: 暂停原因

    Returns:
        更新后的商户对象
    """
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise ValueError("商户不存在")

    merchant.status = MerchantStatus.suspended
    merchant.suspended_reason = reason

    db.commit()
    db.refresh(merchant)

    return merchant


def activate_merchant(db: Session, merchant_id: int) -> Merchant:
    """
    激活商户

    Args:
        db: 数据库会话
        merchant_id: 商户ID

    Returns:
        更新后的商户对象
    """
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise ValueError("商户不存在")

    merchant.status = MerchantStatus.approved
    merchant.suspended_reason = None

    db.commit()
    db.refresh(merchant)

    return merchant


def update_merchant_stats(
    db: Session,
    merchant_id: int,
    sales_amount_cents: int,
    earnings_cents: int,
) -> None:
    """
    更新商户统计数据

    Args:
        db: 数据库会话
        merchant_id: 商户ID
        sales_amount_cents: 销售金额(分)
        earnings_cents: 收益金额(分)
    """
    merchant = db.get(Merchant, merchant_id)
    if merchant:
        merchant.total_sales_cents += sales_amount_cents
        merchant.total_earnings_cents += earnings_cents
        merchant.total_orders += 1
        db.commit()


def get_merchant_earnings(
    db: Session,
    merchant_id: int,
    skip: int = 0,
    limit: int = 100,
    settled_only: bool = False,
) -> list:
    """
    获取商户收益列表

    Args:
        db: 数据库会话
        merchant_id: 商户ID
        skip: 跳过条数
        limit: 限制条数
        settled_only: 只返回已结算

    Returns:
        收益记录列表
    """
    from app.models import MerchantEarning

    query = select(MerchantEarning).where(MerchantEarning.merchant_id == merchant_id)

    if settled_only:
        query = query.where(MerchantEarning.is_settled == True)

    query = query.order_by(MerchantEarning.created_at.desc()).offset(skip).limit(limit)

    return list(db.execute(query).scalars().all())


def get_merchant_stats(
    db: Session, merchant_id: int
) -> dict:
    """
    获取商户统计数据

    Args:
        db: 数据库会话
        merchant_id: 商户ID

    Returns:
        统计数据字典
    """
    from app.models import MerchantEarning, Product, ShareLink
    from sqlalchemy import func

    # 获取商户信息
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        return {}

    # 统计商品数量
    product_count = db.execute(
        select(func.count(Product.id)).where(Product.merchant_id == merchant_id)
    ).scalar() or 0

    # 统计分享链接数量
    share_link_count = db.execute(
        select(func.count(ShareLink.id)).where(ShareLink.merchant_id == merchant_id)
    ).scalar() or 0

    # 统计待结算收益
    unsettled_earnings = db.execute(
        select(func.sum(MerchantEarning.earnings_cents)).where(
            MerchantEarning.merchant_id == merchant_id,
            MerchantEarning.is_settled == False,
        )
    ).scalar() or 0

    # 统计已结算收益
    settled_earnings = db.execute(
        select(func.sum(MerchantEarning.earnings_cents)).where(
            MerchantEarning.merchant_id == merchant_id,
            MerchantEarning.is_settled == True,
        )
    ).scalar() or 0

    return {
        "merchant_id": merchant.id,
        "merchant_name": merchant.merchant_name,
        "merchant_code": merchant.merchant_code,
        "status": merchant.status,
        "total_sales_cents": merchant.total_sales_cents,
        "total_earnings_cents": merchant.total_earnings_cents,
        "total_orders": merchant.total_orders,
        "product_count": product_count,
        "share_link_count": share_link_count,
        "unsettled_earnings_cents": unsettled_earnings,
        "settled_earnings_cents": settled_earnings,
        "platform_fee_percent": merchant.platform_fee_percent,
    }
