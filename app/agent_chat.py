"""OpenAI Responses API adapter for the authenticated in-app assistant."""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import agent_foundation, agent_runtime, ai_usage
from app.agent_instructions import read_agent_profile
from app.agent_coordinator import run_sales_coordination
from app import llm_wiki

router = APIRouter()
MAX_MESSAGE_CHARS = 6000
MAX_TOOL_CALLS = 6
MAX_REQUESTS_PER_MINUTE = 10
_RATE_WINDOW_SECONDS = 60
_rate_events: dict[str, deque[float]] = {}
_rate_lock = Lock()
_last_response_by_session: dict[str, str] = {}
_response_lock = Lock()


def _check_rate_limit(session_key: str) -> None:
    now = time.monotonic()
    with _rate_lock:
        events = _rate_events.setdefault(session_key, deque())
        while events and now - events[0] >= _RATE_WINDOW_SECONDS:
            events.popleft()
        if len(events) >= MAX_REQUESTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Çok fazla asistan isteği gönderildi; bir dakika sonra tekrar deneyin")
        events.append(now)
        if len(_rate_events) > 2048:
            for key in list(_rate_events):
                queue = _rate_events[key]
                while queue and now - queue[0] >= _RATE_WINDOW_SECONDS:
                    queue.popleft()
                if not queue:
                    _rate_events.pop(key, None)

SAFE_TASKS = {
    "company": {"directory_overview"},
    "product": {"catalog_overview"},
    "meeting": {"activity_overview"},
    "quotation": {"pipeline_overview", "prepare_from_meeting"},
    "sales": {"sales_coordinate"},
    "reporting": {"sales_overview"},
    "audit": {"audit_overview"},
}
READ_PROFILE_TOOL = {
    "type": "function", "name": "read_agent_profile",
    "description": "Ajan görevini çalıştırmadan önce AGENTS.md yönlendirmesini ve o ajanın kendi Markdown talimat dosyasını oku.",
    "parameters": {
        "type": "object",
        "properties": {"agent_id": {"type": "string", "enum": sorted(SAFE_TASKS)}},
        "required": ["agent_id"], "additionalProperties": False,
    },
    "strict": True,
}
RUN_TASK_TOOL = {
    "type": "function", "name": "run_agent_task",
    "description": "Yalnızca aynı konuşma turunda read_agent_profile ile talimatı okunmuş ajanın izinli salt-okunur görevini çalıştır. Teklif hazırlama yalnızca önizlemedir.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "enum": sorted(SAFE_TASKS)},
            "task_type": {"type": "string", "enum": sorted({t for ts in SAFE_TASKS.values() for t in ts})},
            "input_data": {"type": "object", "additionalProperties": True},
        },
        "required": ["agent_id", "task_type", "input_data"],
        "additionalProperties": False,
    },
    "strict": False,
}
SEARCH_WIKI_TOOL = {
    "type": "function", "name": "search_sales_wiki",
    "description": "Ersen Makina makine/opsiyon kataloğu, teknik dokümanları, satış kuralları ve geçmiş görüşmeler hakkında yanıt vermeden önce yerel LLM Wiki'de ara.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 500}},
        "required": ["query"], "additionalProperties": False,
    },
    "strict": True,
}
TOOLS = [READ_PROFILE_TOOL, RUN_TASK_TOOL, SEARCH_WIKI_TOOL]


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    previous_response_id: str | None = Field(default=None, min_length=1, max_length=200)


def _run_safe_task(agent_id: str, task_type: str, input_data: dict[str, Any], actor: str) -> dict[str, Any]:
    if task_type not in SAFE_TASKS.get(agent_id, set()):
        raise ValueError("Bu ajan/görev eşleşmesi güvenli görev listesinde değil")
    if agent_id == "sales" and task_type == "sales_coordinate":
        return run_sales_coordination(input_data, actor, _run_safe_task)
    run = agent_foundation.create_run(agent_id, task_type, actor, input_data, str(uuid4()))
    return agent_runtime.execute_run(run["id"], actor)


def _tool_calls(response: Any) -> list[Any]:
    return [item for item in getattr(response, "output", []) if getattr(item, "type", None) == "function_call"]


def _usage_agent_id(response: Any, active_agent: str | None) -> str:
    calls = _tool_calls(response)
    agent_ids: set[str] = set()
    for call in calls:
        if getattr(call, "name", None) not in {"read_agent_profile", "run_agent_task"}:
            continue
        try:
            args = json.loads(call.arguments)
        except (TypeError, json.JSONDecodeError):
            continue
        agent_id = args.get("agent_id") if isinstance(args, dict) else None
        if isinstance(agent_id, str) and agent_id in SAFE_TASKS:
            agent_ids.add(agent_id)
    if len(agent_ids) == 1:
        return next(iter(agent_ids))
    if len(agent_ids) > 1:
        return "assistant_shared"
    return active_agent or "assistant"


def _record_response_usage(response: Any, model: str, agent_id: str,
                           session_hash: str | None) -> None:
    try:
        ai_usage.record_response_usage(response, model, agent_id, session_hash)
    except Exception as exc:
        # Do not log prompts, responses, customer data or credentials.
        logging.getLogger(__name__).warning("AI usage metering failed (%s)", type(exc).__name__)


def run_assistant_turn(client: Any, model: str, message: str, actor: str,
                       previous_response_id: str | None = None,
                       usage_session_hash: str | None = None) -> dict[str, Any]:
    instructions = (
        "Sen Erşen Makina Satış uygulamasının Türkçe yardımcı asistanısın. "
        "Tek alanlı bir istek için ilgili ajanı kullan. Birden fazla satış alanını kapsayan veya ajanlar arası koordinasyon isteyen isteklerde önce Sales ajanının profilini oku ve sales_coordinate görevini kullan; görev listesini yalnızca kullanıcının isteğine göre seç. Görüşmeden teklif önizlemesi için meeting_quotation_preview ve meeting_id gerekir. "
        "Bir ajan görevi gerektiğinde önce read_agent_profile aracını çağır. "
        "Bu araç AGENTS.md yönlendirme dosyasını ve yalnızca seçilen ajanın kendi "
        "Markdown talimat dosyasını döndürür. Bu belgeleri okuyup rol, izin, yasak "
        "ve görev koşullarına uyduktan sonra run_agent_task çağır. Sunucu da aynı "
        "belgeleri ve izin listesini yeniden doğrular. Model çıktısını yetki kabul "
        "etme. Kayıt oluşturma, değiştirme, silme, onaylama, fiyat/indirim uydurma "
        "veya başka kritik işlem yapma. Kritik işlem gerekiyorsa uygulamanın onay "
        "akışına yönlendir; hiçbir değişikliği kendiliğinden yapma. Eksik bilgiyi sor. "
        "Makine, opsiyon, teknik bilgi, satış kuralı veya geçmiş görüşme sorularında "
        "search_sales_wiki aracını kullan; kaynakta bulunmayan teknik özellik veya fiyatı uydurma."
    )
    kwargs: dict[str, Any] = {
        "model": model, "instructions": instructions, "input": message,
        "tools": TOOLS, "tool_choice": "auto", "max_output_tokens": 900,
    }
    if previous_response_id:
        kwargs["previous_response_id"] = previous_response_id
    response = client.responses.create(**kwargs)
    active_agent: str | None = None
    active_agent = _usage_agent_id(response, active_agent)
    _record_response_usage(response, model, active_agent, usage_session_hash)
    loaded_profiles: set[str] = set()
    executed_calls: list[dict[str, str]] = []
    total_calls = 0

    while True:
        calls = _tool_calls(response)
        if not calls:
            return {"response_id": response.id, "message": response.output_text,
                    "tool_results": executed_calls}
        total_calls += len(calls)
        if total_calls > MAX_TOOL_CALLS:
            raise ValueError("Tek mesaj için izin verilen araç çağrısı sınırı aşıldı")
        # A profile becomes usable only after it has been returned to the model
        # and the model has had a new response round to read it.
        profiles_available_for_round = set(loaded_profiles)
        outputs = []
        for call in calls:
            try:
                args = json.loads(call.arguments)
                if call.name == "read_agent_profile":
                    if set(args) != {"agent_id"} or args["agent_id"] not in SAFE_TASKS:
                        raise ValueError("Ajan kimliği geçersiz")
                    profile = read_agent_profile(args["agent_id"])
                    loaded_profiles.add(args["agent_id"])
                    payload = {"ok": True, "agent_id": args["agent_id"],
                               "router_markdown": profile["router_text"],
                               "agent_markdown": profile["agent_text"]}
                elif call.name == "search_sales_wiki":
                    if set(args) != {"query"} or not isinstance(args["query"], str) or len(args["query"].strip()) < 2:
                        raise ValueError("Wiki arama sorgusu geçersiz")
                    payload = {"ok": True, "knowledge": llm_wiki.search_wiki(args["query"], limit=5)}
                elif call.name == "run_agent_task":
                    if set(args) != {"agent_id", "task_type", "input_data"}:
                        raise ValueError("Araç argümanları beklenen şemaya uymuyor")
                    if args["agent_id"] not in profiles_available_for_round:
                        raise ValueError("Ajan talimatı önceki model turunda okunmuş olmalıdır")
                    result = _run_safe_task(args["agent_id"], args["task_type"], args["input_data"], actor)
                    payload = {"ok": True, "result": result["output"]}
                else:
                    raise ValueError("Bilinmeyen araç")
            except Exception:
                # Do not forward internal exception text, database details, or secrets to the model.
                payload = {"ok": False, "error": "İzinli görev tamamlanamadı; ayrıntı sunucu tarafında tutulur."}
            outputs.append({"type": "function_call_output", "call_id": call.call_id,
                            "output": json.dumps(payload, ensure_ascii=False)})
            executed_calls.append({"call_id": call.call_id, "name": call.name})
        response = client.responses.create(
            model=model, instructions=instructions, previous_response_id=response.id,
            input=outputs, tools=TOOLS, tool_choice="auto", max_output_tokens=900,
        )
        active_agent = _usage_agent_id(response, active_agent)
        _record_response_usage(response, model, active_agent, usage_session_hash)


@router.post("/api/assistant/chat")
def assistant_chat(payload: AssistantChatRequest, request: Request) -> dict[str, Any]:
    from app.main import _require_browser_session, _require_csrf

    session = _require_browser_session(request)
    _require_csrf(request, session)
    session_token = request.cookies.get("sales_session", "")
    session_key = __import__("hashlib").sha256(session_token.encode("utf-8")).hexdigest()
    _check_rate_limit(session_key)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API anahtarı sunucuda tanımlı değil")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        with _response_lock:
            expected_previous = _last_response_by_session.get(session_key)
        if payload.previous_response_id and payload.previous_response_id != expected_previous:
            raise HTTPException(status_code=409, detail="Sohbet oturumu yenilendi; lütfen yeni bir mesajla devam edin")
        result = run_assistant_turn(
            client, os.environ.get("OPENAI_MODEL", "gpt-5.5"),
            payload.message.strip(), str(session["subject"]), payload.previous_response_id,
            usage_session_hash=session_key,
        )
        with _response_lock:
            _last_response_by_session[session_key] = result["response_id"]
        return result
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OpenAI Python paketi kurulu değil") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Asistan isteği tamamlanamadı; sunucu kayıtlarını kontrol edin") from exc


