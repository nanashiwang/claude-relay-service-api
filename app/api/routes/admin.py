from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import api_key_prefix, generate_api_key, hash_api_key, utcnow
from app.db.session import get_db
from app.models import ApiKey, CardClaim, CardCode, Product, RechargeRequest, RefundRequest, User
from app.models.enums import CardCodeStatus, RequestStatus
from app.schemas.cards import AdminCardCodeOut, ApiKeyCreateOut, ApiKeyOut
from app.schemas.recharge import AdminReviewIn, RechargeOut
from app.schemas.refund import RefundOut
from app.schemas.wallet import AdminAdjustIn
from app.services.requests import approve_recharge, approve_refund, reject_recharge, reject_refund
from app.services.wallet import adjust_wallet

router = APIRouter()


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    total_users = db.execute(select(func.count()).select_from(User)).scalar_one()

    total_orders = db.execute(select(func.count()).select_from(CardClaim)).scalar_one()

    approved_recharge = db.execute(
        select(func.coalesce(func.sum(RechargeRequest.amount_cents), 0)).where(RechargeRequest.status == RequestStatus.approved)
    ).scalar_one()
    approved_refund = db.execute(
        select(func.coalesce(func.sum(RefundRequest.amount_cents), 0)).where(RefundRequest.status == RequestStatus.approved)
    ).scalar_one()
    total_revenue = int(approved_recharge or 0) - int(approved_refund or 0)

    total_cards = db.execute(
        select(func.count()).select_from(CardCode).where(CardCode.status == CardCodeStatus.available)
    ).scalar_one()

    return {
        "total_users": int(total_users or 0),
        "total_orders": int(total_orders or 0),
        "total_revenue": int(total_revenue),
        "total_cards": int(total_cards or 0),
    }


@router.post("/users/{user_id}/api-keys", response_model=ApiKeyCreateOut)
def admin_create_api_key(
    user_id: int,
    name: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> ApiKeyCreateOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    raw_key = generate_api_key()
    rec = ApiKey(user_id=user_id, name=name, key_prefix=api_key_prefix(raw_key), key_hash=hash_api_key(raw_key))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ApiKeyCreateOut(id=rec.id, user_id=rec.user_id, name=rec.name, key_prefix=rec.key_prefix, api_key=raw_key)


@router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyOut])
def admin_list_api_keys(
    user_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[ApiKey]:
    return db.execute(select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.id.desc())).scalars().all()


@router.post("/api-keys/{api_key_id}/revoke")
def admin_revoke_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    rec = db.get(ApiKey, api_key_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
    if rec.revoked_at:
        return {"status": "already_revoked"}
    rec.revoked_at = utcnow()
    db.add(rec)
    db.commit()
    return {"status": "revoked"}


@router.post("/recharge-requests/{request_id}/approve", response_model=RechargeOut)
def admin_approve_recharge(
    request_id: int,
    payload: AdminReviewIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> RechargeRequest:
    return approve_recharge(db=db, request_id=request_id, admin_user_id=admin.id, note=payload.note)


@router.post("/recharge-requests/{request_id}/reject", response_model=RechargeOut)
def admin_reject_recharge(
    request_id: int,
    payload: AdminReviewIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> RechargeRequest:
    return reject_recharge(db=db, request_id=request_id, admin_user_id=admin.id, note=payload.note)


@router.post("/refund-requests/{request_id}/approve", response_model=RefundOut)
def admin_approve_refund(
    request_id: int,
    payload: AdminReviewIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> RefundRequest:
    return approve_refund(db=db, request_id=request_id, admin_user_id=admin.id, note=payload.note)


@router.post("/refund-requests/{request_id}/reject", response_model=RefundOut)
def admin_reject_refund(
    request_id: int,
    payload: AdminReviewIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> RefundRequest:
    return reject_refund(db=db, request_id=request_id, admin_user_id=admin.id, note=payload.note)


@router.post("/wallets/{user_id}/adjust")
def admin_adjust_user_wallet(
    user_id: int,
    payload: AdminAdjustIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> dict:
    tx = adjust_wallet(db=db, user_id=user_id, amount_cents=payload.amount_cents, admin_user_id=admin.id, note=payload.note)
    return {"transaction_id": tx.id, "balance_after_cents": tx.balance_after_cents}


@router.post("/cards/import")
def import_cards(
    product_sku: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
) -> dict:
    product = db.execute(select(Product).where(Product.sku == product_sku)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    content = (file.file.read() or b"").decode("utf-8", errors="ignore")
    lines = [line.strip() for line in content.splitlines()]
    codes = [line for line in lines if line]
    if not codes:
        return {"total": 0, "inserted": 0, "skipped": 0}

    inserted = 0
    skipped = 0
    for code in codes:
        code_hash = hashlib.sha256(code.encode("utf-8")).digest()
        try:
            with db.begin_nested():
                db.add(
                    CardCode(
                        product_id=product.id,
                        code=code,
                        code_sha256=code_hash,
                        status=CardCodeStatus.available,
                        imported_by_user_id=admin.id,
                    )
                )
                db.flush()
            inserted += 1
        except IntegrityError:
            skipped += 1

    db.commit()
    return {"total": len(codes), "inserted": inserted, "skipped": skipped}


@router.get("/recharge-requests", response_model=list[RechargeOut])
def admin_list_recharge_requests(
    status: RequestStatus | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[RechargeRequest]:
    stmt = select(RechargeRequest).order_by(RechargeRequest.id.desc())
    if status:
        stmt = stmt.where(RechargeRequest.status == status)
    return db.execute(stmt).scalars().all()


@router.get("/refund-requests", response_model=list[RefundOut])
def admin_list_refund_requests(
    status: RequestStatus | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[RefundRequest]:
    stmt = select(RefundRequest).order_by(RefundRequest.id.desc())
    if status:
        stmt = stmt.where(RefundRequest.status == status)
    return db.execute(stmt).scalars().all()


@router.get("/inventory/{product_sku}")
def admin_inventory(
    product_sku: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    product = db.execute(select(Product).where(Product.sku == product_sku)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    rows = db.execute(
        select(CardCode.status, func.count())
        .where(CardCode.product_id == product.id)
        .group_by(CardCode.status)
    ).all()

    counts = {status.value: int(cnt) for status, cnt in rows}
    available = counts.get(CardCodeStatus.available.value, 0)
    claimed = counts.get(CardCodeStatus.claimed.value, 0)
    voided = counts.get(CardCodeStatus.voided.value, 0)
    total = available + claimed + voided

    return {
        "product_id": product.id,
        "sku": product.sku,
        "total": total,
        "available": available,
        "claimed": claimed,
        "voided": voided,
    }


@router.get("/cards", response_model=list[AdminCardCodeOut])
def admin_list_cards(
    product_sku: str | None = None,
    status: CardCodeStatus | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[AdminCardCodeOut]:
    limit = max(1, min(int(limit or 100), 500))

    stmt = (
        select(CardCode, Product.sku, CardClaim.id)
        .join(Product, Product.id == CardCode.product_id)
        .outerjoin(CardClaim, CardClaim.card_code_id == CardCode.id)
        .order_by(CardCode.id.desc())
        .limit(limit)
    )
    if product_sku:
        stmt = stmt.where(Product.sku == product_sku)
    if status:
        stmt = stmt.where(CardCode.status == status)

    rows = db.execute(stmt).all()
    return [
        AdminCardCodeOut(
            id=card.id,
            product_sku=sku,
            status=card.status,
            code=card.code,
            order_id=claim_id,
            created_at=card.imported_at,
        )
        for card, sku, claim_id in rows
    ]
