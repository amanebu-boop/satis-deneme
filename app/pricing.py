from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

CENT = Decimal("0.01")

class QuoteLine(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(gt=0, le=999999999)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=4)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_quote(lines: list[QuoteLine], currency: str, tax_rate: float = 0, discount_rate: float = 0) -> dict:
    """Calculate totals deterministically; this function does not validate local tax law."""
    if not lines:
        raise ValueError("At least one line is required")
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError("Currency must be a three-letter uppercase code")
    if not (0 <= tax_rate <= 1) or not (0 <= discount_rate <= 1):
        raise ValueError("Tax and discount rates must be between 0 and 1")

    subtotal = sum((line.quantity * line.unit_price for line in lines), Decimal("0"))
    discount = subtotal * Decimal(str(discount_rate))
    taxable = subtotal - discount
    tax = taxable * Decimal(str(tax_rate))
    total = taxable + tax
    return {
        "currency": currency,
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(money(line.unit_price)),
                "line_total": str(money(line.quantity * line.unit_price)),
            }
            for line in lines
        ],
        "subtotal": str(money(subtotal)),
        "discount_rate": str(discount_rate),
        "discount_amount": str(money(discount)),
        "tax_rate": str(tax_rate),
        "tax_amount": str(money(tax)),
        "total": str(money(total)),
        "status": "calculated_not_approved",
        "note": "Draft calculation only. Verify currency, tax rules, discounts, and rounding policy before commercial use.",
    }
