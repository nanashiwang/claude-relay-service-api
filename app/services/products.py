from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.models.enums import ProductKind


DEFAULT_PRODUCTS: list[dict] = [
    {"sku": "codex_day_1", "provider": "codex", "kind": ProductKind.day, "duration_days": 1, "name": "codex 1天卡"},
    {"sku": "codex_day_7", "provider": "codex", "kind": ProductKind.day, "duration_days": 7, "name": "codex 7天卡"},
    {"sku": "codex_day_31", "provider": "codex", "kind": ProductKind.day, "duration_days": 31, "name": "codex 31天卡"},
    {"sku": "codex_usage_10", "provider": "codex", "kind": ProductKind.usage, "usage_usd": 10, "name": "codex 按量$10"},
    {"sku": "codex_usage_30", "provider": "codex", "kind": ProductKind.usage, "usage_usd": 30, "name": "codex 按量$30"},
    {"sku": "codex_usage_100", "provider": "codex", "kind": ProductKind.usage, "usage_usd": 100, "name": "codex 按量$100"},
    {"sku": "gemini_day_1", "provider": "gemini", "kind": ProductKind.day, "duration_days": 1, "name": "gemini 1天卡"},
    {"sku": "gemini_day_7", "provider": "gemini", "kind": ProductKind.day, "duration_days": 7, "name": "gemini 7天卡"},
    {"sku": "gemini_day_31", "provider": "gemini", "kind": ProductKind.day, "duration_days": 31, "name": "gemini 31天卡"},
    {"sku": "gemini_usage_10", "provider": "gemini", "kind": ProductKind.usage, "usage_usd": 10, "name": "gemini 按量$10"},
    {"sku": "gemini_usage_30", "provider": "gemini", "kind": ProductKind.usage, "usage_usd": 30, "name": "gemini 按量$30"},
    {"sku": "gemini_usage_100", "provider": "gemini", "kind": ProductKind.usage, "usage_usd": 100, "name": "gemini 按量$100"},
    {"sku": "claude_day_1", "provider": "claude", "kind": ProductKind.day, "duration_days": 1, "name": "claude 1天卡"},
    {"sku": "claude_day_7", "provider": "claude", "kind": ProductKind.day, "duration_days": 7, "name": "claude 7天卡"},
    {"sku": "claude_day_31", "provider": "claude", "kind": ProductKind.day, "duration_days": 31, "name": "claude 31天卡"},
    {"sku": "claude_usage_10", "provider": "claude", "kind": ProductKind.usage, "usage_usd": 10, "name": "claude 按量$10"},
    {"sku": "claude_usage_30", "provider": "claude", "kind": ProductKind.usage, "usage_usd": 30, "name": "claude 按量$30"},
    {"sku": "claude_usage_100", "provider": "claude", "kind": ProductKind.usage, "usage_usd": 100, "name": "claude 按量$100"},
]


def seed_default_products(db: Session) -> int:
    inserted = 0
    for item in DEFAULT_PRODUCTS:
        exists = db.execute(select(Product.id).where(Product.sku == item["sku"])).first()
        if exists:
            continue
        db.add(Product(**item))
        inserted += 1
    db.commit()
    return inserted

