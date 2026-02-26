from __future__ import annotations

import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import CardCode, Product, ProductTierDiscount
from app.models.enums import CardCodeStatus
from app.models.enums import ProductKind
from app.schemas.product import ProductCreateIn, ProductOut, ProductUpdateIn

router = APIRouter()

_INVENTORY_CACHE_TTL_SECONDS = 8
_inventory_cache_lock = Lock()
_inventory_cache_payload: CategoryProductsWithInventory | None = None
_inventory_cache_ts = 0.0


def _get_inventory_cache() -> CategoryProductsWithInventory | None:
    now = time.monotonic()
    with _inventory_cache_lock:
        if _inventory_cache_payload and now - _inventory_cache_ts < _INVENTORY_CACHE_TTL_SECONDS:
            return _inventory_cache_payload
    return None


def _set_inventory_cache(payload: CategoryProductsWithInventory) -> None:
    global _inventory_cache_payload, _inventory_cache_ts
    with _inventory_cache_lock:
        _inventory_cache_payload = payload
        _inventory_cache_ts = time.monotonic()


def _invalidate_inventory_cache() -> None:
    global _inventory_cache_payload, _inventory_cache_ts
    with _inventory_cache_lock:
        _inventory_cache_payload = None
        _inventory_cache_ts = 0.0


def _active_products_base_query():
    return (
        select(Product)
        .options(selectinload(Product.tier_discounts))
        .where(Product.active.is_(True))
    )


def _normalize_provider_key(provider: str | None) -> str:
    normalized = " ".join((provider or "").strip().split())
    return normalized.lower() if normalized else "other"


def _group_products_by_provider(products: list[Product]) -> dict[str, list[Product]]:
    grouped: dict[str, list[Product]] = {}
    for product in products:
        key = _normalize_provider_key(product.provider)
        grouped.setdefault(key, []).append(product)
    return grouped


def _normalize_tier_discounts(raw_tiers: list[dict] | None) -> list[tuple[int, int]]:
    tiers = list(raw_tiers or [])
    normalized: list[tuple[int, int]] = []
    seen_qty: set[int] = set()
    for tier in tiers:
        min_qty = int(tier["min_quantity"])
        discount_percent = int(tier["discount_percent"])
        if min_qty in seen_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"阶梯数量重复: {min_qty}")
        seen_qty.add(min_qty)
        normalized.append((min_qty, discount_percent))

    normalized.sort(key=lambda item: item[0])
    return normalized


class CategoryProductsWithInventory(BaseModel):
    categories: dict[str, list[ProductOut]]
    inventory: dict[str, int]


class InventoryBatchIn(BaseModel):
    skus: list[str]


class InventoryItemOut(BaseModel):
    sku: str
    available: int


class InventoryBatchOut(BaseModel):
    items: list[InventoryItemOut]


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), _: object = Depends(get_current_user)) -> list[Product]:
    return (
        db.execute(
            select(Product)
            .options(selectinload(Product.tier_discounts))
            .order_by(Product.provider.asc(), Product.id.asc())
        )
        .scalars()
        .all()
    )


@router.get("/by-category", response_model=dict[str, list[ProductOut]])
def get_products_by_category(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> dict[str, list[Product]]:
    products = (
        db.execute(
            _active_products_base_query().order_by(Product.provider.asc(), Product.kind.asc(), Product.id.asc())
        )
        .scalars()
        .all()
    )

    return _group_products_by_provider(products)


@router.get("/by-category-with-inventory", response_model=CategoryProductsWithInventory)
def get_products_by_category_with_inventory(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> CategoryProductsWithInventory:
    cached = _get_inventory_cache()
    if cached:
        return cached

    products = (
        db.execute(
            _active_products_base_query().order_by(Product.provider.asc(), Product.kind.asc(), Product.id.asc())
        )
        .scalars()
        .all()
    )

    categories = _group_products_by_provider(products)

    product_ids = [p.id for p in products]
    counts: dict[int, int] = {}
    if product_ids:
        rows = db.execute(
            select(CardCode.product_id, func.count())
            .where(CardCode.product_id.in_(product_ids), CardCode.status == CardCodeStatus.available)
            .group_by(CardCode.product_id)
        ).all()
        counts = {pid: int(cnt) for pid, cnt in rows}

    inventory = {p.sku: counts.get(p.id, 0) for p in products}
    payload = CategoryProductsWithInventory(
        categories=categories,
        inventory=inventory,
    )
    _set_inventory_cache(payload)
    return payload


@router.get("/provider/{provider}", response_model=list[ProductOut])
def get_products_by_provider(
    provider: str,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[Product]:
    products = (
        db.execute(
            _active_products_base_query()
            .where(Product.provider.ilike(provider))
            .order_by(Product.id.asc())
        )
        .scalars()
        .all()
    )
    return list(products)


@router.post("/inventory/batch", response_model=InventoryBatchOut)
def get_product_inventory_batch(
    payload: InventoryBatchIn,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> InventoryBatchOut:
    normalized: list[str] = []
    seen: set[str] = set()
    for sku in payload.skus or []:
        cleaned = (sku or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    if not normalized:
        return InventoryBatchOut(items=[])

    rows = db.execute(
        select(Product.id, Product.sku).where(Product.sku.in_(normalized), Product.active.is_(True))
    ).all()
    sku_to_id = {sku: pid for pid, sku in rows}

    counts: dict[int, int] = {}
    if sku_to_id:
        count_rows = db.execute(
            select(CardCode.product_id, func.count())
            .where(CardCode.product_id.in_(list(sku_to_id.values())), CardCode.status == CardCodeStatus.available)
            .group_by(CardCode.product_id)
        ).all()
        counts = {pid: int(cnt) for pid, cnt in count_rows}

    items: list[InventoryItemOut] = []
    for sku in normalized:
        product_id = sku_to_id.get(sku)
        available = counts.get(product_id, 0) if product_id else 0
        items.append(InventoryItemOut(sku=sku, available=available))
    return InventoryBatchOut(items=items)


@router.get("/inventory/{product_sku}")
def get_product_inventory(
    product_sku: str,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> dict:
    product = db.execute(select(Product).where(Product.sku == product_sku, Product.active.is_(True))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    available = db.execute(
        select(func.count()).select_from(CardCode).where(
            CardCode.product_id == product.id,
            CardCode.status == CardCodeStatus.available,
        )
    ).scalar_one()
    return {"product_id": product.id, "sku": product.sku, "available": int(available)}


@router.post("", response_model=ProductOut)
def create_product(
    payload: ProductCreateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Product:
    data = payload.model_dump()
    data["sku"] = (data.get("sku") or "").strip()
    data["provider"] = " ".join(((data.get("provider") or "").strip().split()))
    data["currency"] = str(data.get("currency") or "CNY").upper()

    if not data["sku"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SKU 不能为空")
    if not data["provider"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider 不能为空")

    exists = db.execute(select(Product.id).where(Product.sku == data["sku"])).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SKU 已存在")

    raw_tiers = data.pop("tier_discounts", [])
    if data.get("discount_percent") is not None and (data["discount_percent"] <= 0 or data["discount_percent"] >= 100):
        data["discount_percent"] = None

    if data.get("kind") == ProductKind.day:
        data["usage_usd"] = None
    if data.get("kind") == ProductKind.usage:
        data["duration_days"] = None

    product = Product(**data)
    for min_qty, discount_percent in _normalize_tier_discounts(raw_tiers):
        product.tier_discounts.append(
            ProductTierDiscount(min_quantity=min_qty, discount_percent=discount_percent)
        )

    db.add(product)
    db.commit()
    _invalidate_inventory_cache()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Product:
    product = db.execute(
        select(Product).options(selectinload(Product.tier_discounts)).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    data = payload.model_dump(exclude_unset=True)
    raw_tiers = data.pop("tier_discounts", None)

    if "discount_percent" in data:
        discount = data.get("discount_percent")
        if discount is not None and (discount <= 0 or discount >= 100):
            data["discount_percent"] = None

    for field, value in data.items():
        setattr(product, field, value)

    if raw_tiers is not None:
        normalized = _normalize_tier_discounts(raw_tiers)
        product.tier_discounts.clear()
        for min_qty, discount_percent in normalized:
            product.tier_discounts.append(
                ProductTierDiscount(min_quantity=min_qty, discount_percent=discount_percent)
            )

    db.add(product)
    db.commit()
    _invalidate_inventory_cache()
    db.refresh(product)
    return product
