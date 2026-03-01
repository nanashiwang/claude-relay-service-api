from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Merchant, Referral, ReferralRebate, RechargeRequest, User
from app.models.enums import RequestStatus, WalletTxKind
from app.services.wallet import apply_wallet_tx, lock_wallet

# 默认返利比例（可被全局配置覆盖）
DEFAULT_REBATE_PERCENT = 5


def get_rebate_percent(db: Session) -> int:
    """
    获取当前返利比例

    Args:
        db: 数据库会话

    Returns:
        返利比例(0-100)
    """
    # TODO: 从全局配置表读取，目前返回默认值
    return DEFAULT_REBATE_PERCENT


def referral_code_for_user(user_id: int) -> str:
    return f"U{user_id}"


def resolve_referrer_by_code(db: Session, code: str) -> User | None:
    """通过推荐码解析推荐人"""
    normalized = (code or "").strip()
    if not normalized:
        return None

    # 支持分享链接代码
    from app.models import ShareLink

    share_link = db.execute(
        select(ShareLink).where(ShareLink.link_code == normalized, ShareLink.active == True)
    ).scalar_one_or_none()

    if share_link:
        return db.get(User, share_link.user_id)

    # 支持用户ID格式 (U123)
    if normalized.lower().startswith("u") and normalized[1:].isdigit():
        referrer_id = int(normalized[1:])
        return db.get(User, referrer_id)

    # 支持用户名
    return db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()


def get_referrer_id(db: Session, referred_user_id: int) -> int | None:
    """获取用户的推荐人ID"""
    return db.execute(
        select(Referral.referrer_user_id).where(Referral.referred_user_id == referred_user_id)
    ).scalar_one_or_none()


def has_approved_recharge(db: Session, user_id: int) -> bool:
    """检查用户是否有已通过的充值"""
    return (
        db.execute(
            select(RechargeRequest.id).where(
                RechargeRequest.user_id == user_id, RechargeRequest.status == RequestStatus.approved
            )
        ).first()
        is not None
    )


def try_apply_referral_rebate(
    db: Session,
    *,
    referred_user_id: int,
    card_claim_id: int,
    amount_cents: int,
    currency: str,
) -> ReferralRebate | None:
    """
    尝试应用推荐返利

    Args:
        db: 数据库会话
        referred_user_id: 被推荐用户ID
        card_claim_id: 卡密提取记录ID
        amount_cents: 金额(分)
        currency: 币种

    Returns:
        创建的返利记录，如果不满足条件则返回None
    """
    referrer_id = get_referrer_id(db, referred_user_id)
    if not referrer_id:
        return None

    # 检查被推荐人是否有已通过的充值（防止刷单）
    if not has_approved_recharge(db, referred_user_id):
        return None

    # 检查是否已经返利
    exists = db.execute(select(ReferralRebate.id).where(ReferralRebate.card_claim_id == card_claim_id)).first()
    if exists:
        return None

    # 获取返利比例
    rebate_percent = get_rebate_percent(db)
    rebate_cents = (amount_cents * rebate_percent) // 100
    if rebate_cents <= 0:
        return None

    # 获取推荐人信息（检查是否是商户）
    referrer = db.get(User, referrer_id)
    if not referrer:
        return None

    merchant_id = None
    if referrer.is_merchant and referrer.merchant_id:
        merchant_id = referrer.merchant_id

    # 给推荐人钱包增加余额
    wallet = lock_wallet(db, referrer_id)
    apply_wallet_tx(
        db=db,
        wallet=wallet,
        amount_cents=rebate_cents,
        kind=WalletTxKind.adjustment,
        reference_type="referral_rebate",
        reference_id=card_claim_id,
        currency=currency,
        created_by_user_id=None,
        note=f"rebate:referrer:{referrer_id}:referred:{referred_user_id}",
    )

    # 创建返利记录
    rebate = ReferralRebate(
        referrer_user_id=referrer_id,
        referred_user_id=referred_user_id,
        card_claim_id=card_claim_id,
        amount_cents=rebate_cents,
        currency=currency,
        merchant_id=merchant_id,
    )
    db.add(rebate)
    db.flush()

    return rebate


def try_bind_referrer(
    db: Session,
    user_id: int,
    referral_code: str,
) -> bool:
    """
    尝试绑定推荐人

    Args:
        db: 数据库会话
        user_id: 用户ID
        referral_code: 推荐码

    Returns:
        是否绑定成功
    """
    # 检查是否已有推荐人
    existing = get_referrer_id(db, user_id)
    if existing:
        return False

    # 解析推荐人
    referrer = resolve_referrer_by_code(db, referral_code)
    if not referrer:
        return False

    # 不能绑定自己
    if referrer.id == user_id:
        return False

    # 创建推荐关系
    referral = Referral(
        referrer_user_id=referrer.id,
        referred_user_id=user_id,
    )
    db.add(referral)
    db.commit()

    return True
