from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import utcnow
from app.db.session import get_db
from app.models import CardCode, PaymentOrder, Product, User
from app.models.enums import CardCodeStatus, PaymentOrderStatus
from app.schemas.payment_order import PaymentOrderCreateIn, PaymentOrderCreateOut, PaymentOrderOut
from app.services.cards import deliver_paid_order, resolve_price_cents
from app.services.epay import (
    build_notify_url,
    build_return_url,
    build_submit_url,
    generate_payment_order_no,
    get_epay_runtime_config,
    is_epay_configured,
    make_sign,
    money_cents_to_yuan,
    money_yuan_to_cents,
    normalize_device,
    normalize_pay_type,
    serialize_notify_payload,
    verify_sign,
)

router = APIRouter()


def _parse_card_codes(delivery_codes: str | None) -> list[str]:
    if not delivery_codes:
        return []
    return [line for line in (s.strip() for s in delivery_codes.splitlines()) if line]


def _to_out(order: PaymentOrder) -> PaymentOrderOut:
    return PaymentOrderOut(
        order_no=order.order_no,
        sku=order.product_sku,
        quantity=order.quantity,
        unit_price_cents=order.unit_price_cents,
        total_price_cents=order.total_price_cents,
        currency=order.currency,
        pay_type=order.pay_type,
        status=order.status,
        trade_no=order.trade_no,
        card_codes=_parse_card_codes(order.delivery_codes),
        failure_reason=order.failure_reason,
        created_at=order.created_at,
        paid_at=order.paid_at,
        delivered_at=order.delivered_at,
    )


def _next_order_no(db: Session) -> str:
    for _ in range(8):
        order_no = generate_payment_order_no()
        exists = db.execute(select(PaymentOrder.id).where(PaymentOrder.order_no == order_no)).first()
        if not exists:
            return order_no
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成订单号失败，请稍后重试")


def _extract_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.client.host if request.client else "").strip() or "127.0.0.1"


@router.post("/orders", response_model=PaymentOrderCreateOut)
def create_payment_order(
    payload: PaymentOrderCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> PaymentOrderCreateOut:
    epay_config = get_epay_runtime_config(db)
    if not is_epay_configured(db):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="在线支付未配置")

    pay_type = normalize_pay_type(payload.pay_type)
    device = normalize_device(payload.device)

    product = db.execute(select(Product).where(Product.sku == payload.sku, Product.active.is_(True))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在或已下架")

    unit_price_cents = resolve_price_cents(product, quantity=payload.quantity)
    if unit_price_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="产品未设置价格")
    total_price_cents = unit_price_cents * payload.quantity

    available = db.execute(
        select(func.count()).select_from(CardCode).where(
            CardCode.product_id == product.id, CardCode.status == CardCodeStatus.available
        )
    ).scalar_one()
    if int(available or 0) < payload.quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="库存不足")

    order_no = _next_order_no(db)
    notify_url = build_notify_url(epay_config)
    return_url = build_return_url(order_no, epay_config)
    params: dict[str, object] = {
        "pid": epay_config.pid,
        "type": pay_type,
        "out_trade_no": order_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": product.name,
        "money": money_cents_to_yuan(total_price_cents),
        "sitename": "Card Platform",
        "param": f"user_id={user.id};sku={product.sku};qty={payload.quantity}",
        "clientip": _extract_client_ip(request),
        "device": device,
    }
    params["sign"] = make_sign(params, epay_config.merchant_key)
    params["sign_type"] = epay_config.sign_type
    pay_url = build_submit_url(params, epay_config)

    order = PaymentOrder(
        order_no=order_no,
        user_id=user.id,
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        quantity=payload.quantity,
        unit_price_cents=unit_price_cents,
        total_price_cents=total_price_cents,
        currency=product.currency,
        pay_type=pay_type,
        status=PaymentOrderStatus.pending,
    )
    db.add(order)
    db.commit()

    return PaymentOrderCreateOut(
        order_no=order.order_no,
        sku=order.product_sku,
        quantity=order.quantity,
        total_price_cents=order.total_price_cents,
        currency=order.currency,
        pay_type=order.pay_type,
        pay_url=pay_url,
    )


@router.get("/orders/{order_no}", response_model=PaymentOrderOut)
def get_payment_order(
    order_no: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> PaymentOrderOut:
    order = db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no)).scalar_one_or_none()
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return _to_out(order)


@router.get("/orders", response_model=list[PaymentOrderOut])
def list_payment_orders(
    limit: int = 20,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[PaymentOrderOut]:
    limit = max(1, min(int(limit or 20), 100))
    rows = (
        db.execute(
            select(PaymentOrder)
            .where(PaymentOrder.user_id == user.id)
            .order_by(PaymentOrder.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_to_out(order) for order in rows]


@router.api_route("/notify/epay", methods=["GET", "POST"], include_in_schema=False)
async def epay_notify(
    request: Request,
    db: Session = Depends(get_db),
):
    epay_config = get_epay_runtime_config(db)
    if not is_epay_configured(db):
        return PlainTextResponse("fail")

    params: dict[str, object] = dict(request.query_params)
    if request.method.upper() == "POST":
        try:
            form = await request.form()
            for k, v in form.items():
                params[k] = v
        except Exception:
            pass

    out_trade_no = str(params.get("out_trade_no") or "").strip()
    trade_status = str(params.get("trade_status") or "").strip()
    pid = str(params.get("pid") or "").strip()
    if not out_trade_no or not trade_status or not pid:
        return PlainTextResponse("fail")
    if pid != epay_config.pid:
        return PlainTextResponse("fail")
    if not verify_sign(params, epay_config.merchant_key):
        return PlainTextResponse("fail")

    if trade_status != "TRADE_SUCCESS":
        return PlainTextResponse("success")

    try:
        order = (
            db.execute(
                select(PaymentOrder).where(PaymentOrder.order_no == out_trade_no).with_for_update()
            )
            .scalars()
            .one_or_none()
        )
        if not order:
            db.rollback()
            return PlainTextResponse("fail")

        paid_cents = money_yuan_to_cents(str(params.get("money") or "0"))
        if paid_cents != order.total_price_cents:
            db.rollback()
            return PlainTextResponse("fail")

        order.trade_no = str(params.get("trade_no") or "").strip() or order.trade_no
        order.notify_payload = serialize_notify_payload(params)
        if not order.paid_at:
            order.paid_at = utcnow()

        if order.status != PaymentOrderStatus.delivered:
            order.status = PaymentOrderStatus.paid
            user = db.get(User, order.user_id)
            product = db.get(Product, order.product_id)
            if not user or not product:
                order.status = PaymentOrderStatus.failed
                order.failure_reason = "用户或产品不存在"
            else:
                try:
                    _, codes = deliver_paid_order(
                        db=db,
                        user=user,
                        product=product,
                        quantity=order.quantity,
                        unit_price_cents=order.unit_price_cents,
                    )
                    order.delivery_codes = "\n".join([code.code for code in codes])
                    order.delivered_at = utcnow()
                    order.status = PaymentOrderStatus.delivered
                    order.failure_reason = None
                except HTTPException as exc:
                    order.status = PaymentOrderStatus.failed
                    order.failure_reason = str(exc.detail)

        db.add(order)
        db.commit()
        return PlainTextResponse("success")
    except Exception:
        db.rollback()
        return PlainTextResponse("fail")
