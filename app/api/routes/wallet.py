from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Wallet, WalletTransaction
from app.schemas.wallet import WalletOut, WalletTransactionOut

router = APIRouter()


@router.get("", response_model=WalletOut)
def get_wallet(db: Session = Depends(get_db), user=Depends(get_current_user)) -> Wallet:
    wallet = db.get(Wallet, user.id)
    if wallet:
        return wallet
    wallet = Wallet(user_id=user.id)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/transactions", response_model=list[WalletTransactionOut])
def list_transactions(db: Session = Depends(get_db), user=Depends(get_current_user)) -> list[WalletTransaction]:
    return (
        db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user.id)
            .order_by(WalletTransaction.id.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
