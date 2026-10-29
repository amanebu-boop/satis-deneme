import pytest
from pydantic import ValidationError

from app.pricing import QuoteLine


def test_quote_quantity_accepts_one_as_a_whole_number():
    line = QuoteLine(description="Deneme ürünü", quantity="1", unit_price="10")
    assert line.quantity == 1
    assert isinstance(line.quantity, int)


@pytest.mark.parametrize("quantity", ["0", "-1", "1.5", 1.5])
def test_quote_quantity_rejects_non_positive_or_fractional_values(quantity):
    with pytest.raises(ValidationError):
        QuoteLine(description="Deneme ürünü", quantity=quantity, unit_price="10")
