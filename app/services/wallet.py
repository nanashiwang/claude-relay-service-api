from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import Wallet, WalletTransaction
from app.models.enums import WalletTxKind

INT32_MIN = -2_147_483_648
INT32_MAX = 2_147_483_647


def lock_wallet(db: Session, user_id: int) -> Wallet:
    wallet = (
        db.execute(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
        .scalars()
        .one_or_none()
    )
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        db.flush()
    return wallet


def apply_wallet_tx(
    *,
    db: Session,
    wallet: Wallet,
    amount_cents: int,
    kind: WalletTxKind,
    reference_type: str | None,
    reference_id: int | None,
    currency: str,
    created_by_user_id: int | None,
    note: str | None,
) -> WalletTransaction:
    if amount_cents < INT32_MIN or amount_cents > INT32_MAX:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="金额超出系统限制")
    next_balance = wallet.balance_cents + amount_cents
    if next_balance < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="余额不足")
    if next_balance < INT32_MIN or next_balance > INT32_MAX:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="余额超出系统限制")

    wallet.balance_cents = next_balance
    wallet.currency = currency
    wallet.updated_at = utcnow()

    tx = WalletTransaction(
        user_id=wallet.user_id,
        amount_cents=amount_cents,
        currency=currency,
        balance_after_cents=next_balance,
        kind=kind,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by_user_id=created_by_user_id,
        note=note,
    )
    db.add(tx)
    db.add(wallet)
    db.flush()
    return tx


def adjust_wallet(db: Session, user_id: int, amount_cents: int, admin_user_id: int, note: str | None) -> WalletTransaction:
    try:
        wallet = lock_wallet(db, user_id)
        tx = apply_wallet_tx(
            db=db,
            wallet=wallet,
            amount_cents=amount_cents,
            kind=WalletTxKind.adjustment,
            reference_type="admin_adjustment",
            reference_id=None,
            currency=wallet.currency,
            created_by_user_id=admin_user_id,
            note=note,
        )
        db.commit()
        db.refresh(tx)
        return tx
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
