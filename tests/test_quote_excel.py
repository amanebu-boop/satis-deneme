from datetime import datetime
from io import BytesIO
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from app.pricing import QuoteLine
from fastapi import HTTPException
from openpyxl import load_workbook

from app import quote_excel
from app.quote_pdf import convert_excel_to_pdf
from pypdf import PdfReader


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



def test_template_excel_can_be_converted_to_pdf_when_libreoffice_is_installed():
    if not (shutil.which("libreoffice") or shutil.which("soffice")):
        pytest.skip("LibreOffice is not installed in this test environment")
    excel_content = quote_excel.render_quote_excel(sample_quote(), sample_company())
    pdf_content = convert_excel_to_pdf(excel_content)

    assert pdf_content.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf_content), strict=True)
    assert len(reader.pages) >= 1
    rendered_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "ERS-12345678" in rendered_text
    assert "Örnek Sanayi A.Ş." in rendered_text
    assert "Deneme Makinesi" in rendered_text
    assert len(reader.pages) >= 2
    second_page_text = reader.pages[1].extract_text() or ""
    first_content = next((line.strip() for line in second_page_text.splitlines() if line.strip()), "")
    assert first_content.startswith("7.")
    assert "GARANTİ" in second_page_text.upper()
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.2756) < 1.0
        assert abs(float(page.mediabox.height) - 841.8898) < 1.0


def test_pdf_fallback_uses_a4_and_starts_second_page_at_section_seven(monkeypatch):
    monkeypatch.setattr("app.quote_pdf.shutil.which", lambda _name: None)
    workbook = quote_excel.render_quote_excel(sample_quote(), sample_company())
    pdf = convert_excel_to_pdf(workbook)
    reader = PdfReader(BytesIO(pdf), strict=True)

    assert len(reader.pages) == 2
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.2756) < 1.0
        assert abs(float(page.mediabox.height) - 841.8898) < 1.0

    second_page_text = reader.pages[1].extract_text() or ""
    assert "7." in second_page_text[:100]
    assert "GARANTİ" in second_page_text.upper()


def test_pdf_renderer_uses_workbook_template_when_libreoffice_is_missing(monkeypatch):
    monkeypatch.setattr("app.quote_pdf.shutil.which", lambda _name: None)
    workbook = quote_excel.render_quote_excel(sample_quote(), sample_company())
    pdf = convert_excel_to_pdf(workbook)
    reader = PdfReader(BytesIO(pdf), strict=True)
    assert len(reader.pages) >= 1
    text = "\\n".join(page.extract_text() or "" for page in reader.pages)
    assert "ERS-12345678" in text
    assert "Örnek Sanayi A.Ş." in text
    assert "Deneme Makinesi" in text
    assert pdf.startswith(b"%PDF-")
