from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_api_key_user, get_current_user
from app.db.session import get_db
from app.schemas.cards import ClaimBatchIn, ClaimBatchOut, ClaimIn, ClaimOut
from app.services.cards import claim_card, claim_cards

router = APIRouter()


@router.post("/claim", response_model=ClaimOut)
def claim_with_api_key(payload: ClaimIn, db: Session = Depends(get_db), api_ctx=Depends(get_api_key_user)) -> ClaimOut:
    user, api_key = api_ctx
    return claim_card(db=db, user=user, api_key_id=api_key.id, sku=payload.sku)


@router.post("/claim-by-login", response_model=ClaimOut)
def claim_by_login(payload: ClaimIn, db: Session = Depends(get_db), user=Depends(get_current_user)) -> ClaimOut:
    return claim_card(db=db, user=user, api_key_id=None, sku=payload.sku)


@router.post("/claim-batch", response_model=ClaimBatchOut)
def claim_batch_with_api_key(
    payload: ClaimBatchIn, db: Session = Depends(get_db), api_ctx=Depends(get_api_key_user)
) -> ClaimBatchOut:
    user, api_key = api_ctx
    return claim_cards(db=db, user=user, api_key_id=api_key.id, sku=payload.sku, quantity=payload.quantity)


@router.post("/claim-batch-by-login", response_model=ClaimBatchOut)
def claim_batch_by_login(payload: ClaimBatchIn, db: Session = Depends(get_db), user=Depends(get_current_user)) -> ClaimBatchOut:
    return claim_cards(db=db, user=user, api_key_id=None, sku=payload.sku, quantity=payload.quantity)
