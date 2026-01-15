from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import CardCode, Product
from app.models.enums import CardCodeStatus
from app.schemas.product import ProductOut, ProductUpdateIn

router = APIRouter()


class CategoryProducts(BaseModel):
    """分类产品列表"""
    codex: list[ProductOut]
    gemini: list[ProductOut]
    claude: list[ProductOut]


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), _: object = Depends(get_current_user)) -> list[Product]:
    """获取所有产品列表"""
    return db.execute(select(Product).order_by(Product.provider.asc(), Product.id.asc())).scalars().all()


@router.get("/by-category", response_model=CategoryProducts)
def get_products_by_category(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Dict[str, list[Product]]:
    """按供应商分类获取产品列表 (codex/gemini/claude)"""
    products = db.execute(
        select(Product)
        .where(Product.active == True)
        .order_by(Product.provider.asc(), Product.kind.asc(), Product.id.asc())
    ).scalars().all()

    result: Dict[str, list[Product]] = {"codex": [], "gemini": [], "claude": []}
    for p in products:
        provider = p.provider.lower()
        if provider in result:
            result[provider].append(p)

    return result


@router.get("/provider/{provider}", response_model=list[ProductOut])
def get_products_by_provider(
    provider: str,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[Product]:
    """获取指定供应商的产品列表"""
    products = db.execute(
        select(Product)
        .where(Product.provider.ilike(provider), Product.active == True)
        .order_by(Product.id.asc())
    ).scalars().all()
    return list(products)


@router.get("/inventory/{product_sku}")
def get_product_inventory(
    product_sku: str,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> dict:
    """查询指定 SKU 的可用库存（供前端展示用）"""
    product = db.execute(select(Product).where(Product.sku == product_sku, Product.active == True)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    available = db.execute(
        select(func.count()).select_from(CardCode).where(
            CardCode.product_id == product.id, CardCode.status == CardCodeStatus.available
        )
    ).scalar_one()
    return {"product_id": product.id, "sku": product.sku, "available": int(available)}


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产品不存在")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
