from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Base, User, Wallet
from app.services.announcement import seed_default_announcement
from app.services.products import seed_default_products


def main() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_default_products(db)
        seed_default_announcement(db)

        if not settings.admin_username or not settings.admin_password:
            print("未设置 ADMIN_USERNAME/ADMIN_PASSWORD，跳过创建管理员")
            return

        exists = db.execute(select(User).where(User.username == settings.admin_username)).scalar_one_or_none()
        if exists:
            print("管理员已存在，跳过创建")
            return

        admin = User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Wallet(user_id=admin.id, balance_cents=0, currency=settings.default_currency))
        db.commit()
        print(f"已创建管理员: {settings.admin_username}")


if __name__ == "__main__":
    main()
