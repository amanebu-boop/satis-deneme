import os
from uuid import uuid4

import pytest

from app import db


def test_sqlite_to_postgresql_migration_dry_run_and_apply(monkeypatch, tmp_path):
    postgres_url = os.environ.get("POSTGRES_TEST_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_URL is not configured for this run.")

    psycopg = pytest.importorskip("psycopg")
    schema = f"sales_mig_{uuid4().hex[:12]}"
    with psycopg.connect(postgres_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')

    source_path = tmp_path / "source.sqlite"
    try:
        # Prepare an empty PostgreSQL schema with the current application DDL.
        monkeypatch.setenv("SALES_DATABASE_URL", postgres_url)
        monkeypatch.setenv("SALES_DATABASE_SCHEMA", schema)
        db.init_db()

        # Build a representative SQLite source database using the public data APIs.
        monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
        monkeypatch.delenv("SALES_DATABASE_SCHEMA", raising=False)
        monkeypatch.setenv("SALES_DATABASE_PATH", str(source_path))
        db.init_db()

        company_id = str(uuid4())
        db.create_company({
            "id": company_id,
            "name": "Migration Integration Ltd.",
            "authorized_people": ["Test Person"],
            "phone_numbers": ["+90 555 000 0000"],
            "city": "Konya",
            "notes": "Preserve Unicode: İmalat",
        })
        db.create_contact({
            "id": str(uuid4()),
            "company_id": company_id,
            "name": "Migration Contact",
            "email": "migration@example.invalid",
            "phone": None,
            "notes": None,
        })

        machine_id = str(uuid4())
        option_id = str(uuid4())
        db.create_product({
            "id": machine_id,
            "sku": f"MIG-{uuid4().hex[:8]}",
            "name": "Migration Machine",
            "description": "Parent product",
            "currency": "EUR",
            "unit_price": "22000",
            "product_type": "machine",
            "parent_product_id": None,
        })
        db.create_product({
            "id": option_id,
            "sku": f"MIG-{uuid4().hex[:8]}",
            "name": "Migration Option",
            "description": "Child product",
            "currency": "EUR",
            "unit_price": "4500",
            "product_type": "option",
            "parent_product_id": machine_id,
        })

        meeting_id = str(uuid4())
        db.create_meeting({
            "id": meeting_id,
            "company_id": company_id,
            "meeting_date": "2026-11-02T10:00",
            "notes": "Meeting retained",
            "meeting_type": "visit",
            "topic": "Migration test",
            "product_lines": [{
                "product_id": machine_id,
                "sku": db.get_product(machine_id)["sku"],
                "name": "Migration Machine",
                "quantity": 1,
                "unit_price": "22000",
                "currency": "EUR",
            }],
        })
        db.create_follow_up({
            "id": str(uuid4()),
            "company_id": company_id,
            "title": "Migration follow-up",
            "due_date": "2026-11-10",
            "status": "open",
            "created_at": "2026-11-02T10:00:00+00:00",
        })
        quotation_id = str(uuid4())
        db.create_quotation({
            "id": quotation_id,
            "company_id": company_id,
            "currency": "EUR",
            "subtotal": "22000.00",
            "tax_rate": "0.20",
            "tax_amount": "4400.00",
            "total": "26400.00",
            "status": "draft",
            "created_at": "2026-11-02T10:00:00+00:00",
            "lines": [{
                "id": str(uuid4()),
                "description": "Migration Machine",
                "quantity": "1",
                "unit_price": "22000",
                "line_total": "22000.00",
            }],
        })

        import importlib.util
        script = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py"
        spec = importlib.util.spec_from_file_location("migration_under_test", script)
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)

        monkeypatch.setenv("SALES_DATABASE_URL", postgres_url)
        monkeypatch.setenv("SALES_DATABASE_SCHEMA", schema)
        dry_counts = migration.migrate(source_path, apply=False)
        assert dry_counts["companies"] == 1
        assert dry_counts["contacts"] == 1
        assert dry_counts["products"] == 2
        assert dry_counts["meetings"] == 1
        assert dry_counts["meeting_products"] == 1
        assert dry_counts["quotations"] == 1
        assert dry_counts["quotation_lines"] == 1

        with db.connect() as target:
            assert target.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"] == 0

        imported_counts = migration.migrate(source_path, apply=True)
        assert imported_counts == dry_counts

        company = db.get_company(company_id)
        assert company["name"] == "Migration Integration Ltd."
        assert company["authorized_people"] == ["Test Person"]
        assert company["notes"] == "Preserve Unicode: İmalat"
        assert db.get_product(option_id)["parent_product_id"] == machine_id
        meeting = next(item for item in db.list_meetings() if item["id"] == meeting_id)
        assert meeting["product_lines"][0]["product_id"] == machine_id
        quotation = db.get_quotation(quotation_id)
        assert quotation["quote_number"] == "ERS-2026-0001"
        assert quotation["lines"][0]["description"] == "Migration Machine"
    finally:
        monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
        monkeypatch.delenv("SALES_DATABASE_SCHEMA", raising=False)
        monkeypatch.delenv("SALES_DATABASE_PATH", raising=False)
        with psycopg.connect(postgres_url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
