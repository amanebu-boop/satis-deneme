"""Deterministic coordinator for safe, read-only sales workflows.

The model may select only named task intents. This module owns the fixed mapping,
validation, sequencing, and failure isolation; it never performs business writes.
"""
from __future__ import annotations

from typing import Any, Callable

from app.agent_instructions import load_agent_instructions
from app import agent_foundation

# Public intent -> (agent id, allowlisted task type).
TASKS: dict[str, tuple[str, str]] = {
    "company_overview": ("company", "directory_overview"),
    "product_overview": ("product", "catalog_overview"),
    "meeting_overview": ("meeting", "activity_overview"),
    "quotation_overview": ("quotation", "pipeline_overview"),
    "sales_overview": ("reporting", "sales_overview"),
    "audit_overview": ("audit", "audit_overview"),
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
    if not isinstance(input_data, dict) or set(input_data) - {"tasks", "meeting_id"}:
        raise ValueError("sales_coordinate accepts only tasks and optional meeting_id")
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

    # Fixed order prevents model-controlled sequencing of dependent workflows.
    ordered = [name for name in TASKS if name in requested]
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for name in ordered:
        agent_id, task_type = TASKS[name]
        task_input = {"meeting_id": meeting_id.strip()} if name == "meeting_quotation_preview" else {}
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
