from fastapi.testclient import TestClient

from app.main import app
from app.meeting_audio import prepare_meeting_draft, transcribe_audio


class FakeTranscriptions:
    def __init__(self, result="Müşteri çift kafa büküm makinesiyle ilgileniyor."):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.result


class FakeAudioClient:
    def __init__(self):
        self.audio = type("Audio", (), {})()
        self.audio.transcriptions = FakeTranscriptions()


def test_transcribe_audio_uses_configured_model_and_returns_text():
    client = FakeAudioClient()
    text = transcribe_audio(client, "meeting.webm", b"audio-bytes", "audio/webm", "gpt-4o-mini-transcribe")
    assert text == "Müşteri çift kafa büküm makinesiyle ilgileniyor."
    assert client.audio.transcriptions.kwargs == {
        "model": "gpt-4o-mini-transcribe",
        "file": ("meeting.webm", b"audio-bytes", "audio/webm"),
        "response_format": "text",
    }


def test_transcribe_audio_rejects_empty_transcript():
    client = FakeAudioClient()
    client.audio.transcriptions.result = "   "
    try:
        transcribe_audio(client, "meeting.wav", b"audio-bytes", "audio/wav", "gpt-4o-mini-transcribe")
    except ValueError as exc:
        assert "metin çıkarılamadı" in str(exc)
    else:
        raise AssertionError("Empty transcript must be rejected")


def _login(client):
    login = client.post(
        "/api/login",
        json={"password": "a-secure-test-password-123"},
        headers={"Origin": "https://testserver"},
    )
    assert login.status_code == 200
    return {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}


def test_meeting_audio_transcription_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/meetings/transcribe",
            files={"file": ("meeting.webm", b"audio", "audio/webm")},
        )
    assert response.status_code == 401


def test_meeting_audio_transcription_rejects_unsupported_type(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        headers = _login(client)
        response = client.post(
            "/api/meetings/transcribe",
            headers=headers,
            files={"file": ("meeting.exe", b"not-audio", "application/octet-stream")},
        )
    assert response.status_code == 415


def test_meeting_audio_transcription_requires_server_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app, base_url="https://testserver") as client:
        headers = _login(client)
        response = client.post(
            "/api/meetings/transcribe",
            headers=headers,
            files={"file": ("meeting.webm", b"audio", "audio/webm")},
        )
    assert response.status_code == 503
    assert "API anahtarı" in response.json()["detail"]


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
