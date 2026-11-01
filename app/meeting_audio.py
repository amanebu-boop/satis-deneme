"""Authenticated, non-persistent audio transcription for meeting capture."""
from __future__ import annotations

import os
import json
import hashlib
import time
from collections import deque
from threading import Lock
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app import db

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


class MeetingDraftRequest(BaseModel):
    transcript: str = Field(min_length=10, max_length=15000)


MEETING_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": ["string", "null"]},
        "meeting_type": {"type": "string", "enum": ["phone", "visit", "unknown"]},
        "topic": {"type": "string"},
        "notes": {"type": "string"},
        "product_lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_id": {"type": ["string", "null"]},
                    "quantity": {"type": "integer"},
                    "mention": {"type": "string"},
                },
                "required": ["product_id", "quantity", "mention"],
                "additionalProperties": False,
            },
        },
        "unmatched_company": {"type": ["string", "null"]},
        "unmatched_products": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "company_id", "meeting_type", "topic", "notes", "product_lines",
        "unmatched_company", "unmatched_products", "questions",
    ],
    "additionalProperties": False,
}


def prepare_meeting_draft(client: Any, model: str, transcript: str,
                          companies: list[dict[str, Any]], products: list[dict[str, Any]]) -> tuple[dict[str, Any], Any]:
    # Only the minimum company and catalogue fields needed for exact matching are sent.
    company_context = [
        {"id": item["id"], "name": item["name"], "city": item.get("city"), "district": item.get("district")}
        for item in companies
    ]
    product_context = [
        {"id": item["id"], "sku": item["sku"], "name": item["name"],
         "description": item.get("description"), "product_type": item.get("product_type", "machine"),
         "parent_product_id": item.get("parent_product_id")}
        for item in products
    ]
    response = client.responses.create(
        model=model,
        instructions=(
            "Sen Erşen Makina satış görüşmesi taslak yardımcısısın. Türkçe konuşma/not metninden yalnızca açıkça söylenen bilgileri çıkar. "
            "Firma ve ürünleri yalnızca verilen katalog kayıtlarıyla eşleştir; verilen ID'ler dışında ID üretme. "
            "Firma adı yoksa, birden fazla olası firma varsa veya eşleşme kesin değilse company_id null olsun ve unmatched_company alanını doldur. "
            "Ürün açıkça katalogdaki tek bir kayıtla eşleşmiyorsa product_id null olsun ve unmatched_products/ questions alanlarına yaz. "
            "Ürün miktarı belirtilmemişse 1 varsayma; quantity alanında 0 kullan ve soru ekle. "
            "Fiyat, indirim, teslimat tarihi, para birimi veya ticari taahhüt uydurma. Fiyatı modelden çıkarma; fiyatları kullanıcı formda kontrol eder. "
            "Notları anlamı koruyarak düzenle. Bu yalnızca taslaktır; hiçbir kayıt oluşturma veya değiştirme."
        ),
        input=json.dumps({
            "transcript": transcript,
            "companies": company_context,
            "products": product_context,
        }, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "meeting_capture_draft",
                "strict": True,
                "schema": MEETING_DRAFT_SCHEMA,
            }
        },
        max_output_tokens=1200,
    )
    parsed = json.loads(response.output_text)
    company_ids = {str(item["id"]) for item in companies}
    product_by_id = {str(item["id"]): item for item in products}
    company_id = parsed.get("company_id")
    if company_id is not None and str(company_id) not in company_ids:
        parsed["company_id"] = None
        parsed["questions"].append("Firma eşleşmesi doğrulanamadı; firmayı listeden seçin.")
    clean_lines = []
    for line in parsed.get("product_lines", []):
        product_id = line.get("product_id")
        product = product_by_id.get(str(product_id)) if product_id is not None else None
        quantity = line.get("quantity")
        if product is None:
            parsed["unmatched_products"].append(line.get("mention") or "Katalogda eşleşmeyen ürün")
            continue
        if type(quantity) is not int or quantity < 0 or quantity > 999999:
            parsed["questions"].append(f"{product['name']} için miktarı belirtin.")
            quantity = 0
        if quantity == 0:
            parsed["questions"].append(f"{product['name']} için miktarı belirtin.")
        clean_lines.append({
            "product_id": product["id"], "sku": product["sku"], "name": product["name"],
            "product_type": product.get("product_type", "machine"),
            "parent_product_id": product.get("parent_product_id"),
            "quantity": quantity, "unit_price": None, "currency": product["currency"],
        })
    parsed["product_lines"] = clean_lines
    parsed["meeting_type"] = parsed["meeting_type"] if parsed["meeting_type"] in {"phone", "visit"} else None
    if parsed["meeting_type"] is None:
        parsed["questions"].append("Görüşme türünü (telefon veya ziyaret) seçin.")
    if parsed.get("company_id") is None:
        parsed["questions"].append("Firma eşleşmedi; doğru firmayı listeden seçin.")
    parsed["topic"] = str(parsed.get("topic") or "Genel görüşme")[:200]
    parsed["notes"] = str(parsed.get("notes") or transcript)[:10000]
    return parsed, response


@router.post("/api/meetings/prepare")
def prepare_meeting_capture(payload: MeetingDraftRequest, request: Request) -> dict[str, Any]:
    from app.main import _require_browser_session, _require_csrf

    session = _require_browser_session(request)
    _require_csrf(request, session)
    _check_transcription_rate_limit(request.cookies.get("sales_session", ""))
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Görüşme taslağı hazırlamak için OpenAI API anahtarı sunucuda tanımlı değil.")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
        model = os.environ.get("OPENAI_MODEL", "gpt-5.5")
        companies = db.list_companies()
        products = db.list_products()
        draft, response = prepare_meeting_draft(client, model, payload.transcript.strip(), companies, products)
        try:
            from app import ai_usage
            session_hash = hashlib.sha256(request.cookies.get("sales_session", "").encode("utf-8")).hexdigest()
            ai_usage.record_response_usage(response, model, "meeting", session_hash)
        except Exception:
            pass
        return draft
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Görüşme taslağı hazırlanamadı. Metni kontrol edip tekrar deneyin.") from exc
