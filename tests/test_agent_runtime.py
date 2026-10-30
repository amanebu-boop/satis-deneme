from __future__ import annotations

import pytest

from app import agent_foundation as foundation
from app import agent_runtime


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales-runtime-test.db"))
    from app import db
    db.init_db()
    foundation.init_agent_foundation()
    return tmp_path / "sales-runtime-test.db"


def test_disabled_reporting_agent_cannot_execute(isolated_database):
    run = foundation.create_run("reporting", "sales_overview", "test-user")

    with pytest.raises(ValueError, match="disabled"):
        agent_runtime.execute_run(run["id"], "test-user")

    assert foundation.list_runs()[0]["status"] == "blocked"


def test_read_only_sales_overview_executes_and_records_aggregate_output(isolated_database, monkeypatch):
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'reporting'")

    monkeypatch.setattr(db, "list_companies", lambda: [{"id": "1"}, {"id": "2"}])
    monkeypatch.setattr(db, "list_meetings", lambda: [{"id": "m1"}])
    monkeypatch.setattr(db, "list_products", lambda: [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}])
    monkeypatch.setattr(db, "list_quotations", lambda: [
        {"status": "draft", "currency": "TRY"},
        {"status": "sent", "currency": "TRY"},
        {"status": "draft", "currency": "EUR"},
    ])
    monkeypatch.setattr(db, "list_follow_ups", lambda: [
        {"status": "open"}, {"status": "done"}, {"status": "open"},
    ])

    run = foundation.create_run("reporting", "sales_overview", "test-user")
    result = agent_runtime.execute_run(run["id"], "test-user")

    assert result["status"] == "succeeded"
    assert result["output"] == {
        "report": "sales_overview",
        "scope": "aggregate_counts_only",
        "companies": 2,
        "meetings": 1,
        "products": 3,
        "quotations": 3,
        "quotations_by_status": {"draft": 2, "sent": 1},
        "quotations_by_currency": {"EUR": 1, "TRY": 2},
        "follow_ups_by_status": {"done": 1, "open": 2},
    }
    assert foundation.list_runs()[0]["status"] == "succeeded"
    assert {item["event_type"] for item in foundation.list_audit_logs()} >= {
        "run_started", "run_succeeded",
    }


def test_unsupported_task_does_not_start(isolated_database):
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'reporting'")

    run = foundation.create_run("reporting", "arbitrary_task", "test-user")
    with pytest.raises(ValueError, match="unsupported"):
        agent_runtime.execute_run(run["id"], "test-user")

    assert foundation.list_runs()[0]["status"] == "queued"


def test_invalid_reporting_input_is_marked_failed(isolated_database):
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'reporting'")

    run = foundation.create_run(
        "reporting", "sales_overview", "test-user", {"unexpected": "value"}
    )
    with pytest.raises(ValueError, match="does not accept"):
        agent_runtime.execute_run(run["id"], "test-user")

    assert foundation.list_runs()[0]["status"] == "failed"
    assert foundation.list_audit_logs()[0]["event_type"] == "run_failed"
