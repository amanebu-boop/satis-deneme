"""Generate an Ersen Makina Excel quotation from a saved draft without altering its template layout."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import warnings

from fastapi import HTTPException
from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "Ersen_Makina_Teklif_Sablonu.xlsx"
MAX_LINES = 15


def _first_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or value.get("full_name") or value.get("title") or "").strip()
    return ""


def _company_contact(company: dict) -> tuple[str, str]:
    people = company.get("authorized_people") or []
    person = _first_text(people[0]) if isinstance(people, list) and people else ""
    phones = company.get("phone_numbers") or []
    phone = _first_text(phones[0]) if isinstance(phones, list) and phones else ""
    return person, phone


def render_quote_excel(quote: dict, company: dict | None) -> bytes:
    if not TEMPLATE_PATH.is_file():
        raise HTTPException(status_code=503, detail="Excel teklif şablonu uygulama paketinde bulunamadı.")
    lines = quote.get("lines") or []
    if not lines:
        raise HTTPException(status_code=422, detail="Excel teklifi için en az bir ürün/hizmet satırı gerekli.")
    if len(lines) > MAX_LINES:
        raise HTTPException(status_code=422, detail=f"Bu teklif şablonu en fazla {MAX_LINES} kalem destekliyor.")
    if float(quote.get("discount_amount") or 0) != 0:
        raise HTTPException(status_code=422, detail="Erşen Makina şablonunda indirim bölümü bulunmadığı için indirimli teklifler Excel olarak oluşturulamaz. Önce indirim oranını sıfırlayın.")

    customer = company or {}
    contact, phone = _company_contact(customer)
    created_raw = str(quote.get("created_at") or "")[:10]
    try:
        quote_date = date.fromisoformat(created_raw)
    except ValueError:
        quote_date = date.today()
    try:
        validity_days = 15
        valid_until = quote_date + timedelta(days=validity_days)
        tax_rate = float(quote.get("tax_rate") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Teklif tarihi veya vergi oranı geçersiz.")

    # openpyxl preserves cell formatting and formulas. The source template includes
    # an Excel-only validation extension that openpyxl warns it cannot retain; suppress
    # only that known warning so it does not leak into server logs.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Data Validation extension is not supported")
        workbook = load_workbook(TEMPLATE_PATH, data_only=False)
    try:
        sheet = workbook["Teklif"]
        quote_number = "ERS-" + str(quote.get("id", ""))[:8].upper()
        sheet["D13"] = quote_number
        sheet["D14"] = quote_date
        sheet["D15"] = valid_until
        sheet["J14"] = validity_days
        sheet["J15"] = str(quote.get("currency") or "EUR").upper()

        sheet["J6"] = _first_text(customer.get("name")) or "Firma belirtilmedi"
        sheet["J7"] = _first_text(customer.get("address"))
        tax_office = _first_text(customer.get("tax_office"))
        tax_number = _first_text(customer.get("tax_number"))
        sheet["J8"] = " / ".join(value for value in (tax_office, tax_number) if value)
        sheet["J9"] = contact
        email = _first_text(customer.get("email"))
        sheet["J10"] = " / ".join(value for value in (phone, email) if value)
        sheet["J11"] = str(customer.get("mersis_number") or "")

        # Keep the supplied workbook's rows, formulas, styles, payment terms and
        # seller information intact; fill only the 15 supported quotation lines.
        for row in range(28, 43):
            index = row - 28
            if index >= len(lines):
                for cell in (f"C{row}", f"D{row}", f"J{row}", f"K{row}"):
                    sheet[cell] = None
                continue
            line = lines[index]
            sheet[f"C{row}"] = ""
            sheet[f"D{row}"] = str(line.get("description") or "")[:500]
            try:
                sheet[f"J{row}"] = float(line.get("quantity") or 0)
                sheet[f"K{row}"] = float(line.get("unit_price") or 0)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"Teklif kalemi {index + 1} için miktar veya birim fiyat geçersiz.")

        # The workbook intentionally has no discount row. Calculate tax using the
        # saved draft's rate instead of the template's original fixed 20% formula.
        sheet["I44"] = "=ara_toplam*" + format(tax_rate, ".8g")
        sheet["I45"] = "=ara_toplam+kdv_toplam"
        sheet["I46"] = "[Genel toplam yazıyla, " + str(quote.get("currency") or "EUR") + "]"
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.calculation.calcMode = "auto"
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
