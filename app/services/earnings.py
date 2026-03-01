"""
收益结算服务

提供商户收益计算和结算的业务逻辑
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import Merchant, MerchantEarning

if TYPE_CHECKING:
    from app.models import CardClaim, Product, ShareLink


def calculate_earnings(
    sales_amount_cents: int,
    platform_fee_percent: int,
    rebate_percent: int = 0,
) -> dict:
    """
    计算收益分配

    Args:
        sales_amount_cents: 销售金额(分)
        platform_fee_percent: 平台抽成比例(0-100)
        rebate_percent: 推荐返利比例(0-100)

    Returns:
        收益分配字典
    """
    platform_fee = sales_amount_cents * platform_fee_percent // 100
    rebate_amount = sales_amount_cents * rebate_percent // 100
    merchant_earnings = sales_amount_cents - platform_fee - rebate_amount

    return {
        "sales_amount_cents": sales_amount_cents,
        "platform_fee_cents": platform_fee,
        "rebate_cents": rebate_amount,
        "merchant_earnings_cents": max(0, merchant_earnings),
    }


def create_merchant_earning(
    db: Session,
    card_claim: CardClaim,
    product: Product,
    share_link: ShareLink | None = None,
    rebate_percent: int = 0,
) -> MerchantEarning | None:
    """
    创建商户收益记录

    Args:
        db: 数据库会话
        card_claim: 卡密提取记录
        product: 产品
        share_link: 分享链接
        rebate_percent: 推荐返利比例

    Returns:
        创建的收益记录，如果没有商户则返回None
    """
    # 检查产品是否属于商户
    if not product.merchant_id:
        return None

    merchant = db.get(Merchant, product.merchant_id)
    if not merchant or merchant.status != "approved":
        return None

    # 计算收益分配
    earnings = calculate_earnings(
        sales_amount_cents=card_claim.cost_cents,
        platform_fee_percent=merchant.platform_fee_percent,
        rebate_percent=rebate_percent,
    )

    # 创建收益记录
    merchant_earning = MerchantEarning(
        merchant_id=merchant.id,
        card_claim_id=card_claim.id,
        product_id=product.id,
        sales_amount_cents=earnings["sales_amount_cents"],
        earnings_cents=earnings["merchant_earnings_cents"],
        platform_fee_cents=earnings["platform_fee_cents"],
        referral_rebate_cents=earnings["rebate_cents"],
    )
    db.add(merchant_earning)
    db.flush()

    # 更新卡密提取记录
    card_claim.merchant_id = merchant.id
    card_claim.merchant_earning_id = merchant_earning.id
    if share_link:
        card_claim.share_link_id = share_link.id

    db.commit()

    # 更新商户统计数据
    from app.services.merchant import update_merchant_stats

    update_merchant_stats(
        db,
        merchant.id,
        earnings["sales_amount_cents"],
        earnings["merchant_earnings_cents"],
    )

    # 更新分享链接统计
    if share_link:
        from app.services.share_links import record_conversion

        record_conversion(db, share_link.id, earnings["sales_amount_cents"])

    return merchant_earning


def settle_earnings(
    db: Session,
    merchant_id: int,
    earning_ids: list[int] | None = None,
) -> int:
    """
    结算收益

    Args:
        db: 数据库会话
        merchant_id: 商户ID
        earning_ids: 要结算的收益ID列表，None表示结算所有未结算

    Returns:
        结算的收益记录数量
    """
    from sqlalchemy import select

    query = select(MerchantEarning).where(
        MerchantEarning.merchant_id == merchant_id,
        MerchantEarning.is_settled == False,
    )

    if earning_ids:
        query = query.where(MerchantEarning.id.in_(earning_ids))

    earnings = list(db.execute(query).scalars().all())
    now = datetime.utcnow()

    for earning in earnings:
        earning.is_settled = True
        earning.settled_at = now

    db.commit()

    return len(earnings)


def get_unsettled_earnings(db: Session, merchant_id: int) -> list[MerchantEarning]:
    """
    获取未结算的收益

    Args:
        db: 数据库会话
        merchant_id: 商户ID

    Returns:
        未结算收益列表
    """
    from sqlalchemy import select

    return list(
        db.execute(
            select(MerchantEarning)
            .where(
                MerchantEarning.merchant_id == merchant_id,
                MerchantEarning.is_settled == False,
            )
            .order_by(MerchantEarning.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_total_unsettled(db: Session, merchant_id: int) -> int:
    """
    获取未结算总金额

    Args:
        db: 数据库会话
        merchant_id: 商户ID

    Returns:
        未结算金额(分)
    """
    from sqlalchemy import select, func

    result = db.execute(
        select(func.sum(MerchantEarning.earnings_cents)).where(
            MerchantEarning.merchant_id == merchant_id,
            MerchantEarning.is_settled == False,
        )
    ).scalar()

    return result or 0
