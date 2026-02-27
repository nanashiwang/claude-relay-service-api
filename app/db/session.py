from __future__ import annotations

from collections.abc import Generator
import re

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _is_unknown_database_error(exc: OperationalError) -> bool:
    raw = getattr(exc, "orig", exc)
    args = getattr(raw, "args", ())
    if args:
        code = args[0]
        if isinstance(code, int) and code == 1049:  # MySQL: Unknown database
            return True
    return "unknown database" in str(raw).lower()


def _safe_mysql_charset(raw_charset: str | None) -> str:
    charset = (raw_charset or "").strip().lower()
    if not charset:
        return "utf8mb4"
    if re.fullmatch(r"[a-z0-9_]+", charset):
        return charset
    return "utf8mb4"


def _ensure_mysql_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("mysql"):
        return
    if not url.database:
        return

    probe_engine = create_engine(url, pool_pre_ping=True)
    try:
        with probe_engine.connect():
            return
    except OperationalError as exc:
        if not _is_unknown_database_error(exc):
            raise
    finally:
        probe_engine.dispose()

    admin_engine = create_engine(url.set(database=None), pool_pre_ping=True)
    try:
        db_name = url.database.replace("`", "``")
        charset = _safe_mysql_charset(url.query.get("charset"))
        with admin_engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET {charset}")
    except OperationalError as exc:
        raise RuntimeError("MySQL 数据库不存在且自动创建失败，请确认账号具备建库权限或先手动创建数据库") from exc
    finally:
        admin_engine.dispose()


_ensure_mysql_database_exists(settings.database_url)
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
