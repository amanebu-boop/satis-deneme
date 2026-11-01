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


def test_prepare_quotation_from_meeting_returns_preview_without_creating_quote(isolated_database):
    from app import db
    _enable("quotation")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'Firma A')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1', 'c1', '2026-10-31', 'private note')")
        connection.execute("INSERT INTO products (id, sku, name, currency, unit_price) VALUES ('p1', 'SKU1', 'Makine', 'EUR', '100')")
        connection.executemany(
            """INSERT INTO meeting_products
               (id, meeting_id, product_id, sku, name, quantity, unit_price, currency)
               VALUES (?, 'm1', ?, ?, ?, ?, ?, 'EUR')""",
            [("mp1", "p1", "SKU1", "Makine", "1", "100"),
             ("mp2", "p1", "SKU1", "Makine", "2", "100")],
        )
    run = foundation.create_run("quotation", "prepare_from_meeting", "test-user", {"meeting_id": "m1"})
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["company_id"] == "c1"
    assert output["line_count"] == 2
    assert output["subtotal"] == "300"
    assert "discount" not in output
    assert output["lines"][0]["quantity"] == 1
    assert "private note" not in str(output)
    assert db.list_quotations() == []


def test_prepare_quotation_from_meeting_rejects_missing_price(isolated_database):
    from app import db
    _enable("quotation")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'Firma A')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1', 'c1', '2026-10-31', 'note')")
        connection.execute(
            """INSERT INTO meeting_products
               (id, meeting_id, name, quantity, unit_price, currency)
               VALUES ('mp1', 'm1', 'Makine', '1', '', 'EUR')"""
        )
    run = foundation.create_run("quotation", "prepare_from_meeting", "test-user", {"meeting_id": "m1"})
    with pytest.raises(ValueError, match="tam sayı değil"):
        agent_runtime.execute_run(run["id"], "test-user")
    assert db.list_quotations() == []


def test_successful_preview_can_be_submitted_for_hash_bound_approval(isolated_database):
    from app import db
    _enable("quotation")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'Firma A')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1', 'c1', '2026-10-31', 'note')")
        connection.execute(
            """INSERT INTO meeting_products
               (id, meeting_id, name, quantity, unit_price, currency)
               VALUES ('mp1', 'm1', 'Makine', '1', '100', 'EUR')"""
        )
    run = foundation.create_run("quotation", "prepare_from_meeting", "test-user", {"meeting_id": "m1"})
    preview = agent_runtime.execute_run(run["id"], "test-user")["output"]
    approval = foundation.request_approval(run["id"], "quotation.create_from_meeting", preview, "test-user")
    reviewed = foundation.review_approval(approval["id"], "approved", "test-user", preview)
    assert reviewed["status"] == "approved"
    assert foundation.list_approvals()[0]["payload"] == preview
    assert foundation.list_runs()[0]["status"] == "pending_approval"



def test_succeeded_non_quotation_run_cannot_request_approval(isolated_database):
    _enable("reporting")
    run = foundation.create_run("reporting", "sales_overview", "test-user")
    agent_runtime.execute_run(run["id"], "test-user")
    with pytest.raises(ValueError, match="not eligible"):
        foundation.request_approval(run["id"], "arbitrary.action", {}, "test-user")


def test_audit_agent_returns_aggregate_counts_without_actor_or_event_details(isolated_database):
    foundation.set_agent_enabled("audit", True, "test-user")
    foundation.create_run("company", "directory_overview", "another-user")
    run = foundation.create_run("audit", "audit_overview", "test-user")

    output = agent_runtime.execute_run(run["id"], "test-user")["output"]

    assert output["report"] == "audit_overview"
    assert output["scope"] == "aggregate_counts_only"
    assert output["audit_events"] >= 3
    assert output["events_by_type"]["agent_enabled"] == 1
    assert output["events_by_type"]["run_blocked"] == 1
    assert output["agent_runs_by_status"]["blocked"] == 1
    assert "another-user" not in str(output)
    assert "details" not in output


def test_agent_task_requires_router_and_own_markdown_permission(isolated_database):
    from app.agent_instructions import load_agent_instructions

    loaded = load_agent_instructions("audit", "audit_overview")
    assert loaded["agent_id"] == "audit"
    assert loaded["task_type"] == "audit_overview"

    with pytest.raises(ValueError, match="not permitted"):
        load_agent_instructions("audit", "prepare_from_meeting")


def test_sales_agent_allows_only_the_deterministic_coordinator_task(isolated_database):
    from app.agent_instructions import load_agent_instructions

    loaded = load_agent_instructions("sales", "sales_coordinate")
    assert loaded["agent_id"] == "sales"
    assert loaded["task_type"] == "sales_coordinate"

    with pytest.raises(ValueError, match="not permitted"):
        load_agent_instructions("sales", "delete_company")


def test_every_registered_agent_has_routed_instruction_file(isolated_database):
    from app.agent_instructions import AGENT_FILES, load_agent_instructions

    assert set(AGENT_FILES) == {
        "company", "product", "meeting", "quotation",
        "warehouse", "sales", "reporting", "audit",
    }
    for agent_id in AGENT_FILES:
        path = AGENT_FILES[agent_id]
        from pathlib import Path
        assert (Path(__file__).resolve().parents[1] / path).is_file()

    assert load_agent_instructions("company", "directory_overview")["agent_id"] == "company"
    assert load_agent_instructions("product", "catalog_overview")["agent_id"] == "product"
    assert load_agent_instructions("meeting", "activity_overview")["agent_id"] == "meeting"
    assert load_agent_instructions("quotation", "prepare_from_meeting")["agent_id"] == "quotation"
    assert load_agent_instructions("reporting", "sales_overview")["agent_id"] == "reporting"
    assert load_agent_instructions("audit", "audit_overview")["agent_id"] == "audit"


def test_company_data_quality_reports_only_aggregate_counts(isolated_database):
    from app import db
    _enable("company")
    with db.connect() as connection:
        connection.executemany(
            """INSERT INTO companies (id, name, sector, city, address, phone_numbers)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("c1", "ABC Makina", '["Mobilya"]', "Konya", "Adres 1", '["05550000000"]'),
                ("c2", "ABC Makina", None, None, None, "[]"),
                ("c3", "XYZ Makina", '["Mobilya"]', "Konya", "Adres 3", "[]"),
            ],
        )
        connection.execute("INSERT INTO contacts (id, company_id, name, phone) VALUES ('ct3','c3','Yetkili','05551112233')")
    run = foundation.create_run("company", "data_quality", "tester")
    result = agent_runtime.execute_run(run["id"], "tester")["output"]
    assert result["missing_sector"] == 1
    assert result["missing_city"] == 1
    assert result["missing_address"] == 1
    assert result["missing_phone"] == 1
    assert result["duplicate_name_groups"] == 1
    assert "ABC Makina" not in str(result)


def test_product_catalog_health_checks_integer_price_and_option_links(isolated_database):
    from app import db
    _enable("product")
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO products (id, sku, name, description, currency, unit_price, product_type)
               VALUES ('machine', 'M-1', 'Makine', 'Ana makine', 'EUR', '22000', 'machine')"""
        )
        connection.execute(
            """INSERT INTO products (id, sku, name, description, currency, unit_price, product_type)
               VALUES ('bad-option', 'O-1', 'Opsiyon A', '', 'EUR', '4500.5', 'option')"""
        )
        connection.execute(
            """INSERT INTO products (id, sku, name, description, currency, unit_price, product_type)
               VALUES ('service', 'S-1', 'Servis', 'Servis', 'EUR', '100', 'service')"""
        )
        connection.execute(
            """INSERT INTO products (id, sku, name, description, currency, unit_price, product_type, parent_product_id)
               VALUES ('bad-parent-option', 'O-2', 'Opsiyon B', 'Opsiyon', 'EUR', '500', 'option', 'service')"""
        )
    run = foundation.create_run("product", "catalog_health", "tester")
    result = agent_runtime.execute_run(run["id"], "tester")["output"]
    assert result["missing_description"] == 1
    assert result["invalid_integer_price"] == 1
    assert result["options_without_parent"] == 1
    assert result["options_with_non_machine_parent"] == 1


def test_meeting_follow_up_review_lists_overdue_and_next_week_tasks(isolated_database):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app import db
    _enable("meeting")
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'ABC')")
        connection.executemany(
            """INSERT INTO follow_up_tasks (id, company_id, title, due_date, status, created_at)
               VALUES (?, 'c1', ?, ?, ?, ?)""",
            [
                ("f1", "Gecikmiş", (today - timedelta(days=1)).isoformat(), "open", today.isoformat()),
                ("f2", "Yaklaşan", (today + timedelta(days=3)).isoformat(), "open", today.isoformat()),
                ("f3", "Tamamlandı", (today - timedelta(days=1)).isoformat(), "done", today.isoformat()),
            ],
        )
    run = foundation.create_run("meeting", "follow_up_review", "tester")
    result = agent_runtime.execute_run(run["id"], "tester")["output"]
    assert result["overdue_count"] == 1
    assert result["due_within_7_days_count"] == 1


def test_sales_period_summary_keeps_currency_totals_separate(isolated_database):
    from app import db
    _enable("reporting")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'ABC')")
        connection.execute(
            "INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1','c1','2026-11-01','not')")
        connection.executemany(
            """INSERT INTO quotations
               (id, company_id, currency, subtotal, tax_rate, tax_amount, total, status, created_at)
               VALUES (?, 'c1', ?, ?, '0.20', ?, ?, 'draft', ?)""",
            [("q1", "EUR", "100", "20", "120", "2026-11-01T10:00:00+00:00"),
             ("q2", "TRY", "200", "40", "240", "2026-11-01T10:00:00+00:00")],
        )
    run = foundation.create_run(
        "reporting", "period_summary", "tester",
        {"date_from": "2026-11-01", "date_to": "2026-11-01"},
    )
    result = agent_runtime.execute_run(run["id"], "tester")["output"]
    assert result["meetings"] == 1
    assert result["quotations"] == 2
    assert result["quotation_totals_by_currency"] == {
        "EUR": {"count": 1, "total": "120"}, "TRY": {"count": 1, "total": "240"}
    }


def test_audit_anomaly_review_counts_failed_runs_without_actor_details(isolated_database):
    from app import db
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO agent_runs
               (id, agent_id, task_type, status, input_json, output_json, requested_by, created_at, finished_at)
               VALUES ('failed-1', 'reporting', 'sales_overview', 'failed', '{}', '{}', 'private-user', '2026-11-01', '2026-11-01')"""
        )
    _enable("audit")
    run = foundation.create_run("audit", "anomaly_review", "tester")
    result = agent_runtime.execute_run(run["id"], "tester")["output"]
    assert result["failed_or_blocked_runs"]["failed"] == 1
    assert "private-user" not in str(result)


def test_meeting_product_link_review_reports_broken_catalog_links_and_invalid_values(isolated_database):
    from app import db
    _enable("meeting")
    with db.connect() as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES ('c1', 'Firma A')")
        connection.execute("INSERT INTO products (id, sku, name, currency, unit_price) VALUES ('p1', 'A', 'Makine', 'EUR', '100')")
        connection.execute("INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES ('m1', 'c1', '2026-10-31', '')")
        connection.executemany(
            """INSERT INTO meeting_products
               (id, meeting_id, product_id, name, quantity, unit_price, currency)
               VALUES (?, 'm1', ?, ?, ?, ?, ?)""",
            [("mp1", "p1", "Makine", "1", "100", "EUR"),
             ("mp2", None, "Eski ürün", "1.5", "", "EURO")],
        )
    run = foundation.create_run("meeting", "product_link_review", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["meeting_product_lines"] == 2
    assert output["missing_catalog_link"] == 1
    assert output["invalid_quantity"] == 1
    assert output["invalid_unit_price"] == 1
    assert output["invalid_currency"] == 1


def test_quotation_integrity_review_reports_arithmetic_and_company_anomalies(isolated_database):
    from app import db
    _enable("quotation")
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO quotations
               (id, company_id, currency, subtotal, tax_rate, tax_amount, total, status, created_at)
               VALUES ('q1', NULL, 'EUR', '100', '0.20', '20', '121', 'draft', '2026-10-31')"""
        )
        connection.execute(
            """INSERT INTO quotation_lines
               (id, quotation_id, description, quantity, unit_price, line_total)
               VALUES ('l1', 'q1', 'Makine', '1', '100', '100')"""
        )
    run = foundation.create_run("quotation", "integrity_review", "test-user")
    output = agent_runtime.execute_run(run["id"], "test-user")["output"]
    assert output["missing_company"] == 1
    assert output["subtotal_or_line_total_mismatches"] == 0
    assert output["total_mismatches"] == 1
