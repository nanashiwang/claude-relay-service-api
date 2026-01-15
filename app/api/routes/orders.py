from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models import CardClaim, CardCode, Product
from app.schemas.orders import OrderOut

router = APIRouter()


@router.get("", response_model=list[OrderOut])
def list_orders(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[OrderOut]:
    limit = max(1, min(int(limit or 100), 500))

    rows = db.execute(
        select(CardClaim, Product.sku, CardCode.code)
        .join(Product, Product.id == CardClaim.product_id)
        .join(CardCode, CardCode.id == CardClaim.card_code_id)
        .order_by(CardClaim.id.desc())
        .limit(limit)
    ).all()

    return [
        OrderOut(
            id=claim.id,
            user_id=claim.user_id,
            product_sku=sku,
            price_cents=claim.cost_cents,
            currency=claim.currency,
            card_code=code,
            created_at=claim.created_at,
        )
        for claim, sku, code in rows
    ]

