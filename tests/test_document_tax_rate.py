from app.documents import render_quotation_html


def test_document_displays_tax_rate_as_percentage():
    quotation = {
        "id": "test-quote",
        "created_at": "2026-10-29T00:00:00+00:00",
        "currency": "EUR",
        "lines": [{"description": "Deneme", "quantity": "1", "unit_price": "20000", "line_total": "20000"}],
        "discount_rate": "0.0",
        "discount_amount": "0.00",
        "tax_rate": "0.2",
        "tax_amount": "4000.00",
        "subtotal": "20000.00",
        "total": "24000.00",
    }
    html = render_quotation_html(quotation, {"name": "Deneme firması"})
    assert "KDV/vergi (%20.0)" in html
    assert "KDV/vergi (%0.2)" not in html
