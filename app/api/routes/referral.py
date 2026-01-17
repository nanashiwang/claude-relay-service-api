from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Referral, ReferralRebate, User, Wallet
from app.schemas.referral import ReferralBindIn, ReferralRebateOut, ReferralSummaryOut
from app.services.referral import referral_code_for_user, resolve_referrer_by_code

router = APIRouter()


def _build_summary(db: Session, user_id: int) -> ReferralSummaryOut:
    referral_code = referral_code_for_user(user_id)

    referrer_row = (
        db.execute(
            select(User.username)
            .join(Referral, Referral.referrer_user_id == User.id)
            .where(Referral.referred_user_id == user_id)
        )
        .scalars()
        .first()
    )

    referred_count = db.execute(
        select(func.count(Referral.id)).where(Referral.referrer_user_id == user_id)
    ).scalar_one()

    total_rebate_cents = db.execute(
        select(func.coalesce(func.sum(ReferralRebate.amount_cents), 0)).where(ReferralRebate.referrer_user_id == user_id)
    ).scalar_one()

    wallet = db.get(Wallet, user_id)
    currency = wallet.currency if wallet else "CNY"

    return ReferralSummaryOut(
        referral_code=referral_code,
        referrer_username=referrer_row,
        referred_count=int(referred_count or 0),
        total_rebate_cents=int(total_rebate_cents or 0),
        currency=currency,
    )


@router.get("/me", response_model=ReferralSummaryOut)
def get_referral_summary(db: Session = Depends(get_db), user=Depends(get_current_user)) -> ReferralSummaryOut:
    return _build_summary(db, user.id)


@router.post("/bind", response_model=ReferralSummaryOut)
def bind_referrer(
    payload: ReferralBindIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ReferralSummaryOut:
    exists = db.execute(select(Referral.id).where(Referral.referred_user_id == user.id)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已绑定推广人")

    referrer = resolve_referrer_by_code(db, payload.code)
    if not referrer or not referrer.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="推广码无效")
    if referrer.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能绑定自己")

    db.add(Referral(referrer_user_id=referrer.id, referred_user_id=user.id))
    db.commit()
    return _build_summary(db, user.id)


@router.get("/rebates", response_model=list[ReferralRebateOut])
def list_referral_rebates(
    limit: int = 20,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[ReferralRebateOut]:
    limit = max(1, min(limit, 100))
    rows = (
        db.execute(
            select(ReferralRebate, User.username)
            .join(User, User.id == ReferralRebate.referred_user_id)
            .where(ReferralRebate.referrer_user_id == user.id)
            .order_by(ReferralRebate.id.desc())
            .limit(limit)
        )
        .all()
    )
    result: list[ReferralRebateOut] = []
    for rebate, referred_name in rows:
        result.append(
            ReferralRebateOut(
                id=rebate.id,
                referred_user_id=rebate.referred_user_id,
                referred_username=referred_name,
                card_claim_id=rebate.card_claim_id,
                amount_cents=rebate.amount_cents,
                currency=rebate.currency,
                created_at=rebate.created_at,
            )
        )
    return result
