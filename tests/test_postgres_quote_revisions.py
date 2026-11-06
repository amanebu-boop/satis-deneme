from uuid import uuid4

import pytest

from app import db, db_backend


def test_postgres_quote_revision_round_trip():
    if not db_backend.is_postgres_configured():
        pytest.skip("PostgreSQL integration environment is not configured")
    db.initialize()

    suffix = uuid4().hex
    original_id = "quote-" + suffix
    revision_id = "revision-" + suffix
    created_at = "2026-11-06T10:00:00+00:00"

    def record(identifier):
        return {
            "id": identifier,
            "company_id": None,
            "currency": "EUR",
            "subtotal": "100.00",
            "tax_rate": "0.20",
            "tax_amount": "20.00",
            "total": "120.00",
            "status": "draft",
            "created_at": created_at,
            "lines": [{
                "id": "line-" + identifier,
                "description": "PostgreSQL revision test",
                "quantity": "1",
                "unit_price": "100",
                "line_total": "100.00",
            }],
        }

    try:
        original = db.create_quotation(record(original_id))
        revision = db.create_quotation(record(revision_id), revision_of=original_id)
        assert revision["quote_group_number"] == original["quote_group_number"]
        assert revision["revision"] == 1
        assert revision["revision_of"] == original_id
        assert db.get_quotation(revision_id)["quote_number"].endswith("-R01")
    finally:
        db.delete_quotation(revision_id)
        db.delete_quotation(original_id)
