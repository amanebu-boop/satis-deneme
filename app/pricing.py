from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

CENT = Decimal("0.01")
FIXED_TAX_RATE = Decimal("0.20")


class QuoteLine(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(gt=0, le=999999999)
    unit_price: int = Field(ge=0, le=99999999)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_quote(lines: list[QuoteLine], currency: str) -> dict:
    """Calculate a quotation using the template's fixed 20% VAT."""
    if not lines:
        raise ValueError("At least one line is required")
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError("Currency must be a three-letter uppercase code")

    subtotal = sum(
        (Decimal(line.quantity) * Decimal(line.unit_price) for line in lines),
        Decimal("0"),
    )
    tax = subtotal * FIXED_TAX_RATE
    total = subtotal + tax
    return {
        "currency": currency,
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(money(Decimal(line.quantity) * Decimal(line.unit_price))),
            }
            for line in lines
        ],
        "subtotal": str(money(subtotal)),
        "tax_rate": str(FIXED_TAX_RATE),
        "tax_amount": str(money(tax)),
        "total": str(money(total)),
        "status": "calculated_not_approved",
        "note": "Draft calculation only. Verify currency and commercial terms before use.",
    }
