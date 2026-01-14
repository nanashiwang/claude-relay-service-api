from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import RefundRequest, Wallet
from app.schemas.refund import RefundCreateIn, RefundOut

router = APIRouter()


@router.post("", response_model=RefundOut)
def create_refund_request(
    payload: RefundCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)
) -> RefundRequest:
    wallet = db.get(Wallet, user.id)
    if not wallet or wallet.balance_cents < payload.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="余额不足，无法发起退款申请")

    req = RefundRequest(
        user_id=user.id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        reason=payload.reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("", response_model=list[RefundOut])
def list_refund_requests(db: Session = Depends(get_db), user=Depends(get_current_user)) -> list[RefundRequest]:
    return (
        db.execute(select(RefundRequest).where(RefundRequest.user_id == user.id).order_by(RefundRequest.id.desc()))
        .scalars()
        .all()
    )

