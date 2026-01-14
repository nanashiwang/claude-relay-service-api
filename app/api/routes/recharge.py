from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import RechargeRequest
from app.schemas.recharge import RechargeCreateIn, RechargeOut

router = APIRouter()


@router.post("", response_model=RechargeOut)
def create_recharge_request(
    payload: RechargeCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)
) -> RechargeRequest:
    req = RechargeRequest(
        user_id=user.id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        note=payload.note,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("", response_model=list[RechargeOut])
def list_recharge_requests(db: Session = Depends(get_db), user=Depends(get_current_user)) -> list[RechargeRequest]:
    return (
        db.execute(select(RechargeRequest).where(RechargeRequest.user_id == user.id).order_by(RechargeRequest.id.desc()))
        .scalars()
        .all()
    )

