from fastapi.testclient import TestClient

from app.main import app
from app.meeting_audio import prepare_meeting_draft


class FakeResponses:
    def __init__(self, payload):
        import json
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        import json
        self.kwargs = kwargs
        return type("Response", (), {"output_text": json.dumps(self.payload, ensure_ascii=False), "usage": None})()


class FakeResponsesClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def test_prepare_meeting_draft_only_returns_catalogued_ids_and_flags_missing_data():
    company = {"id": "company-1", "name": "ABC Makina", "city": "Konya", "district": "Selçuklu", "tax_number": "private"}
    product = {
        "id": "product-1", "sku": "M-001", "name": "Çift Kafa Büküm Makinası",
        "description": "Makine", "currency": "EUR", "unit_price": "22000",
        "product_type": "machine", "parent_product_id": None,
    }
    payload = {
        "company_id": "company-1",
        "meeting_type": "unknown",
        "topic": "Makine görüşmesi",
        "notes": "ABC Makina çift kafa büküm makinesiyle ilgileniyor.",
        "product_lines": [
            {"product_id": "product-1", "quantity": 0, "mention": "çift kafa"},
            {"product_id": "made-up-id", "quantity": 1, "mention": "bilinmeyen ürün"},
        ],
        "unmatched_company": None,
        "unmatched_products": [],
        "questions": [],
    }
    client = FakeResponsesClient(payload)
    draft, response = prepare_meeting_draft(
        client, "gpt-5.5", "ABC Makina çift kafa büküm makinesiyle ilgileniyor.",
        [company], [product],
    )
    assert draft["company_id"] == "company-1"
    assert draft["meeting_type"] is None
    assert len(draft["product_lines"]) == 1
    assert draft["product_lines"][0]["product_id"] == "product-1"
    assert draft["product_lines"][0]["quantity"] == 0
    assert draft["product_lines"][0]["unit_price"] is None
    assert "bilinmeyen ürün" in draft["unmatched_products"]
    assert any("miktarı" in item for item in draft["questions"])
    assert any("görüşme türünü" in item.lower() for item in draft["questions"])
    sent = client.responses.kwargs["input"]
    assert "tax_number" not in sent
    assert "22000" not in sent
    assert response is not None


def test_prepare_meeting_draft_rejects_unknown_company_id():
    payload = {
        "company_id": "invented",
        "meeting_type": "phone",
        "topic": "Konu",
        "notes": "Görüşme notu",
        "product_lines": [],
        "unmatched_company": None,
        "unmatched_products": [],
        "questions": [],
    }
    client = FakeResponsesClient(payload)
    draft, _ = prepare_meeting_draft(client, "gpt-5.5", "Bir firma ile görüşme yapıldı.", [], [])
    assert draft["company_id"] is None
    assert any("Firma eşleşmesi doğrulanamadı" in item for item in draft["questions"])
