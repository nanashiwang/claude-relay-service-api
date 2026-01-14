from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# 使用 pbkdf2_sha256 避免 bcrypt 依赖兼容性问题（bcrypt 新版本会导致 passlib 初始化失败）
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, is_admin: bool) -> str:
    expire = utcnow() + timedelta(minutes=settings.jwt_access_token_exp_minutes)
    payload: dict[str, Any] = {"sub": subject, "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def api_key_prefix(api_key: str) -> str:
    return api_key[:8]


def hash_api_key(api_key: str) -> bytes:
    return hashlib.sha256(api_key.encode("utf-8")).digest()
