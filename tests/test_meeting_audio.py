import json

import openai
import pytest
from fastapi.testclient import TestClient

from app import db
from app.company_sectors import COMPANY_SECTORS
from app.main import app
from app.meeting_audio import extract_meeting_capture


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"output_text": json.dumps(self.payload, ensure_ascii=False), "usage": None})()


class FakeOpenAI:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def capture_payload(*, company_id=None, company_name="ABC Makina", sector="Mobilya",
                    meeting_type="visit", product_id=None, quantity=2):
    return {
        "company": {
            "company_id": company_id,
            "name": company_name,
            "sector": sector,
            "authorized_people": ["Ayşe Yılmaz"],
            "phone_numbers": ["05551234567"],
            "city": "Konya",
            "district": "Selçuklu",
            "neighborhood": None,
            "street": None,
            "building_number": None,
            "postal_code": None,
            "address_extra": None,
            "website": None,
            "email": None,
            "notes": None,
        },
        "meeting": {
            "meeting_type": meeting_type,
            "topic": "Makine ihtiyacı",
            "notes": "Firma iki adet büküm makinesiyle ilgileniyor.",
            "product_lines": [
                {"product_id": product_id, "quantity": quantity, "mention": "Büküm makinesi"}
            ] if product_id else [],
        },
        "unmatched_products": [],
    }


def test_company_sectors_are_canonical_and_exclude_steel_door():
    assert "Çelik Kapı" not in COMPANY_SECTORS
    assert len(COMPANY_SECTORS) == 10
    assert "Otomotiv" in COMPANY_SECTORS
    assert "Enjeksiyon Plastik Kalıpları" in COMPANY_SECTORS
    assert "Sac Kalıpları" in COMPANY_SECTORS


def test_extract_new_company_and_meeting_only_uses_explicit_catalogue_data():
    product = {
        "id": "product-1", "sku": "M-001", "name": "Çift Kafa Büküm Makinası",
        "description": "Makine", "currency": "EUR", "unit_price": "22000",
        "product_type": "machine", "parent_product_id": None,
    }
    client = FakeOpenAI(capture_payload(product_id="product-1"))
    extracted, response = extract_meeting_capture(
        client, "gpt-test", "ABC Makina Konya'da mobilya üretir. İki adet çift kafa büküm makinesi için ziyaret yapıldı.",
        [], [product],
    )
    assert extracted["company_id"] is None
    assert extracted["company_name"] == "ABC Makina"
    assert extracted["sector"] == "Mobilya"
    assert extracted["is_new_company"] is True
    assert extracted["meeting_type"] == "visit"
    assert extracted["product_lines"][0]["quantity"] == 2
    assert extracted["product_lines"][0]["unit_price"] == ""
    sent = client.responses.kwargs["input"]
    assert "22000" not in sent
    assert "tax_number" not in sent
    assert response is not None


def test_extract_existing_company_does_not_change_a_known_sector():
    company = {"id": "company-1", "name": "ABC Makina", "sector": "Çelik Eşya", "city": "Konya"}
    payload = capture_payload(company_id="company-1", sector="Mobilya")
    extracted, _ = extract_meeting_capture(
        FakeOpenAI(payload), "gpt-test", "ABC Makina ile telefon görüşmesi yapıldı.", [company], []
    )
    assert extracted["company_id"] == "company-1"
    assert extracted["sector"] == "Çelik Eşya"
    assert extracted["is_new_company"] is False


@pytest.mark.parametrize("sector,meeting_type,expected", [
    (None, "visit", "sektörü"),
    ("Mobilya", "unknown", "Görüşme türü"),
    ("Çelik Kapı", "visit", "sektörü"),
])
def test_capture_does_not_save_when_required_company_or_meeting_data_is_missing(sector, meeting_type, expected):
    payload = capture_payload(sector=sector, meeting_type=meeting_type)
    extracted, _ = extract_meeting_capture(
        FakeOpenAI(payload), "gpt-test", "ABC Makina hakkında görüşme notu.", [], []
    )
    assert extracted["questions"]
    assert any(expected.lower() in question.lower() for question in extracted["questions"])


def test_invalid_model_company_id_is_not_trusted():
    payload = capture_payload(company_id="invented")
    extracted, _ = extract_meeting_capture(
        FakeOpenAI(payload), "gpt-test", "ABC Makina ile ziyaret yapıldı.", [], []
    )
    assert extracted["company_id"] is None
    assert extracted["is_new_company"] is True


def test_product_without_quantity_is_not_added_but_meeting_can_be_created():
    product = {
        "id": "product-1", "sku": "M-001", "name": "Büküm Makinası",
        "currency": "EUR", "unit_price": "22000", "product_type": "machine",
    }
    payload = capture_payload(product_id="product-1", quantity=0)
    extracted, _ = extract_meeting_capture(
        FakeOpenAI(payload), "gpt-test", "ABC Makina ile ziyaret yapıldı.", [], [product]
    )
    assert extracted["product_lines"] == []
    assert any("miktar belirtilmedi" in warning for warning in extracted["warnings"])


def test_company_and_meeting_are_created_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()
    company = {
        "id": "company-1", "name": "ABC Makina", "sector": "Mobilya",
        "authorized_people": [], "phone_numbers": [], "city": "Konya",
    }
    meeting = {
        "id": "meeting-1", "company_id": "company-1", "meeting_date": "2026-11-01",
        "meeting_type": "visit", "topic": "Makine ihtiyacı", "notes": "Görüşme notu",
        "product_lines": [],
    }
    with db.connect() as connection:
        connection.execute("CREATE TRIGGER fail_meeting BEFORE INSERT ON meetings BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
    with pytest.raises(Exception):
        db.create_company_and_meeting(company, meeting)
    assert db.get_company("company-1") is None
    assert db.list_meetings() == []


def _login(client):
    login = client.post(
        "/api/login", json={"password": "a-secure-test-password-123"},
        headers={"Origin": "https://testserver"},
    )
    assert login.status_code == 200
    return {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}


def test_capture_endpoint_creates_new_company_and_meeting(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake = FakeOpenAI(capture_payload())
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: fake)
    with TestClient(app, base_url="https://testserver") as client:
        headers = _login(client)
        response = client.post(
            "/api/meetings/capture", headers=headers,
            json={"transcript": "ABC Makina Konya'da mobilya üretir. Ziyaret yapıldı."},
        )
        assert response.status_code == 201
        result = response.json()
        assert result["created"] is True
        assert result["company"]["created"] is True
        assert result["company"]["sector"] == "Mobilya"
        companies = client.get("/api/companies", headers=headers).json()
        meetings = client.get("/api/meetings", headers=headers).json()
        assert len(companies) == 1 and companies[0]["sector"] == "Mobilya"
        assert len(meetings) == 1 and meetings[0]["company_id"] == companies[0]["id"]


def test_capture_endpoint_reuses_existing_company_and_does_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    payload = capture_payload(company_id="existing-company", sector="Mobilya")
    fake = FakeOpenAI(payload)
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: fake)
    with TestClient(app, base_url="https://testserver") as client:
        headers = _login(client)
        company = client.post("/api/companies", headers=headers, json={"name": "ABC Makina", "sector": "Çelik Eşya"})
        assert company.status_code == 201
        payload["company"]["company_id"] = company.json()["id"]
        fake.responses.payload = payload
        response = client.post("/api/meetings/capture", headers=headers, json={"transcript": "ABC Makina ile ziyaret yapıldı."})
        assert response.status_code == 201
        assert response.json()["company"]["created"] is False
        assert len(client.get("/api/companies", headers=headers).json()) == 1
        assert len(client.get("/api/meetings", headers=headers).json()) == 1


def test_capture_endpoint_requires_auth_and_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app, base_url="https://testserver") as client:
        unauthorized = client.post("/api/meetings/capture", json={"transcript": "ABC Makina ile görüşme notu."})
        assert unauthorized.status_code == 401
        headers = _login(client)
        unavailable = client.post("/api/meetings/capture", headers=headers, json={"transcript": "ABC Makina ile görüşme notu."})
        assert unavailable.status_code == 503


def test_audio_transcription_endpoint_is_not_registered():
    assert not any(getattr(route, "path", None) == "/api/meetings/transcribe" for route in app.routes)
