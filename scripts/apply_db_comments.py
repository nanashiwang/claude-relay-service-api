from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import engine
from app.models import Base

TARGET_TABLES = {
    "users",
    "api_keys",
    "products",
    "card_codes",
    "card_claims",
    "wallets",
    "wallet_transactions",
    "recharge_requests",
    "refund_requests",
}

STRING_TYPES = {
    "char",
    "varchar",
    "text",
    "tinytext",
    "mediumtext",
    "longtext",
    "enum",
    "set",
}

NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")


def escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def format_default(value: object, data_type: str) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return str(value)

    text_value = str(value)
    upper = text_value.upper()
    if upper.startswith("CURRENT_TIMESTAMP") or upper in {"NOW()", "UUID()"}:
        return text_value

    if data_type.lower() in STRING_TYPES:
        return f"'{escape_sql_string(text_value)}'"

    if NUMERIC_RE.match(text_value):
        return text_value

    return f"'{escape_sql_string(text_value)}'"


def build_modify_column_sql(table_name: str, row: dict, new_comment: str) -> str:
    column_name = row["COLUMN_NAME"]
    column_type = row["COLUMN_TYPE"]
    data_type = row["DATA_TYPE"]
    is_nullable = row["IS_NULLABLE"] == "YES"
    column_default = row["COLUMN_DEFAULT"]
    extra = (row["EXTRA"] or "").lower()
    charset = row["CHARACTER_SET_NAME"]
    collation = row["COLLATION_NAME"]

    parts: list[str] = [f"`{column_name}`", column_type]
    if charset:
        parts.append(f"CHARACTER SET {charset}")
    if collation:
        parts.append(f"COLLATE {collation}")
    parts.append("NULL" if is_nullable else "NOT NULL")

    default_sql = format_default(column_default, data_type)
    if default_sql is not None:
        parts.append(f"DEFAULT {default_sql}")

    if "auto_increment" in extra:
        parts.append("AUTO_INCREMENT")
    if "on update current_timestamp" in extra:
        parts.append("ON UPDATE CURRENT_TIMESTAMP")

    parts.append(f"COMMENT '{escape_sql_string(new_comment)}'")
    column_sql = " ".join(parts)
    return f"ALTER TABLE `{table_name}` MODIFY COLUMN {column_sql}"


def main() -> None:
    parser = argparse.ArgumentParser(description="把 SQLAlchemy 模型中的 comment 同步到 MySQL（默认仅打印 SQL）")
    parser.add_argument("--apply", action="store_true", help="执行 SQL（否则只打印）")
    args = parser.parse_args()

    statements: list[str] = []

    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in TARGET_TABLES:
                continue

            current_table_comment = conn.execute(
                text(
                    """
                    SELECT table_comment
                    FROM information_schema.tables
                    WHERE table_schema=DATABASE() AND table_name=:table_name
                    """
                ),
                {"table_name": table.name},
            ).scalar_one_or_none()

            if table.comment and (current_table_comment or "") != table.comment:
                statements.append(f"ALTER TABLE `{table.name}` COMMENT='{escape_sql_string(table.comment)}'")

            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA,
                           CHARACTER_SET_NAME, COLLATION_NAME, COLUMN_COMMENT
                    FROM information_schema.columns
                    WHERE table_schema=DATABASE() AND table_name=:table_name
                    ORDER BY ORDINAL_POSITION
                    """
                ),
                {"table_name": table.name},
            ).mappings().all()
            current_columns = {r["COLUMN_NAME"]: dict(r) for r in rows}

            for column in table.columns:
                if not column.comment:
                    continue
                current = current_columns.get(column.name)
                if not current:
                    continue
                if (current.get("COLUMN_COMMENT") or "") == column.comment:
                    continue
                statements.append(build_modify_column_sql(table.name, current, column.comment))

        if not statements:
            print("无需要更新的注释")
            return

        for sql in statements:
            print(sql + ";")

        if not args.apply:
            print(f"\n以上共 {len(statements)} 条 SQL（默认不执行），加 --apply 才会执行。")
            return

        for sql in statements:
            conn.execute(text(sql))
        conn.commit()
        print(f"\n已执行并应用 {len(statements)} 条注释变更。")


if __name__ == "__main__":
    main()

