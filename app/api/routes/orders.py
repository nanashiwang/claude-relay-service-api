from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import utcnow
from app.db.session import get_db
from app.models import CardClaim, CardCode, Product
from app.schemas.orders import OrderOut

router = APIRouter()
OrderPeriod = Literal["today", "week", "month", "all"]


def _period_start(period: OrderPeriod) -> datetime | None:
    now = utcnow().astimezone(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return day_start
    if period == "week":
        return day_start - timedelta(days=day_start.weekday())
    if period == "month":
        return day_start.replace(day=1)
    return None


def _orders_query(period: OrderPeriod):
    query = (
        select(CardClaim, Product.sku, CardCode.code)
        .join(Product, Product.id == CardClaim.product_id)
        .join(CardCode, CardCode.id == CardClaim.card_code_id)
    )
    start_at = _period_start(period)
    if start_at is not None:
        query = query.where(CardClaim.created_at >= start_at)
    return query.order_by(CardClaim.id.desc())


def _to_order_out(claim: CardClaim, sku: str, code: str) -> OrderOut:
    return OrderOut(
        id=claim.id,
        user_id=claim.user_id,
        product_sku=sku,
        price_cents=claim.cost_cents,
        currency=claim.currency,
        card_code=code,
        created_at=claim.created_at,
    )


@router.get("", response_model=list[OrderOut])
def list_orders(
    limit: int = 100,
    period: OrderPeriod = Query(default="all"),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[OrderOut]:
    limit = max(1, min(int(limit or 100), 500))
    rows = db.execute(_orders_query(period).limit(limit)).all()
    return [_to_order_out(claim, sku, code) for claim, sku, code in rows]


@router.get("/export")
def export_orders(
    period: OrderPeriod = Query(default="all"),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> StreamingResponse:
    rows = db.execute(_orders_query(period)).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "orders"
    sheet.append(
        [
            "order_id",
            "user_id",
            "product_sku",
            "price_cents",
            "price",
            "currency",
            "card_code",
            "created_at_utc",
        ]
    )

    for claim, sku, code in rows:
        created_at = ""
        if claim.created_at:
            created_at = claim.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        sheet.append(
            [
                claim.id,
                claim.user_id,
                sku,
                claim.cost_cents,
                round((claim.cost_cents or 0) / 100, 2),
                claim.currency,
                code,
                created_at,
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"orders_{period}_{timestamp}.xlsx"
    headers = {
        "Content-Disposition": f"attachment; filename={filename}; filename*=UTF-8''{quote(filename)}"
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
