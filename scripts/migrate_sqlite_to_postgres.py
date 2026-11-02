"""Conservative, dry-run-first SQLite to PostgreSQL data migration utility."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

TABLE_ORDER = (
    "companies", "products", "contacts", "meetings", "follow_up_tasks",
    "meeting_products", "quotations", "quote_sequences", "quotation_lines", "auth_sessions",
)


def _digest(rows: list[dict[str, Any]], columns: list[str]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = json.dumps([row.get(column) for column in columns], ensure_ascii=False, separators=(",", ":"), default=str)
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _sort_products(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = {row["id"]: row for row in rows}
    ordered = []
    while remaining:
        ready = [row for row in remaining.values() if not row.get("parent_product_id") or row["parent_product_id"] not in remaining]
        if not ready:
            raise RuntimeError("Product catalog contains a parent cycle; refusing migration")
        for row in ready:
            ordered.append(row)
            remaining.pop(row["id"], None)
    return ordered


def _source_snapshot(source_path: Path, target_columns: dict[str, list[str]]):
    snapshot = {}
    with sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        existing = {row["name"] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in TABLE_ORDER:
            if table not in existing:
                raise RuntimeError(f"Source database is missing required table: {table}")
            source_info = source.execute(f"PRAGMA table_info({table})").fetchall()
            source_names = {row["name"] for row in source_info}
            columns = target_columns[table]
            missing = [column for column in columns if column not in source_names]
            if missing:
                raise RuntimeError(f"Source table {table} is missing target columns: {missing}")
            primary_key = [row["name"] for row in sorted(source_info, key=lambda item: item["pk"]) if row["pk"]]
            order = primary_key or columns
            sql = f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(order)}"
            rows = [dict(row) for row in source.execute(sql).fetchall()]
            digest_rows = rows
            if table == "products":
                rows = _sort_products(rows)
            snapshot[table] = {"columns": columns, "rows": rows, "count": len(rows), "sha256": _digest(digest_rows, columns)}
    return snapshot


def migrate_sqlite_to_postgres(source_path: Path, target_url: str, *, apply: bool = False) -> dict[str, Any]:
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source database not found: {source_path}")
    if target_url.startswith("postgres://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgres://"):]
    elif target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgresql://"):]
    engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with tempfile.TemporaryDirectory(prefix="sales-sqlite-migration-") as temporary_dir:
            source_copy = Path(temporary_dir) / "source.db"
            source_connection = sqlite3.connect(str(source_path))
            copy_connection = sqlite3.connect(str(source_copy))
            try:
                # SQLite backup API captures a consistent snapshot, including committed WAL pages.
                source_connection.backup(copy_connection)
            finally:
                copy_connection.close()
                source_connection.close()

            previous = {
                name: os.environ.get(name)
                for name in ("DATABASE_URL", "SALES_DATABASE_URL", "SALES_DATABASE_PATH")
            }
            try:
                os.environ.pop("DATABASE_URL", None)
                os.environ.pop("SALES_DATABASE_URL", None)
                os.environ["SALES_DATABASE_PATH"] = str(source_copy)
                from app import db
                db.init_db()  # Apply the existing safe SQLite schema upgrades to the copy only.
            finally:
                for name, value in previous.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value

            with engine.connect() as connection:
                inspector = inspect(connection)
                target_tables = set(inspector.get_table_names())
                missing_tables = [table for table in TABLE_ORDER if table not in target_tables]
                if missing_tables:
                    raise RuntimeError(f"Target schema is not initialized; missing tables: {missing_tables}")
                target_columns = {table: [column["name"] for column in inspector.get_columns(table)] for table in TABLE_ORDER}
                target_pks = {table: inspector.get_pk_constraint(table).get("constrained_columns") or [] for table in TABLE_ORDER}
                source = _source_snapshot(source_copy, target_columns)
                target_counts = {table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in TABLE_ORDER}
                occupied = {table: count for table, count in target_counts.items() if count}
                if occupied:
                    raise RuntimeError(f"Target database is not empty; refusing overwrite: {occupied}")
            if apply:
                with engine.begin() as connection:
                    for table in TABLE_ORDER:
                        entry = source[table]
                        if not entry["rows"]:
                            continue
                        columns = entry["columns"]
                        names = ", ".join(columns)
                        binds = ", ".join(f":v{i}" for i in range(len(columns)))
                        statement = text(f"INSERT INTO {table} ({names}) VALUES ({binds})")
                        batch = [{f"v{i}": row.get(column) for i, column in enumerate(columns)} for row in entry["rows"]]
                        for offset in range(0, len(batch), 500):
                            connection.execute(statement, batch[offset:offset + 500])
                    for table in TABLE_ORDER:
                        columns = source[table]["columns"]
                        order = target_pks[table] or columns
                        rows = [dict(row._mapping) for row in connection.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(order)}")).fetchall()]
                        actual_digest = _digest(rows, columns)
                        if len(rows) != source[table]["count"] or actual_digest != source[table]["sha256"]:
                            raise RuntimeError(f"Post-copy verification failed for table {table}")
        return {
            "mode": "apply" if apply else "dry-run",
            "source": str(source_path),
            "tables": {table: {"rows": source[table]["count"], "sha256": source[table]["sha256"]} for table in TABLE_ORDER},
            "target_was_empty": True,
            "verified": bool(apply),
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy SQLite data to an empty PostgreSQL schema; dry-run is the default.")
    parser.add_argument("--source", type=Path, default=Path(os.environ.get("SALES_DATABASE_PATH", "data/sales.db")))
    parser.add_argument("--apply", action="store_true", help="Write rows to the target; otherwise only inspect and hash.")
    args = parser.parse_args()
    target_url = os.environ.get("DATABASE_URL") or os.environ.get("SALES_DATABASE_URL")
    if not target_url:
        raise SystemExit("DATABASE_URL is required")
    result = migrate_sqlite_to_postgres(args.source, target_url, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY RUN ONLY: no rows were written. Review the report, then rerun with --apply in a maintenance window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
