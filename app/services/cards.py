from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import CardClaim, CardCode, Product
from app.models.enums import CardCodeStatus, WalletTxKind
from app.schemas.cards import ClaimBatchOut, ClaimOut
from app.services.earnings import create_merchant_earning
from app.services.referral import get_rebate_percent, try_apply_referral_rebate
from app.services.wallet import apply_wallet_tx, lock_wallet


def _normalize_quantity(quantity: int | None) -> int:
    try:
        q = int(quantity or 1)
    except Exception:
        q = 1
    return max(1, q)


def _resolve_discount_percent(product: Product, quantity: int = 1) -> int | None:
    qty = _normalize_quantity(quantity)

    matched_tier_discount: int | None = None
    tiers = list(getattr(product, "tier_discounts", []) or [])
    if tiers:
        tiers.sort(key=lambda item: int(getattr(item, "min_quantity", 0) or 0))
        for tier in tiers:
            min_qty = int(getattr(tier, "min_quantity", 0) or 0)
            if min_qty <= 0:
                continue
            if qty >= min_qty:
                matched_tier_discount = int(getattr(tier, "discount_percent", 0) or 0)
            else:
                break

    if matched_tier_discount is not None and 0 < matched_tier_discount < 100:
        return matched_tier_discount

    discount = product.discount_percent
    if discount is not None and 0 < discount < 100:
        return int(discount)

    return None


def _resolve_price_cents(product: Product, quantity: int = 1) -> int:
    discount = _resolve_discount_percent(product, quantity)
    if discount is not None:
        discounted = round(product.price_cents * discount / 100)
        return max(discounted, 1)
    return product.price_cents


def _get_product_for_claim(db: Session, sku: str) -> Product:
    product = db.execute(select(Product).where(Product.sku == sku, Product.active.is_(True))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在或已下架")
    if _resolve_price_cents(product, 1) <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="产品未设置价格")
    return product


def resolve_price_cents(product: Product, quantity: int = 1) -> int:
    return _resolve_price_cents(product, quantity)


def deliver_paid_order(
    *,
    db: Session,
    user,
    product: Product,
    quantity: int,
    unit_price_cents: int | None = None,
) -> tuple[list[CardClaim], list[CardCode]]:
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="购买数量错误")

    unit_cost = unit_price_cents if unit_price_cents is not None else _resolve_price_cents(product, quantity)
    codes = (
        db.execute(
            select(CardCode)
            .where(CardCode.product_id == product.id, CardCode.status == CardCodeStatus.available)
            .with_for_update(skip_locked=True)
            .limit(quantity)
        )
        .scalars()
        .all()
    )
    if len(codes) < quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="库存不足")

    claims: list[CardClaim] = []
    for code in codes:
        claim = CardClaim(
            user_id=user.id,
            api_key_id=None,
            product_id=product.id,
            card_code_id=code.id,
            cost_cents=unit_cost,
            currency=product.currency,
        )
        db.add(claim)
        db.flush()

        code.status = CardCodeStatus.claimed
        code.claimed_by_user_id = user.id
        code.claimed_at = utcnow()
        db.add(code)

        try_apply_referral_rebate(
            db,
            referred_user_id=user.id,
            card_claim_id=claim.id,
            amount_cents=unit_cost,
            currency=product.currency,
        )

        # 创建商户收益记录
        rebate_percent = get_rebate_percent(db)
        create_merchant_earning(
            db,
            card_claim=claim,
            product=product,
            rebate_percent=rebate_percent,
        )

        claims.append(claim)

    return claims, codes


def _claim_many_in_tx(
    db: Session,
    user,
    api_key_id: int | None,
    *,
    product: Product,
    sku: str,
    quantity: int,
) -> tuple[list[CardClaim], list[CardCode], int]:
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="购买数量错误")

    wallet = lock_wallet(db, user.id)
    unit_price_cents = _resolve_price_cents(product, quantity)
    total_cost = unit_price_cents * quantity
    if wallet.balance_cents < total_cost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="余额不足")

    codes = (
        db.execute(
            select(CardCode)
            .where(CardCode.product_id == product.id, CardCode.status == CardCodeStatus.available)
            .with_for_update(skip_locked=True)
            .limit(quantity)
        )
        .scalars()
        .all()
    )
    if len(codes) < quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="库存不足")

    claims: list[CardClaim] = []
    balance_after_cents = wallet.balance_cents
    for code in codes:
        claim = CardClaim(
            user_id=user.id,
            api_key_id=api_key_id,
            product_id=product.id,
            card_code_id=code.id,
            cost_cents=unit_price_cents,
            currency=product.currency,
        )
        db.add(claim)
        db.flush()

        code.status = CardCodeStatus.claimed
        code.claimed_by_user_id = user.id
        code.claimed_at = utcnow()
        db.add(code)

        tx = apply_wallet_tx(
            db=db,
            wallet=wallet,
            amount_cents=-unit_price_cents,
            kind=WalletTxKind.purchase,
            reference_type="card_claim",
            reference_id=claim.id,
            currency=product.currency,
            created_by_user_id=None,
            note=f"claim:{sku}",
        )
        balance_after_cents = tx.balance_after_cents
        try_apply_referral_rebate(
            db,
            referred_user_id=user.id,
            card_claim_id=claim.id,
            amount_cents=unit_price_cents,
            currency=product.currency,
        )

        # 创建商户收益记录（在循环外统一处理，避免重复查询）
        claims.append(claim)

    # 处理商户收益
    rebate_percent = get_rebate_percent(db)
    for claim in claims:
        create_merchant_earning(
            db,
            card_claim=claim,
            product=product,
            rebate_percent=rebate_percent,
        )

    return claims, codes, balance_after_cents


def claim_cards(db: Session, user, api_key_id: int | None, sku: str, quantity: int) -> ClaimBatchOut:
    product = _get_product_for_claim(db, sku)

    try:
        claims, codes, balance_after_cents = _claim_many_in_tx(db, user, api_key_id, product=product, sku=sku, quantity=quantity)
        unit_cost_cents = claims[0].cost_cents if claims else _resolve_price_cents(product, quantity)
        out = ClaimBatchOut(
            sku=sku,
            quantity=quantity,
            unit_cost_cents=unit_cost_cents,
            total_cost_cents=unit_cost_cents * quantity,
            currency=product.currency,
            card_codes=[c.code for c in codes],
            balance_after_cents=balance_after_cents,
        )
        db.commit()
        return out
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def claim_card(db: Session, user, api_key_id: int | None, sku: str) -> ClaimOut:
    product = _get_product_for_claim(db, sku)

    try:
        claims, codes, balance_after_cents = _claim_many_in_tx(db, user, api_key_id, product=product, sku=sku, quantity=1)
        claim = claims[0]
        code = codes[0]
        out = ClaimOut(
            claim_id=claim.id,
            sku=sku,
            cost_cents=claim.cost_cents,
            currency=product.currency,
            card_code=code.code,
            balance_after_cents=balance_after_cents,
        )
        db.commit()
        return out
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
