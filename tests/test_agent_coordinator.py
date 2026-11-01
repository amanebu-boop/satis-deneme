from __future__ import annotations

import pytest

from app import agent_coordinator


@pytest.fixture
def enabled_sales(monkeypatch):
    monkeypatch.setattr(
        agent_coordinator.agent_foundation,
        "list_agents",
        lambda: [
            {"id": "sales", "enabled": True},
            {"id": "company", "enabled": True},
            {"id": "product", "enabled": True},
            {"id": "meeting", "enabled": True},
            {"id": "quotation", "enabled": True},
            {"id": "reporting", "enabled": True},
            {"id": "audit", "enabled": True},
        ],
    )


def test_coordinator_requires_sales_agent_enabled(monkeypatch):
    monkeypatch.setattr(
        agent_coordinator.agent_foundation,
        "list_agents",
        lambda: [{"id": "sales", "enabled": False}],
    )
    with pytest.raises(ValueError, match="etkin değil"):
        agent_coordinator.run_sales_coordination(
            {"tasks": ["sales_overview"]}, "tester",
            lambda *args: pytest.fail("No sub-agent should run"),
        )


def test_coordinator_runs_only_requested_tasks_in_fixed_order(enabled_sales):
    calls = []

    def execute(agent_id, task_type, input_data, actor):
        calls.append((agent_id, task_type, input_data, actor))
        return {"output": {"agent": agent_id}}

    result = agent_coordinator.run_sales_coordination(
        {"tasks": ["product_overview", "company_overview", "sales_overview"]},
        "tester",
        execute,
    )

    assert calls == [
        ("company", "directory_overview", {}, "tester"),
        ("product", "catalog_overview", {}, "tester"),
        ("reporting", "sales_overview", {}, "tester"),
    ]
    assert result["completed"] == 3
    assert result["failed"] == 0
    assert result["writes_performed"] == 0
    assert result["approval_required_for_business_changes"] is True


def test_meeting_quotation_preview_requires_meeting_id(enabled_sales):
    with pytest.raises(ValueError, match="meeting_id"):
        agent_coordinator.run_sales_coordination(
            {"tasks": ["meeting_quotation_preview"]}, "tester",
            lambda *args: pytest.fail("No sub-agent should run"),
        )


def test_coordinator_rejects_unknown_duplicate_and_excess_tasks(enabled_sales):
    execute = lambda *args: {"output": {}}
    with pytest.raises(ValueError, match="İzin verilmeyen"):
        agent_coordinator.run_sales_coordination({"tasks": ["delete_company"]}, "tester", execute)
    with pytest.raises(ValueError, match="birden fazla"):
        agent_coordinator.run_sales_coordination({"tasks": ["sales_overview", "sales_overview"]}, "tester", execute)
    with pytest.raises(ValueError, match="sınırı"):
        agent_coordinator.run_sales_coordination(
            {"tasks": list(agent_coordinator.TASKS)[:7]}, "tester", execute
        )


def test_coordinator_continues_independent_tasks_after_one_failure(enabled_sales):
    calls = []

    def execute(agent_id, task_type, input_data, actor):
        calls.append(agent_id)
        if agent_id == "company":
            raise RuntimeError("private internal detail")
        return {"output": {"ok": True}}

    result = agent_coordinator.run_sales_coordination(
        {"tasks": ["company_overview", "product_overview"]}, "tester", execute
    )

    assert calls == ["company", "product"]
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["failures"][0]["message"] == "Görev tamamlanamadı; ayrıntı sunucu kayıtlarında."
    assert "private internal detail" not in str(result)


def test_meeting_preview_passes_only_meeting_id_to_quotation_agent(enabled_sales):
    calls = []

    def execute(agent_id, task_type, input_data, actor):
        calls.append((agent_id, task_type, input_data))
        return {"output": {"scope": "draft_preview_only"}}

    result = agent_coordinator.run_sales_coordination(
        {"tasks": ["meeting_quotation_preview"], "meeting_id": "meeting-123"},
        "tester",
        execute,
    )

    assert calls == [("quotation", "prepare_from_meeting", {"meeting_id": "meeting-123"})]
    assert result["results"][0]["result"]["scope"] == "draft_preview_only"
