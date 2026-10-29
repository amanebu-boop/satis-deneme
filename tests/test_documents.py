from app.documents import render_quotation_html


def test_quotation_document_renders_tax_and_final_total():
    html = render_quotation_html(
        {
            "id": "Q-001",
            "created_at": "2026-10-29T10:00:00+00:00",
            "currency": "TRY",
            "lines": [{"description": "Danışmanlık", "quantity": "2", "unit_price": "10.00", "line_total": "20.00"}],
            "subtotal": "20.00",
            "tax_rate": "0.2",
            "tax_amount": "4.00",
            "total": "24.00",
        },
        {"name": "Örnek Firma"},
    )

    assert "Ara toplam" in html
    assert "KDV/vergi" in html
    assert "Genel toplam" in html
