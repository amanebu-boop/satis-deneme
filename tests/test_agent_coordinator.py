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


@pytest.fixture
def isolated_enabled_sales_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales-coordinator.db"))
    from app import db, agent_foundation

    db.init_db()
    agent_foundation.init_agent_foundation()
    agent_foundation.set_agent_enabled("sales", True, "integration-test")
    return db, agent_foundation


def test_sales_coordinator_executes_real_read_only_subagents(isolated_enabled_sales_database):
    from app import agent_chat

    db, foundation = isolated_enabled_sales_database
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('company-1', 'TEST FIRM')")

    result = agent_chat._run_safe_task(
        "sales",
        "sales_coordinate",
        {"tasks": ["sales_overview", "company_overview"]},
        "integration-test",
    )

    assert result["workflow"] == "sales_coordinate"
    assert result["completed"] == 2
    assert result["failed"] == 0
    assert result["writes_performed"] == 0
    outputs = {item["task"]: item["result"] for item in result["results"]}
    assert outputs["company_overview"]["companies"] == 1
    assert outputs["sales_overview"]["companies"] == 1
    runs = foundation.list_runs()
    assert {run["agent_id"] for run in runs} == {"sales", "company", "reporting"}
    parent = next(run for run in runs if run["agent_id"] == "sales")
    children = [run for run in runs if run["parent_run_id"] == parent["id"]]
    assert parent["task_type"] == "sales_coordinate"
    assert parent["status"] == "succeeded"
    assert {run["agent_id"] for run in children} == {"company", "reporting"}
    assert all(run["status"] == "succeeded" for run in runs)


def test_optional_audit_task_reports_disabled_agent_without_running_it(monkeypatch):
    from app import agent_coordinator
    monkeypatch.setattr(agent_coordinator.agent_foundation, "list_agents", lambda: [
        {"id": "sales", "enabled": True}, {"id": "audit", "enabled": False}
    ])
    invoked = []
    result = agent_coordinator.run_sales_coordination(
        {"tasks": ["audit_overview"]}, "tester",
        lambda *args: invoked.append(args),
    )
    assert invoked == []
    assert result["failed"] == 1
    assert result["failures"][0]["status"] == "blocked"
    assert "devre dışı" in result["failures"][0]["message"]


def test_coordinator_passes_explicit_date_range_to_reporting_agent(monkeypatch):
    monkeypatch.setattr(
        agent_coordinator.agent_foundation, "list_agents",
        lambda: [{"id": "sales", "enabled": True}, {"id": "reporting", "enabled": True}],
    )
    calls = []
    result = agent_coordinator.run_sales_coordination(
        {"tasks": ["sales_period_summary"], "date_from": "2026-01-01", "date_to": "2026-01-31"},
        "tester",
        lambda agent_id, task_type, input_data, actor:
            calls.append((agent_id, task_type, input_data)) or {"output": {"meetings": 3}},
    )
    assert calls == [("reporting", "period_summary", {
        "date_from": "2026-01-01", "date_to": "2026-01-31"
    })]
    assert result["completed"] == 1


def test_coordinator_rejects_period_report_without_both_dates(enabled_sales):
    with pytest.raises(ValueError, match="date_from"):
        agent_coordinator.run_sales_coordination(
            {"tasks": ["sales_period_summary"], "date_from": "2026-01-01"},
            "tester", lambda *args: pytest.fail("No task should execute"),
        )
