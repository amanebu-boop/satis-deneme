"""Generate an Ersen Makina Excel quotation from a saved draft without altering its template layout."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
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


def _number_words(value: int) -> str:
    ones = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
    tens = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
    scales = ["", "bin", "milyon", "milyar", "trilyon"]
    if value == 0:
        return "sıfır"
    groups = []
    while value:
        groups.append(value % 1000)
        value //= 1000
    words = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        hundreds, remainder = divmod(group, 100)
        part = []
        if hundreds:
            if hundreds > 1:
                part.append(ones[hundreds])
            part.append("yüz")
        ten, one = divmod(remainder, 10)
        if ten:
            part.append(tens[ten])
        if one:
            part.append(ones[one])
        if index == 1 and group == 1:
            words.append("bin")
        else:
            words.extend(part)
            if scales[index]:
                words.append(scales[index])
    return " ".join(words)


def _amount_in_words(amount: Decimal, currency: str) -> str:
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = int(amount)
    fraction = int((amount - Decimal(whole)) * 100)
    currency_names = {"EUR": ("Avro", "sent"), "TRY": ("Türk lirası", "kuruş"), "USD": ("ABD doları", "sent")}
    unit, minor = currency_names.get(currency, (currency, "alt birim"))
    result = f"{_number_words(whole)} {unit}"
    if fraction:
        result += f" {_number_words(fraction)} {minor}"
    return result


def money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def render_quote_excel(quote: dict, company: dict | None) -> bytes:
    if not TEMPLATE_PATH.is_file():
        raise HTTPException(status_code=503, detail="Excel teklif şablonu uygulama paketinde bulunamadı.")
    lines = quote.get("lines") or []
    if not lines:
        raise HTTPException(status_code=422, detail="Excel teklifi için en az bir ürün/hizmet satırı gerekli.")
    if len(lines) > MAX_LINES:
        raise HTTPException(status_code=422, detail=f"Bu teklif şablonu en fazla {MAX_LINES} kalem destekliyor.")

    customer = company or {}
    contact, phone = _company_contact(customer)
    created_raw = str(quote.get("created_at") or "")[:10]
    try:
        quote_date = date.fromisoformat(created_raw)
    except ValueError:
        quote_date = date.today()
    validity_days = 15
    valid_until = quote_date + timedelta(days=validity_days)

    # Keep the supplied workbook's structure and formulas; only populate quote data.
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
        sheet["J11"] = ""

        descriptions = [str(line.get("description") or "").strip() for line in lines]
        sheet["B18"] = "Teklif kapsamında aşağıdaki ürün ve hizmetler sunulmaktadır: " + "; ".join(item for item in descriptions if item)
        sheet["D21"] = "; ".join(item for item in descriptions if item)
        sheet["D22"] = ""
        sheet["D23"] = ""
        sheet["B80"] = ""

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
                quantity = int(str(line.get("quantity") or 0))
                raw_price = Decimal(str(line.get("unit_price") or 0))
                if raw_price != raw_price.to_integral_value():
                    raise ValueError("Birim fiyat tam sayı olmalıdır.")
                unit_price = int(raw_price)
                if quantity <= 0 or unit_price < 0:
                    raise ValueError("Miktar veya birim fiyat aralık dışında.")
                sheet[f"J{row}"] = quantity
                sheet[f"K{row}"] = unit_price
            except (TypeError, ValueError, ArithmeticError):
                raise HTTPException(
                    status_code=422,
                    detail=f"Teklif kalemi {index + 1} için miktar ve birim fiyat tam sayı olmalıdır; birim fiyat sıfır veya pozitif olmalıdır.",
                )

        # Do not overwrite I44/I45: the template already contains the VAT and total formulas.
        currency = str(quote.get("currency") or "EUR").upper()
        subtotal = sum(
            (Decimal(str(line.get("quantity") or 0)) * Decimal(str(line.get("unit_price") or 0)) for line in lines),
            Decimal("0"),
        )
        total = (subtotal * Decimal("1.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sheet["I46"] = _amount_in_words(total, currency)
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.calculation.calcMode = "auto"
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
