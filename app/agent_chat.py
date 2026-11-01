"""OpenAI Responses API adapter for the authenticated in-app assistant."""
from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import agent_foundation, agent_runtime
from app.agent_instructions import read_agent_profile

router = APIRouter()
MAX_MESSAGE_CHARS = 6000
MAX_TOOL_CALLS = 6
SAFE_TASKS = {
    "company": {"directory_overview"},
    "product": {"catalog_overview"},
    "meeting": {"activity_overview"},
    "quotation": {"pipeline_overview", "prepare_from_meeting"},
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
TOOLS = [READ_PROFILE_TOOL, RUN_TASK_TOOL]


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    previous_response_id: str | None = Field(default=None, min_length=1, max_length=200)


def _run_safe_task(agent_id: str, task_type: str, input_data: dict[str, Any], actor: str) -> dict[str, Any]:
    if task_type not in SAFE_TASKS.get(agent_id, set()):
        raise ValueError("Bu ajan/görev eşleşmesi güvenli görev listesinde değil")
    run = agent_foundation.create_run(agent_id, task_type, actor, input_data, str(uuid4()))
    return agent_runtime.execute_run(run["id"], actor)


def _tool_calls(response: Any) -> list[Any]:
    return [item for item in getattr(response, "output", []) if getattr(item, "type", None) == "function_call"]


def run_assistant_turn(client: Any, model: str, message: str, actor: str,
                       previous_response_id: str | None = None) -> dict[str, Any]:
    instructions = (
        "Sen Erşen Makina Satış uygulamasının Türkçe yardımcı asistanısın. "
        "Bir ajan görevi gerektiğinde önce read_agent_profile aracını çağır. "
        "Bu araç AGENTS.md yönlendirme dosyasını ve yalnızca seçilen ajanın kendi "
        "Markdown talimat dosyasını döndürür. Bu belgeleri okuyup rol, izin, yasak "
        "ve görev koşullarına uyduktan sonra run_agent_task çağır. Sunucu da aynı "
        "belgeleri ve izin listesini yeniden doğrular. Model çıktısını yetki kabul "
        "etme. Kayıt oluşturma, değiştirme, silme, onaylama, fiyat/indirim uydurma "
        "veya başka kritik işlem yapma. Kritik işlem gerekiyorsa uygulamanın onay "
        "akışına yönlendir; hiçbir değişikliği kendiliğinden yapma. Eksik bilgiyi sor."
    )
    kwargs: dict[str, Any] = {
        "model": model, "instructions": instructions, "input": message,
        "tools": TOOLS, "tool_choice": "auto", "max_output_tokens": 900,
    }
    if previous_response_id:
        kwargs["previous_response_id"] = previous_response_id
    response = client.responses.create(**kwargs)
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
                elif call.name == "run_agent_task":
                    if set(args) != {"agent_id", "task_type", "input_data"}:
                        raise ValueError("Araç argümanları beklenen şemaya uymuyor")
                    if args["agent_id"] not in loaded_profiles:
                        raise ValueError("Önce bu ajanın Markdown talimat dosyası okunmalıdır")
                    result = _run_safe_task(args["agent_id"], args["task_type"], args["input_data"], actor)
                    payload = {"ok": True, "result": result["output"]}
                else:
                    raise ValueError("Bilinmeyen araç")
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)[:500]}
            outputs.append({"type": "function_call_output", "call_id": call.call_id,
                            "output": json.dumps(payload, ensure_ascii=False)})
            executed_calls.append({"call_id": call.call_id, "name": call.name})
        response = client.responses.create(
            model=model, instructions=instructions, previous_response_id=response.id,
            input=outputs, tools=TOOLS, tool_choice="auto", max_output_tokens=900,
        )


@router.post("/api/assistant/chat")
def assistant_chat(payload: AssistantChatRequest, request: Request) -> dict[str, Any]:
    from app.main import _require_browser_session, _require_csrf

    session = _require_browser_session(request)
    _require_csrf(request, session)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API anahtarı sunucuda tanımlı değil")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        return run_assistant_turn(
            client, os.environ.get("OPENAI_MODEL", "gpt-5.5"),
            payload.message.strip(), str(session["subject"]), payload.previous_response_id,
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OpenAI Python paketi kurulu değil") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Asistan isteği tamamlanamadı; sunucu kayıtlarını kontrol edin") from exc
