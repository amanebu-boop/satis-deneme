import os
from uuid import uuid4

import pytest

from app import db


def test_postgresql_backend_schema_and_core_records(monkeypatch):
    postgres_url = os.environ.get("POSTGRES_TEST_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_URL is not configured for this run.")

    psycopg = pytest.importorskip("psycopg")
    schema = f"sales_ci_{uuid4().hex[:12]}"

    with psycopg.connect(postgres_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')

    monkeypatch.setenv("SALES_DATABASE_URL", postgres_url)
    monkeypatch.setenv("SALES_DATABASE_SCHEMA", schema)
    try:
        db.init_db()
        company_id = str(uuid4())
        company = db.create_company({
            "id": company_id,
            "name": "PostgreSQL CI Test",
            "authorized_people": [],
            "phone_numbers": [],
        })
        assert db.get_company(company_id)["name"] == company["name"]

        product_id = str(uuid4())
        product = db.create_product({
            "id": product_id,
            "sku": f"CI-{uuid4().hex[:8]}",
            "name": "CI Test Machine",
            "description": None,
            "currency": "EUR",
            "unit_price": "22000",
            "product_type": "machine",
            "parent_product_id": None,
        })
        assert db.get_product(product_id)["sku"] == product["sku"]

        meeting_id = str(uuid4())
        meeting = db.create_meeting({
            "id": meeting_id,
            "company_id": company_id,
            "meeting_date": "2026-11-02T10:00",
            "notes": "PostgreSQL integration test",
            "meeting_type": "visit",
            "topic": "CI",
            "product_lines": [{
                "product_id": product_id,
                "sku": product["sku"],
                "name": product["name"],
                "quantity": 1,
                "unit_price": "22000",
                "currency": "EUR",
            }],
        })
        assert meeting["product_lines"][0]["name"] == "CI Test Machine"

        quote_id = str(uuid4())
        quotation = db.create_quotation({
            "id": quote_id,
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
                "description": "CI Test Machine",
                "quantity": "1",
                "unit_price": "22000",
                "line_total": "22000.00",
            }],
        })
        assert quotation["id"] == quote_id
        assert db.get_quotation(quote_id)["total"] == "26400.00"
    finally:
        monkeypatch.delenv("SALES_DATABASE_SCHEMA", raising=False)
        monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
        with psycopg.connect(postgres_url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
