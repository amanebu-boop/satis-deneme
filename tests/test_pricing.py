from decimal import Decimal

import pytest

from app.pricing import QuoteLine, calculate_quote


def test_quote_calculates_tax_on_full_subtotal():
    result = calculate_quote(
        [QuoteLine(description="Danışmanlık", quantity=Decimal("2"), unit_price=Decimal("10"))],
        "TRY",
        tax_rate=0.20,
    )

    assert result["subtotal"] == "20.00"
    assert result["tax_amount"] == "4.00"
    assert result["total"] == "24.00"
    assert "discount_rate" not in result
    assert "discount_amount" not in result


def test_quote_without_tax_keeps_subtotal_as_total():
    result = calculate_quote(
        [QuoteLine(description="Kurulum", quantity=Decimal("1"), unit_price=Decimal("125.50"))],
        "TRY",
    )

    assert result["subtotal"] == "125.50"
    assert result["tax_amount"] == "0.00"
    assert result["total"] == "125.50"


@pytest.mark.parametrize("tax_rate", [-0.01, 1.01])
def test_quote_rejects_invalid_tax_rate(tax_rate):
    with pytest.raises(ValueError, match="Tax rate"):
        calculate_quote(
            [QuoteLine(description="Hizmet", quantity=Decimal("1"), unit_price=Decimal("10"))],
            "TRY",
            tax_rate=tax_rate,
        )


def test_quote_requires_at_least_one_line():
    with pytest.raises(ValueError, match="At least one line"):
        calculate_quote([], "TRY")
