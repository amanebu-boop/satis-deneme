import pytest
from pydantic import ValidationError

from app.pricing import QuoteLine, calculate_quote


def test_quote_quantity_accepts_one_as_a_whole_number():
    line = QuoteLine(description="Deneme ürünü", quantity="1", unit_price="10")
    assert line.quantity == 1
    assert isinstance(line.quantity, int)


@pytest.mark.parametrize("quantity", ["0", "-1", "1.5", 1.5])
def test_quote_quantity_rejects_non_positive_or_fractional_values(quantity):
    with pytest.raises(ValidationError):
        QuoteLine(description="Deneme ürünü", quantity=quantity, unit_price="10")



def test_quote_calculation_uses_fixed_twenty_percent_vat_without_discount_fields():
    line = QuoteLine(description="Deneme ürünü", quantity=2, unit_price=10)
    result = calculate_quote([line], "EUR")

    assert result["subtotal"] == "20.00"
    assert result["tax_rate"] == "0.20"
    assert result["tax_amount"] == "4.00"
    assert result["total"] == "24.00"
    assert "discount_rate" not in result
    assert "discount_amount" not in result
