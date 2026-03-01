from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_api_key
from app.db.session import get_db
from app.models import ApiKey, User

if TYPE_CHECKING:
    from app.models import Merchant, Product


def get_current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
    """获取当前登录用户"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少登录凭证")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效")

    user = db.execute(select(User).where(User.id == int(user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def require_merchant(user: User = Depends(get_current_user)) -> User:
    """要求商户权限"""
    if not user.is_merchant or not user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要商户权限")
    return user


def get_api_key_user(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> tuple[User, ApiKey]:
    """通过API Key获取用户"""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 API Key")

    key_hash = hash_api_key(x_api_key)
    api_key = db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    ).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效或已吊销")

    user = db.execute(select(User).where(User.id == api_key.user_id)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")

    return user, api_key


def can_manage_product(user: User, product_id: int, db: Session) -> bool:
    """
    检查用户是否可以管理指定商品

    Args:
        user: 用户对象
        product_id: 产品ID
        db: 数据库会话

    Returns:
        是否有管理权限
    """
    # 管理员可以管理所有商品
    if user.is_admin:
        return True

    # 商户只能管理自己的商品
    if user.is_merchant and user.merchant_id:
        from app.models import Product

        product = db.get(Product, product_id)
        return product is not None and product.merchant_id == user.merchant_id

    return False

