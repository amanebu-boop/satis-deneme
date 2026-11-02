import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app import db, db_backend
from scripts.migrate_sqlite_to_postgres import TABLE_ORDER, migrate_sqlite_to_postgres


pytestmark = pytest.mark.skipif(
    not db_backend.is_postgres_configured(),
    reason="PostgreSQL migration integration test requires DATABASE_URL",
)


def test_sqlite_to_postgres_migration_dry_run_and_apply(tmp_path: Path, monkeypatch):
    target_url = os.environ["DATABASE_URL"]
    source_path = tmp_path / "source-sales.db"

    # Build a synthetic SQLite source without touching the configured PostgreSQL target.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
    monkeypatch.setenv("SALES_DATABASE_PATH", str(source_path))
    db.init_db()
    db.create_company({"id": "company-1", "name": "MIGRATION TEST"})
    db.create_product({
        "id": "z-parent", "sku": "MIG-PARENT", "name": "Parent machine",
        "currency": "EUR", "unit_price": "100", "product_type": "machine",
    })
    db.create_product({
        "id": "a-child", "sku": "MIG-OPTION", "name": "Child option",
        "currency": "EUR", "unit_price": "10", "product_type": "option",
        "parent_product_id": "z-parent",
    })
    db.create_meeting({
        "id": "meeting-1", "company_id": "company-1",
        "meeting_date": "2026-11-02", "notes": "synthetic migration fixture",
        "meeting_type": "phone", "topic": "migration",
        "product_lines": [{
            "id": "meeting-line-1", "product_id": "a-child", "sku": "MIG-OPTION",
            "name": "Child option", "quantity": 1, "unit_price": "10", "currency": "EUR",
        }],
    })
    db.create_quotation({
        "id": "quote-1", "company_id": "company-1", "currency": "EUR",
        "subtotal": "10", "tax_rate": "20", "tax_amount": "2", "total": "12",
        "status": "draft", "created_at": "2026-11-02T10:00:00+00:00",
        "lines": [{
            "id": "quote-line-1", "description": "Child option", "quantity": "1",
            "unit_price": "10", "line_total": "10",
        }],
    })

    # Restore the PostgreSQL environment for the migration utility.
    monkeypatch.setenv("DATABASE_URL", target_url)
    monkeypatch.delenv("SALES_DATABASE_PATH", raising=False)

    preview = migrate_sqlite_to_postgres(source_path, target_url, apply=False)
    assert preview["mode"] == "dry-run"
    assert preview["tables"]["companies"]["rows"] == 1
    assert preview["tables"]["meeting_products"]["rows"] == 1
    assert preview["verified"] is False

    result = migrate_sqlite_to_postgres(source_path, target_url, apply=True)
    assert result["verified"] is True
    with sqlite3.connect(source_path) as original_source:
        assert original_source.execute("SELECT count(*) FROM companies").fetchone()[0] == 1
    engine = create_engine(target_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM companies")).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM meetings")).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM meeting_products")).scalar_one() == 1
            assert connection.execute(text("SELECT parent_product_id FROM products WHERE id = 'a-child'")).scalar_one() == "z-parent"
    finally:
        with engine.begin() as connection:
            names = ", ".join(TABLE_ORDER)
            connection.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
        engine.dispose()
