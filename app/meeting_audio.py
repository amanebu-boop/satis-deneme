"""Authenticated, non-persistent audio transcription for meeting capture."""
from __future__ import annotations

import os
import hashlib
import time
from collections import deque
from threading import Lock
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter()
_rate_lock = Lock()
_rate_events: dict[str, deque[float]] = {}
MAX_REQUESTS_PER_MINUTE = 5
MAX_AUDIO_BYTES = 25 * 1024 * 1024
TRANSCRIPTION_MODEL_DEFAULT = "gpt-4o-mini-transcribe"
ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg",
    "audio/mp4", "audio/m4a", "audio/mpga",
}
ALLOWED_AUDIO_SUFFIXES = {".webm", ".wav", ".mp3", ".mp4", ".m4a", ".mpga"}


class TranscriptionResponse(BaseModel):
    text: str


def _check_transcription_rate_limit(session_token: str) -> None:
    key = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    now = time.monotonic()
    with _rate_lock:
        events = _rate_events.setdefault(key, deque())
        while events and now - events[0] >= 60:
            events.popleft()
        if len(events) >= MAX_REQUESTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Bir dakika içinde en fazla 5 ses dönüştürme isteği gönderilebilir.")
        events.append(now)
        if len(_rate_events) > 2048:
            for old_key in list(_rate_events):
                old_events = _rate_events[old_key]
                while old_events and now - old_events[0] >= 60:
                    old_events.popleft()
                if not old_events:
                    _rate_events.pop(old_key, None)


def transcribe_audio(client: Any, filename: str, content: bytes, content_type: str, model: str) -> str:
    result = client.audio.transcriptions.create(
        model=model,
        file=(filename, content, content_type),
        response_format="text",
    )
    transcript = result if isinstance(result, str) else getattr(result, "text", "")
    transcript = str(transcript or "").strip()
    if not transcript:
        raise ValueError("Ses kaydından metin çıkarılamadı")
    return transcript


@router.post("/api/meetings/transcribe", response_model=TranscriptionResponse)
async def transcribe_meeting_audio(request: Request, file: UploadFile = File(...)) -> TranscriptionResponse:
    # Import lazily to avoid a circular import with app.main's session helpers.
    from app.main import _require_browser_session, _require_csrf

    session = _require_browser_session(request)
    _require_csrf(request, session)
    _check_transcription_rate_limit(request.cookies.get("sales_session", ""))
    filename = Path(file.filename or "meeting-audio").name
    suffix = Path(filename).suffix.lower()
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES and content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Desteklenmeyen ses biçimi. WebM, WAV, MP3, MP4 veya M4A yükleyin.")
    try:
        audio_bytes = await file.read(MAX_AUDIO_BYTES + 1)
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Ses dosyası boş.")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Ses dosyası 25 MB sınırını aşamaz.")
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(status_code=503, detail="Ses yazıya dönüştürme için OpenAI API anahtarı sunucuda tanımlı değil.")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
            transcript = transcribe_audio(
                client, filename, audio_bytes,
                content_type or "application/octet-stream",
                os.environ.get("OPENAI_TRANSCRIPTION_MODEL", TRANSCRIPTION_MODEL_DEFAULT),
            )
        except HTTPException:
            raise
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="OpenAI Python paketi kurulu değil.") from exc
        except Exception as exc:
            # Do not expose provider errors, file content, or credentials.
            raise HTTPException(status_code=502, detail="Ses yazıya dönüştürülemedi. Dosyayı kontrol edip tekrar deneyin.") from exc
        return TranscriptionResponse(text=transcript)
    finally:
        await file.close()
