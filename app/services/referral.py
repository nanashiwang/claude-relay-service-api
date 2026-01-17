from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Referral, ReferralRebate, RechargeRequest, User
from app.models.enums import RequestStatus, WalletTxKind
from app.services.wallet import apply_wallet_tx, lock_wallet

REBATE_PERCENT = 10


def referral_code_for_user(user_id: int) -> str:
    return f"U{user_id}"


def resolve_referrer_by_code(db: Session, code: str) -> User | None:
    normalized = (code or "").strip()
    if not normalized:
        return None

    if normalized.lower().startswith("u") and normalized[1:].isdigit():
        referrer_id = int(normalized[1:])
        return db.get(User, referrer_id)

    return db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()


def get_referrer_id(db: Session, referred_user_id: int) -> int | None:
    return db.execute(
        select(Referral.referrer_user_id).where(Referral.referred_user_id == referred_user_id)
    ).scalar_one_or_none()


def has_approved_recharge(db: Session, user_id: int) -> bool:
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
    referrer_id = get_referrer_id(db, referred_user_id)
    if not referrer_id:
        return None
    if not has_approved_recharge(db, referred_user_id):
        return None

    exists = db.execute(select(ReferralRebate.id).where(ReferralRebate.card_claim_id == card_claim_id)).first()
    if exists:
        return None

    rebate_cents = (amount_cents * REBATE_PERCENT) // 100
    if rebate_cents <= 0:
        return None

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

    rebate = ReferralRebate(
        referrer_user_id=referrer_id,
        referred_user_id=referred_user_id,
        card_claim_id=card_claim_id,
        amount_cents=rebate_cents,
        currency=currency,
    )
    db.add(rebate)
    db.flush()
    return rebate
