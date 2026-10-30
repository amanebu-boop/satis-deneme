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


def test_read_only_sales_overview_executes_and_records_aggregate_output(isolated_database):
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'reporting'")
        connection.executemany(
            "INSERT INTO companies (id, name) VALUES (?, ?)",
            [("c1", "Company 1"), ("c2", "Company 2")],
        )
        connection.execute(
            "INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES (?, ?, ?, ?)",
            ("m1", "c1", "2026-10-30", "Test"),
        )
        connection.executemany(
            """INSERT INTO products (id, sku, name, currency, unit_price)
               VALUES (?, ?, ?, ?, ?)""",
            [
                ("p1", "SKU-1", "Product 1", "TRY", "10"),
                ("p2", "SKU-2", "Product 2", "TRY", "20"),
                ("p3", "SKU-3", "Product 3", "EUR", "30"),
            ],
        )
        connection.executemany(
            """INSERT INTO quotations
               (id, currency, subtotal, tax_rate, tax_amount, total, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)""",
            [
                ("q1", "TRY", "10", "0", "0", "10", "2026-10-30"),
                ("q2", "TRY", "20", "0", "0", "20", "2026-10-30"),
                ("q3", "EUR", "30", "0", "0", "30", "2026-10-30"),
            ],
        )
        connection.executemany(
            """INSERT INTO follow_up_tasks
               (id, company_id, title, due_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("f1", "c1", "Follow up 1", "2026-10-31", "open", "2026-10-30"),
                ("f2", "c1", "Follow up 2", "2026-10-31", "done", "2026-10-30"),
                ("f3", "c2", "Follow up 3", "2026-10-31", "open", "2026-10-30"),
            ],
        )

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
        "quotations_by_status": {"draft": 3},
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


def test_completed_agent_run_cannot_execute_twice(isolated_database, monkeypatch):
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'reporting'")

    monkeypatch.setattr(
        agent_runtime, "_sales_overview",
        lambda payload: {"report": "sales_overview", "scope": "aggregate_counts_only"},
    )
    run = foundation.create_run("reporting", "sales_overview", "test-user")
    agent_runtime.execute_run(run["id"], "test-user")

    with pytest.raises(ValueError, match="not queued"):
        agent_runtime.execute_run(run["id"], "test-user")

    assert foundation.list_runs()[0]["status"] == "succeeded"
