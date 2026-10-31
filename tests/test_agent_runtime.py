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


def _enable(agent_id):
    from app import db
    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = ?", (agent_id,))


def test_disabled_agent_cannot_execute(isolated_database):
    run = foundation.create_run("reporting", "sales_overview", "test-user")
    with pytest.raises(ValueError, match="disabled"):
        agent_runtime.execute_run(run["id"], "test-user")
    assert foundation.list_runs()[0]["status"] == "blocked"


def test_sales_overview_returns_aggregate_counts(isolated_database):
    from app import db
    _enable("reporting")
    with db.connect() as connection:
        connection.executemany("INSERT INTO companies (id, name) VALUES (?, ?)", [("c1", "Company 1"), ("c2", "Company 2")])
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES (?, ?, ?, ?)", ("m1", "c1", "2026-10-30", "Private note"))
        connection.executemany(
            "INSERT INTO products (id, sku, name, currency, unit_price) VALUES (?, ?, ?, ?, ?)",
            [("p1", "SKU-1", "Product 1", "TRY", "10"), ("p2", "SKU-2", "Product 2", "TRY", "20"), ("p3", "SKU-3", "Product 3", "EUR", "30")],
        )
        connection.executemany(
            """INSERT INTO quotations (id, currency, subtotal, tax_rate, tax_amount, total, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)""",
            [("q1", "TRY", "10", "0", "0", "10", "2026-10-30"), ("q2", "TRY", "20", "0", "0", "20", "2026-10-30"), ("q3", "EUR", "30", "0", "0", "30", "2026-10-30")],
        )
        connection.executemany(
            "INSERT INTO follow_up_tasks (id, company_id, title, due_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [("f1", "c1", "Follow up 1", "2026-10-31", "open", "2026-10-30"), ("f2", "c1", "Follow up 2", "2026-10-31", "done", "2026-10-30"), ("f3", "c2", "Follow up 3", "2026-10-31", "open", "2026-10-30")],
        )
    run = foundation.create_run("reporting", "sales_overview", "test-user")
    result = agent_runtime.execute_run(run["id"], "test-user")
    assert result["output"]["companies"] == 2
    assert result["output"]["quotations_by_currency"] == {"EUR": 1, "TRY": 2}
    assert "Private note" not in str(result["output"])
    assert foundation.list_runs()[0]["status"] == "succeeded"


def test_company_directory_overview_reads_real_company_and_contact_tables(isolated_database):
    from app import db
    _enable("company")
    with db.connect() as connection:
        connection.executemany("INSERT INTO companies (id, name) VALUES (?, ?)", [("c1", "A"), ("c2", "B")])
        connection.execute("INSERT INTO contacts (id, company_id, name) VALUES ('ct1', 'c1', 'Person')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1', 'c1', '2026-10-30', 'note')")
        connection.execute("INSERT INTO follow_up_tasks (id, company_id, title, due_date, created_at) VALUES ('f1', 'c2', 'Call', '2026-11-01', '2026-10-31')")
    run = foundation.create_run("company", "directory_overview", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output == {
        "report": "company_directory_overview", "scope": "aggregate_counts_only",
        "companies": 2, "contacts": 1, "companies_with_meetings": 1,
        "companies_with_open_follow_ups": 1,
    }


def test_product_catalog_overview_uses_catalog_schema(isolated_database):
    from app import db
    _enable("product")
    with db.connect() as connection:
        connection.executemany(
            "INSERT INTO products (id, sku, name, currency, unit_price, product_type, parent_product_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [("p1", "A", "Machine", "TRY", "10", "machine", None), ("p2", "B", "Option", "TRY", "2", "option", "p1"), ("p3", "C", "Service", "EUR", "5", "service", None)],
        )
    run = foundation.create_run("product", "catalog_overview", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["products"] == 3
    assert output["products_by_type"] == {"machine": 1, "option": 1, "service": 1}
    assert output["linked_options"] == 1


def test_meeting_activity_overview_counts_existing_meeting_product_links(isolated_database):
    from app import db
    _enable("meeting")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'A')")
        connection.execute("INSERT INTO products (id, sku, name, currency, unit_price) VALUES ('p1', 'A', 'Machine', 'TRY', '10')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes, meeting_type) VALUES ('m1', 'c1', '2026-10-30', 'private', 'visit')")
        connection.execute("INSERT INTO meeting_products (id, meeting_id, product_id, name, quantity, unit_price, currency) VALUES ('mp1', 'm1', 'p1', 'Machine', '2', '10', 'TRY')")
    run = foundation.create_run("meeting", "activity_overview", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["meetings"] == 1
    assert output["meeting_product_lines"] == 1
    assert output["meetings_with_products"] == 1
    assert "private" not in str(output)


def test_quotation_pipeline_overview_aggregates_value_by_currency(isolated_database):
    from app import db
    _enable("quotation")
    with db.connect() as connection:
        connection.executemany(
            """INSERT INTO quotations (id, currency, subtotal, tax_rate, tax_amount, total, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)""",
            [("q1", "TRY", "10", "0", "0", "10.50", "2026-10-30"), ("q2", "TRY", "20", "0", "0", "20.25", "2026-10-30"), ("q3", "EUR", "30", "0", "0", "30", "2026-10-30")],
        )
    run = foundation.create_run("quotation", "pipeline_overview", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["quotations"] == 3
    assert output["quotation_value_by_currency"] == {"EUR": "30", "TRY": "30.75"}


def test_unsupported_task_does_not_start(isolated_database):
    _enable("reporting")
    run = foundation.create_run("reporting", "arbitrary_task", "test-user")
    with pytest.raises(ValueError, match="unsupported"):
        agent_runtime.execute_run(run["id"], "test-user")
    assert foundation.list_runs()[0]["status"] == "queued"


def test_invalid_input_is_marked_failed(isolated_database):
    _enable("reporting")
    run = foundation.create_run("reporting", "sales_overview", "test-user", {"unexpected": "value"})
    with pytest.raises(ValueError, match="does not accept"):
        agent_runtime.execute_run(run["id"], "test-user")
    assert foundation.list_runs()[0]["status"] == "failed"
    assert foundation.list_audit_logs()[0]["event_type"] == "run_failed"


def test_completed_run_cannot_execute_twice(isolated_database):
    _enable("reporting")
    run = foundation.create_run("reporting", "sales_overview", "test-user")
    agent_runtime.execute_run(run["id"], "test-user")
    with pytest.raises(ValueError, match="not queued"):
        agent_runtime.execute_run(run["id"], "test-user")
    assert foundation.list_runs()[0]["status"] == "succeeded"
