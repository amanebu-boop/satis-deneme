from app import db


def _quotation(quote_id: str, created_at: str = "2026-10-29T12:00:00+00:00") -> dict:
    return {
        "id": quote_id,
        "company_id": None,
        "currency": "TRY",
        "subtotal": "100.00",
        "discount_rate": "0",
        "discount_amount": "0",
        "tax_rate": "0.20",
        "tax_amount": "20.00",
        "total": "120.00",
        "status": "draft",
        "created_at": created_at,
        "lines": [
            {
                "id": f"line-{quote_id}",
                "description": "Test ürün",
                "quantity": "1",
                "unit_price": "100.00",
                "line_total": "100.00",
            }
        ],
    }


def test_new_quotes_receive_contiguous_yearly_numbers_and_revisions_keep_number(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()

    first = db.create_quotation(_quotation("quote-1"))
    second = db.create_quotation(_quotation("quote-2"))
    revision_one = db.create_quotation(_quotation("quote-3"), revision_of="quote-1")
    revision_two = db.create_quotation(_quotation("quote-4"), revision_of="quote-3")

    assert (first["quote_no"], first["revision_no"]) == ("TK-2026-0001", "R00")
    assert (second["quote_no"], second["revision_no"]) == ("TK-2026-0002", "R00")
    assert (revision_one["quote_no"], revision_one["revision_no"]) == ("TK-2026-0001", "R01")
    assert (revision_two["quote_no"], revision_two["revision_no"]) == ("TK-2026-0001", "R02")
    assert revision_one["revision_of"] == "quote-1"
    assert revision_two["revision_of"] == "quote-3"

    saved_first = db.get_quotation("quote-1")
    assert saved_first["revision_no"] == "R00"
    assert saved_first["quote_no"] == "TK-2026-0001"


def test_number_sequence_is_separate_per_year(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()

    old_year = db.create_quotation(_quotation("quote-2025", "2025-12-31T12:00:00+00:00"))
    new_year = db.create_quotation(_quotation("quote-2026", "2026-01-01T12:00:00+00:00"))

    assert old_year["quote_no"] == "TK-2025-0001"
    assert new_year["quote_no"] == "TK-2026-0001"
