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
from app.models import ApiKey, CardClaim, CardCode, Product, User, Wallet
from app.models.enums import CardCodeStatus
from app.schemas.admin import AdminApiKeyOut, AdminUserOut
from app.schemas.cards import AdminCardCodeOut, ApiKeyCreateOut, ApiKeyOut
from app.schemas.wallet import AdminAdjustIn
from app.services.wallet import adjust_wallet

router = APIRouter()


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    total_users = db.execute(select(func.count()).select_from(User)).scalar_one()

    total_orders = db.execute(select(func.count()).select_from(CardClaim)).scalar_one()

    total_revenue = db.execute(select(func.coalesce(func.sum(CardClaim.cost_cents), 0))).scalar_one()

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


@router.get("/users", response_model=list[AdminUserOut])
def admin_list_users(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[AdminUserOut]:
    limit = max(1, min(int(limit or 200), 500))

    rows = db.execute(
        select(User, Wallet.balance_cents, Wallet.currency)
        .select_from(User)
        .outerjoin(Wallet, Wallet.user_id == User.id)
        .order_by(User.id.desc())
        .limit(limit)
    ).all()

    return [
        AdminUserOut(
            id=u.id,
            username=u.username,
            is_admin=u.is_admin,
            is_active=u.is_active,
            balance_cents=int(balance or 0),
            currency=str(currency or "CNY"),
            created_at=u.created_at,
        )
        for u, balance, currency in rows
    ]


@router.get("/api-keys", response_model=list[AdminApiKeyOut])
def admin_list_all_api_keys(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[AdminApiKeyOut]:
    limit = max(1, min(int(limit or 200), 500))

    keys = db.execute(select(ApiKey).order_by(ApiKey.id.desc()).limit(limit)).scalars().all()
    return [
        AdminApiKeyOut(
            id=k.id,
            user_id=k.user_id,
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=(k.revoked_at is None),
            created_at=k.created_at,
        )
        for k in keys
    ]


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
