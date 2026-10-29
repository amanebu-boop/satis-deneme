from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.pricing import QuoteLine
from fastapi import HTTPException
from openpyxl import load_workbook

from app import quote_excel


TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "Ersen_Makina_Teklif_Sablonu.xlsx"


@pytest.fixture(autouse=True)
def use_repository_template(monkeypatch):
    monkeypatch.setattr(quote_excel, "TEMPLATE_PATH", TEMPLATE)


def sample_quote(**overrides):
    quote = {
        "id": "12345678-1234-5678-1234-567812345678",
        "created_at": "2026-10-29T10:30:00+00:00",
        "currency": "EUR",
        "subtotal": "250.00",
        "tax_rate": 0.20,
        "tax_amount": "50.00",
        "total": "300.00",
        "lines": [
            {"description": "Deneme Makinesi", "quantity": "2", "unit_price": "100.00"},
            {"description": "Kurulum Hizmeti", "quantity": "1", "unit_price": "50.00"},
        ],
    }
    quote.update(overrides)
    return quote


def sample_company():
    return {
        "name": "Örnek Sanayi A.Ş.",
        "address": "Organize Sanayi Bölgesi, Konya",
        "tax_office": "Selçuklu",
        "tax_number": "1234567890",
        "authorized_people": ["Ayşe Yılmaz"],
        "phone_numbers": ["0332 123 45 67"],
        "email": "satinalma@example.test",
        "mersis_number": "MERSIS-EXAMPLE",
    }


def test_excel_output_preserves_template_and_fills_quote_fields():
    result = quote_excel.render_quote_excel(sample_quote(), sample_company())
    workbook = load_workbook(BytesIO(result), data_only=False)
    sheet = workbook["Teklif"]

    assert sheet["D13"].value == "ERS-12345678"
    assert sheet["D14"].value == datetime(2026, 10, 29, 0, 0)
    assert sheet["D15"].value == datetime(2026, 11, 13, 0, 0)
    assert sheet["J6"].value == "Örnek Sanayi A.Ş."
    assert sheet["J7"].value == "Organize Sanayi Bölgesi, Konya"
    assert sheet["J8"].value == "Selçuklu / 1234567890"
    assert sheet["J9"].value == "Ayşe Yılmaz"
    assert sheet["J10"].value == "0332 123 45 67 / satinalma@example.test"
    assert sheet["J11"].value in (None, "")
    assert sheet["D28"].value == "Deneme Makinesi"
    assert sheet["J28"].value == 2
    assert sheet["K28"].value == 100
    assert sheet["D22"].value in (None, "")
    assert sheet["D29"].value == "Kurulum Hizmeti"
    assert sheet["J29"].value == 1
    assert sheet["K29"].value == 50
    assert sheet["L28"].value == "=K28*J28"
    assert sheet["I44"].value == "=ara_toplam*20/100"
    assert sheet["I45"].value == "=ara_toplam+kdv_toplam"
    assert sheet["I46"].value == "üç yüz Avro"
    assert sheet["D49"].value == "Sipariş onayı ve avansın tahsilini takip eden ilk iş günü"

    workbook.close()


def test_excel_output_rejects_decimal_unit_price():
    quote = sample_quote(lines=[
        {"description": "Ondalıklı fiyat", "quantity": "1", "unit_price": "10.5"}
    ])
    with pytest.raises(HTTPException) as exc:
        quote_excel.render_quote_excel(quote, sample_company())
    assert exc.value.status_code == 422
    assert "tam sayı" in str(exc.value.detail).lower()


def test_quote_line_rejects_decimal_unit_price():
    with pytest.raises(ValidationError):
        QuoteLine(description="Ondalıklı fiyat", quantity=1, unit_price="10.5")

def test_excel_output_rejects_more_than_fifteen_lines():
    quote = sample_quote(lines=[
        {"description": f"Kalem {i}", "quantity": "1", "unit_price": "10"}
        for i in range(16)
    ])
    with pytest.raises(HTTPException) as exc:
        quote_excel.render_quote_excel(quote, sample_company())
    assert exc.value.status_code == 422
    assert "15" in str(exc.value.detail)


def test_amount_in_words_handles_turkish_number_groups():
    assert quote_excel._amount_in_words(__import__("decimal").Decimal("1234.50"), "EUR") == "bin iki yüz otuz dört Avro elli sent"
    assert quote_excel._amount_in_words(__import__("decimal").Decimal("0.00"), "TRY") == "sıfır Türk lirası"
