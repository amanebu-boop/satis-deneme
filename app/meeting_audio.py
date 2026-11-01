"""Authenticated AI capture that creates a company and meeting from typed notes."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import db, agent_foundation
from app.company_sectors import COMPANY_SECTORS, is_valid_company_sector

router = APIRouter()
_rate_lock = Lock()
_rate_events: dict[str, deque[float]] = {}
MAX_REQUESTS_PER_MINUTE = 5


def _check_meeting_ai_rate_limit(session_token: str) -> None:
    key = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    now = time.monotonic()
    with _rate_lock:
        events = _rate_events.setdefault(key, deque())
        while events and now - events[0] >= 60:
            events.popleft()
        if len(events) >= MAX_REQUESTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Bir dakika içinde en fazla 5 yapay zekâ kayıt isteği gönderilebilir.")
        events.append(now)
        if len(_rate_events) > 2048:
            for old_key in list(_rate_events):
                old_events = _rate_events[old_key]
                while old_events and now - old_events[0] >= 60:
                    old_events.popleft()
                if not old_events:
                    _rate_events.pop(old_key, None)


class MeetingCaptureRequest(BaseModel):
    transcript: str = Field(min_length=10, max_length=15000)


MEETING_CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {
            "type": "object",
            "properties": {
                "company_id": {"type": ["string", "null"]},
                "name": {"type": ["string", "null"]},
                "sectors": {"type": "array", "items": {"type": "string", "enum": COMPANY_SECTORS}},
                "authorized_people": {"type": "array", "items": {"type": "string"}},
                "phone_numbers": {"type": "array", "items": {"type": "string"}},
                "city": {"type": ["string", "null"]},
                "district": {"type": ["string", "null"]},
                "neighborhood": {"type": ["string", "null"]},
                "street": {"type": ["string", "null"]},
                "building_number": {"type": ["string", "null"]},
                "postal_code": {"type": ["string", "null"]},
                "address_extra": {"type": ["string", "null"]},
                "website": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "tax_office": {"type": ["string", "null"]},
                "tax_number": {"type": ["string", "null"]},
                "mersis_number": {"type": ["string", "null"]},
                "notes": {"type": ["string", "null"]},
            },
            "required": [
                "company_id", "name", "sectors", "authorized_people", "phone_numbers",
                "city", "district", "neighborhood", "street", "building_number",
                "postal_code", "address_extra", "website", "email", "tax_office", "tax_number", "mersis_number", "notes",
            ],
            "additionalProperties": False,
        },
        "meeting": {
            "type": "object",
            "properties": {
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
            },
            "required": ["meeting_type", "topic", "notes", "product_lines"],
            "additionalProperties": False,
        },
        "unmatched_products": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["company", "meeting", "unmatched_products"],
    "additionalProperties": False,
}


def _normalized_company_name(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _candidate_score(item: dict[str, Any], transcript_tokens: set[str], fields: tuple[str, ...]) -> int:
    values = " ".join(str(item.get(field) or "") for field in fields).casefold()
    tokens = {token for token in __import__("re").findall(r"[\w-]+", values, flags=__import__("re").UNICODE) if len(token) > 1}
    return len(tokens & transcript_tokens)


def _relevant_candidates(
    items: list[dict[str, Any]], transcript: str, fields: tuple[str, ...], limit: int
) -> list[dict[str, Any]]:
    import re
    query_tokens = {token for token in re.findall(r"[\w-]+", transcript.casefold(), flags=re.UNICODE) if len(token) > 1}
    ranked = [(score, index, item) for index, item in enumerate(items)
              if (score := _candidate_score(item, query_tokens, fields)) > 0]
    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for _, _, item in ranked[:limit]]


def extract_meeting_capture(
    client: Any,
    model: str,
    transcript: str,
    companies: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> tuple[dict[str, Any], Any]:
    # Send only transcript-relevant candidates to the model. Full records remain
    # server-side for validating any IDs returned by the model.
    company_candidates = _relevant_candidates(companies, transcript, ("name", "city", "district"), 12)
    product_candidates = _relevant_candidates(products, transcript, ("sku", "name", "description"), 20)
    # Keep directly related parent/child options so a matched machine retains its options.
    selected_ids = {str(item["id"]) for item in product_candidates}
    for item in products:
        if str(item.get("parent_product_id") or "") in selected_ids:
            selected_ids.add(str(item["id"]))
        if str(item["id"]) in selected_ids and item.get("parent_product_id"):
            selected_ids.add(str(item["parent_product_id"]))
    product_candidates = [item for item in products if str(item["id"]) in selected_ids][:30]
    company_context = [
        {"id": item["id"], "name": item["name"], "sectors": item.get("sectors") or ([item["sector"]] if item.get("sector") else []),
         "city": item.get("city"), "district": item.get("district")}
        for item in company_candidates
    ]
    product_context = [
        {"id": item["id"], "sku": item["sku"], "name": item["name"],
         "description": item.get("description"), "product_type": item.get("product_type", "machine"),
         "parent_product_id": item.get("parent_product_id")}
        for item in product_candidates
    ]
    response = client.responses.create(
        model=model,
        instructions=(
            "Sen Erşen Makina'nın satış görüşmesi kayıt yardımcısısın. Türkçe metinden yalnızca açıkça belirtilen firma ve görüşme bilgilerini çıkar. "
            "Firma kaydında şirket unvanını ve sektörlerini belirle. Metinde açıkça belirtilen birden fazla sektör varsa hepsini seç; yalnızca verilen sektör listesini kullan. "
            "Sektörleri ancak metindeki firmanın açık faaliyet tanımına dayanarak eşleştir; belirsizse boş liste bırak. Çelik Kapı sektörü bu sistemde yoktur. "
            "Firma listesinde tam olarak eşleşen kayıt varsa yalnızca o kaydın ID'sini seç; benzer isimli firmaları aynı sayma. "
            "Yeni firma için company_id null, name metinde açıkça geçen firma adı olsun. Adres, telefon, e-posta, yetkili, web sitesi ve diğer alanları yalnızca metinde açıkça varsa doldur; uydurma. "
            "Görüşme türü açıkça telefon veya yüz yüze ziyaret olarak anlaşılmıyorsa unknown kullan. Konuyu ve notları metne sadık kalarak düzenle. "
            "Ürünleri yalnızca ürün kataloğundaki ID'lerle eşleştir. Miktar açıkça söylenmemişse 0 yaz. "
            "Fiyat, indirim, para birimi, teslimat tarihi veya ticari taahhüt üretme. Sistem bu metni kullanarak firma ve görüşme kaydını oluşturacak; eksik zorunlu bilgiyi null/unknown bırak."
        ),
        input=json.dumps({
            "transcript": transcript,
            "allowed_company_sectors": COMPANY_SECTORS,
            "existing_companies": company_context,
            "product_catalog": product_context,
        }, ensure_ascii=False),
        text={"format": {"type": "json_schema", "name": "meeting_capture", "strict": True, "schema": MEETING_CAPTURE_SCHEMA}},
        max_output_tokens=1800,
    )
    parsed = json.loads(response.output_text)
    company_data = parsed.get("company") or {}
    meeting_data = parsed.get("meeting") or {}
    company_by_id = {str(item["id"]): item for item in companies}
    product_by_id = {str(item["id"]): item for item in products}
    company_id = company_data.get("company_id")
    existing = company_by_id.get(str(company_id)) if company_id is not None else None
    invalid_company_id = company_id is not None and existing is None
    if invalid_company_id:
        company_data["company_id"] = None
    company_name = str(company_data.get("name") or "").strip()
    ambiguous_company_match = False
    company_match_conflict = False
    if existing is None and company_name:
        matches = [item for item in companies if _normalized_company_name(item.get("name")) == _normalized_company_name(company_name)]
        if len(matches) == 1:
            existing = matches[0]
        elif len(matches) > 1:
            ambiguous_company_match = True
    if existing is not None and company_name and _normalized_company_name(company_name) != _normalized_company_name(existing.get("name")):
        company_match_conflict = True
        existing = None
    questions: list[str] = []
    if ambiguous_company_match:
        questions.append("Aynı unvana sahip birden fazla firma bulundu. Doğru firmayı netleştirin.")
    if company_match_conflict:
        questions.append("Metindeki firma adı eşleşen kayıtla çelişiyor. Firma adını netleştirin.")
    if existing is None and not company_name:
        questions.append("Firma unvanı metinde bulunamadı. Firma adını belirtin.")
    existing_sectors = (existing.get("sectors") or ([existing["sector"]] if existing.get("sector") else [])) if existing else []
    sectors = existing_sectors or company_data.get("sectors") or []
    if not isinstance(sectors, list):
        sectors = []
    sectors = list(dict.fromkeys(item.strip() for item in sectors if isinstance(item, str) and is_valid_company_sector(item.strip())))
    if not sectors:
        questions.append("Firma sektörü belirlenemedi. Firma kaydını oluşturmak için en az bir sektör belirtin.")
    meeting_type = meeting_data.get("meeting_type")
    if meeting_type not in {"phone", "visit"}:
        questions.append("Görüşme türü belirsiz. Telefon görüşmesi mi, yüz yüze ziyaret mi olduğunu belirtin.")
    topic = str(meeting_data.get("topic") or "").strip()[:200] or "Genel görüşme"
    notes = str(meeting_data.get("notes") or "").strip()[:10000] or transcript.strip()[:10000]
    clean_lines: list[dict[str, Any]] = []
    warnings: list[str] = []
    for line in meeting_data.get("product_lines", []):
        product_id = line.get("product_id")
        product = product_by_id.get(str(product_id)) if product_id is not None else None
        if product is None:
            mention = str(line.get("mention") or "").strip()
            if mention:
                warnings.append("Katalogda eşleşmeyen ürün: " + mention)
            continue
        quantity = line.get("quantity")
        if type(quantity) is not int or quantity < 1 or quantity > 999999:
            warnings.append(f"{product['name']} için miktar belirtilmedi; ürün satırı eklenmedi.")
            continue
        clean_lines.append({
            "product_id": product["id"], "sku": product["sku"], "name": product["name"],
            "product_type": product.get("product_type", "machine"),
            "parent_product_id": product.get("parent_product_id"),
            "quantity": quantity, "unit_price": "", "currency": product["currency"],
        })
    selected_machines = {item["product_id"] for item in clean_lines if item["product_type"] == "machine"}
    valid_lines = []
    for line in clean_lines:
        if line["product_type"] == "option" and line.get("parent_product_id") not in selected_machines:
            warnings.append(f"{line['name']} opsiyonu için bağlı ana makine metinde bulunamadı; ürün satırı eklenmedi.")
            continue
        valid_lines.append(line)
    result = {
        "company_id": existing["id"] if existing else None,
        "company_name": existing["name"] if existing else company_name,
        "sectors": sectors,
        "sector": ", ".join(sectors),
        "is_new_company": existing is None,
        "company_data": company_data,
        "meeting_type": meeting_type if meeting_type in {"phone", "visit"} else None,
        "topic": topic,
        "notes": notes,
        "product_lines": valid_lines,
        "questions": questions,
        "warnings": warnings + [
            "Katalogda eşleşmeyen ürün: " + str(item) for item in parsed.get("unmatched_products", []) if str(item).strip()
        ],
    }
    return result, response


def _company_record_from_capture(data: dict[str, Any]) -> dict[str, Any]:
    company = data["company_data"]
    return {
        "id": str(uuid4()),
        "name": str(data["company_name"]).strip(),
        "sectors": data["sectors"],
        "sector": ", ".join(data["sectors"]),
        "authorized_people": [str(item).strip() for item in company.get("authorized_people", []) if str(item).strip()],
        "phone_numbers": [str(item).strip() for item in company.get("phone_numbers", []) if str(item).strip()],
        "city": company.get("city"), "district": company.get("district"),
        "neighborhood": company.get("neighborhood"), "street": company.get("street"),
        "building_number": company.get("building_number"), "postal_code": company.get("postal_code"),
        "address_extra": company.get("address_extra"), "website": company.get("website"),
        "email": company.get("email"), "tax_office": company.get("tax_office"),
        "tax_number": company.get("tax_number"), "mersis_number": company.get("mersis_number"),
        "notes": company.get("notes"),
        "address": ", ".join(str(company.get(key)).strip() for key in
            ("neighborhood", "street", "building_number", "district", "city") if company.get(key)) or None,
    }


@router.post("/api/meetings/capture")
def capture_meeting_from_text(payload: MeetingCaptureRequest, request: Request, http_response: Response) -> dict[str, Any]:
    from app.main import _require_browser_session, _require_csrf

    session = _require_browser_session(request)
    _require_csrf(request, session)
    if not agent_foundation.rule_enabled("external_ai_enabled", default=True):
        raise HTTPException(status_code=503, detail="Harici yapay zekâ kullanımı ajan güvenlik kurallarında kapalı.")
    _check_meeting_ai_rate_limit(request.cookies.get("sales_session", ""))
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Firma ve görüşme kaydı oluşturmak için OpenAI API anahtarı sunucuda tanımlı değil.")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
        model = os.environ.get("OPENAI_MODEL", "gpt-5.5")
        companies = db.list_companies()
        products = db.list_products()
        extracted, ai_response = extract_meeting_capture(client, model, payload.transcript.strip(), companies, products)
        if extracted["questions"]:
            return {"created": False, "questions": extracted["questions"], "warnings": extracted["warnings"]}
        existing = next((item for item in companies if item["id"] == extracted["company_id"]), None)
        company_record = _company_record_from_capture(extracted) if existing is None else None
        company_id = existing["id"] if existing else company_record["id"]
        meeting_id = str(uuid4())
        meeting_date = datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
        meeting_record = {
            "id": meeting_id, "company_id": company_id, "meeting_date": meeting_date,
            "meeting_type": extracted["meeting_type"], "topic": extracted["topic"],
            "notes": extracted["notes"], "product_lines": extracted["product_lines"],
        }
        saved = db.create_company_and_meeting(company_record, meeting_record, company_sectors=extracted["sectors"])
        try:
            agent_foundation.record_external_run(
                "meeting", "capture_from_text", str(session["subject"]),
                {"transcript_sha256": hashlib.sha256(payload.transcript.strip().encode("utf-8")).hexdigest()},
                {"company_id": saved["company"]["id"], "meeting_id": saved["meeting"]["id"],
                 "product_line_count": len(saved["meeting"].get("product_lines", []))},
            )
        except Exception as exc:
            logging.getLogger(__name__).warning("Meeting AI audit record failed (%s)", type(exc).__name__)
        http_response.status_code = 201
        try:
            from app import ai_usage
            session_hash = hashlib.sha256(request.cookies.get("sales_session", "").encode("utf-8")).hexdigest()
            ai_usage.record_response_usage(ai_response, model, "meeting", session_hash)
        except Exception as exc:
            logging.getLogger(__name__).warning("AI usage metering failed (%s)", type(exc).__name__)
        return {
            "created": True,
            "company": {"id": saved["company"]["id"], "name": saved["company"]["name"],
                        "sector": saved["company"]["sector"], "sectors": saved["company"]["sectors"], "created": company_record is not None},
            "meeting": saved["meeting"],
            "warnings": extracted["warnings"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Firma ve görüşme kaydı oluşturulamadı. Metni kontrol edip tekrar deneyin.") from exc
