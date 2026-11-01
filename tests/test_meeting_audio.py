from fastapi.testclient import TestClient

from app.main import app
from app.meeting_audio import transcribe_audio


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
