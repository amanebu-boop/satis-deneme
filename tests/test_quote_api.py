import pytest
from pydantic import ValidationError

from app.main import QuoteRequest


def test_quote_api_rejects_removed_discount_field():
    with pytest.raises(ValidationError):
        QuoteRequest(
            currency="TRY",
            lines=[{"description": "Hizmet", "quantity": "1", "unit_price": "10"}],
            discount_rate=0.1,
        )
