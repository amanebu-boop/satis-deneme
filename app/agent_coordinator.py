"""Deterministic coordinator for safe, read-only sales workflows.

The model may select only named task intents. This module owns the fixed mapping,
validation, sequencing, and failure isolation; it never performs business writes.
"""
from __future__ import annotations

from typing import Any, Callable
from datetime import date

from app.agent_instructions import load_agent_instructions
from app import agent_foundation

# Public intent -> (agent id, allowlisted task type).
TASKS: dict[str, tuple[str, str]] = {
    "company_overview": ("company", "directory_overview"),
    "company_data_quality": ("company", "data_quality"),
    "product_overview": ("product", "catalog_overview"),
    "product_catalog_health": ("product", "catalog_health"),
    "meeting_overview": ("meeting", "activity_overview"),
    "meeting_follow_up_review": ("meeting", "follow_up_review"),
    "quotation_overview": ("quotation", "pipeline_overview"),
    "sales_overview": ("reporting", "sales_overview"),
    "sales_period_summary": ("reporting", "period_summary"),
    "audit_overview": ("audit", "audit_overview"),
    "audit_anomalies": ("audit", "anomaly_review"),
    "meeting_quotation_preview": ("quotation", "prepare_from_meeting"),
}
MAX_COORDINATED_TASKS = 6


def run_sales_coordination(
    input_data: dict[str, Any],
    actor: str,
    execute_task: Callable[[str, str, dict[str, Any], str], dict[str, Any]],
) -> dict[str, Any]:
    """Run a validated sequence of allowlisted read-only sub-agent tasks."""
    load_agent_instructions("sales", "sales_coordinate")
    enabled_agents = {item["id"]: item["enabled"] for item in agent_foundation.list_agents()}
    if not enabled_agents.get("sales", False):
        raise ValueError("Satış Ajanı etkin değil; ajan yönetiminden etkinleştirilmelidir")
    if not isinstance(input_data, dict) or set(input_data) - {"tasks", "meeting_id", "date_from", "date_to"}:
        raise ValueError("sales_coordinate accepts only allowlisted task inputs")
    requested = input_data.get("tasks")
    if not isinstance(requested, list) or not requested:
        raise ValueError("En az bir koordinasyon görevi seçilmelidir")
    if len(requested) > MAX_COORDINATED_TASKS:
        raise ValueError("Koordinasyon görev sınırı aşıldı")
    if any(not isinstance(item, str) for item in requested):
        raise ValueError("Koordinasyon görevleri metin olmalıdır")
    if len(set(requested)) != len(requested):
        raise ValueError("Aynı koordinasyon görevi birden fazla kez istenemez")
    unknown = [item for item in requested if item not in TASKS]
    if unknown:
        raise ValueError("İzin verilmeyen koordinasyon görevi")
    meeting_id = input_data.get("meeting_id")
    if "meeting_quotation_preview" in requested:
        if not isinstance(meeting_id, str) or not meeting_id.strip():
            raise ValueError("Görüşmeden teklif önizlemesi için meeting_id gereklidir")
    elif meeting_id is not None:
        raise ValueError("meeting_id yalnızca meeting_quotation_preview ile kullanılabilir")
    if "sales_period_summary" in requested:
        if not isinstance(input_data.get("date_from"), str) or not isinstance(input_data.get("date_to"), str):
            raise ValueError("Dönem raporu için date_from ve date_to gereklidir")
        try:
            start, end = date.fromisoformat(input_data["date_from"]), date.fromisoformat(input_data["date_to"])
        except ValueError as exc:
            raise ValueError("Dönem tarihleri YYYY-MM-DD biçiminde olmalıdır") from exc
        if start.isoformat() != input_data["date_from"] or end.isoformat() != input_data["date_to"]:
            raise ValueError("Dönem tarihleri tam olarak YYYY-MM-DD biçiminde olmalıdır")
        if start > end or (end - start).days > 3660:
            raise ValueError("Dönem tarih aralığı geçersiz")
    elif "date_from" in input_data or "date_to" in input_data:
        raise ValueError("Tarih alanları yalnızca sales_period_summary ile kullanılabilir")

    # Fixed order prevents model-controlled sequencing of dependent workflows.
    ordered = [name for name in TASKS if name in requested]
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for name in ordered:
        agent_id, task_type = TASKS[name]
        if name == "meeting_quotation_preview":
            task_input = {"meeting_id": meeting_id.strip()}
        elif name == "sales_period_summary":
            task_input = {"date_from": input_data["date_from"], "date_to": input_data["date_to"]}
        else:
            task_input = {}
        if not enabled_agents.get(agent_id, False):
            failures.append({
                "task": name, "status": "blocked",
                "message": f"{agent_id} ajanı devre dışı; Ajan Yönetimi'nden etkinleştirin.",
            })
            continue
        try:
            result = execute_task(agent_id, task_type, task_input, actor)
            results.append({"task": name, "agent_id": agent_id, "status": "succeeded",
                            "result": result.get("output", result)})
        except Exception:
            # A failed subtask must not prevent independent read-only summaries.
            failures.append({"task": name, "status": "failed",
                             "message": "Görev tamamlanamadı; ayrıntı sunucu kayıtlarında."})

    return {
        "workflow": "sales_coordinate",
        "mode": "read_only",
        "completed": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
        "writes_performed": 0,
        "approval_required_for_business_changes": True,
    }
