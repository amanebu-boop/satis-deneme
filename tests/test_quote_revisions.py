from app import db


def _quote(quote_id: str, created_at: str = "2026-11-06T10:00:00+00:00") -> dict:
    return {
        "id": quote_id,
        "company_id": None,
        "currency": "EUR",
        "subtotal": "100.00",
        "tax_rate": "0.20",
        "tax_amount": "20.00",
        "total": "120.00",
        "status": "draft",
        "created_at": created_at,
        "lines": [{
            "id": f"line-{quote_id}",
            "description": "Test makine",
            "quantity": "1",
            "unit_price": "100",
            "line_total": "100.00",
        }],
    }


def test_quote_revisions_share_group_number_and_preserve_previous_versions(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()

    original = db.create_quotation(_quote("quote-original"))
    revision_one = db.create_quotation(_quote("quote-revision-1"), revision_of=original["id"])
    revision_two = db.create_quotation(_quote("quote-revision-2"), revision_of=revision_one["id"])

    assert original["quote_number"] == "ERS-2026-0001"
    assert original["quote_group_number"] == "ERS-2026-0001"
    assert original["revision"] == 0
    assert original["revision_of"] is None

    assert revision_one["quote_number"] == "ERS-2026-0001-R01"
    assert revision_one["quote_group_number"] == original["quote_group_number"]
    assert revision_one["revision"] == 1
    assert revision_one["revision_of"] == original["id"]

    assert revision_two["quote_number"] == "ERS-2026-0001-R02"
    assert revision_two["quote_group_number"] == original["quote_group_number"]
    assert revision_two["revision"] == 2
    assert revision_two["revision_of"] == revision_one["id"]

    saved_original = db.get_quotation(original["id"])
    assert saved_original["revision"] == 0
    assert saved_original["total"] == "120.00"
    assert db.get_quotation(revision_one["id"])["total"] == "120.00"
    assert {item["id"] for item in db.list_quotations()} == {
        original["id"], revision_one["id"], revision_two["id"]
    }


def test_revision_rejects_unknown_source(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()

    import pytest
    with pytest.raises(ValueError, match="Source quotation not found"):
        db.create_quotation(_quote("orphan-revision"), revision_of="missing-source")
