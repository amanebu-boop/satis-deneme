from __future__ import annotations

import pytest

from app import agent_foundation as agents


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales-test.db"))
    from app import db
    db.init_db()
    agents.init_agent_foundation()
    return tmp_path / "sales-test.db"


def test_registry_is_seeded_disabled_and_initialization_is_idempotent(isolated_database):
    first = agents.list_agents()
    agents.init_agent_foundation()
    second = agents.list_agents()

    assert len(first) == 8
    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert all(item["enabled"] is False for item in second)
    assert {rule["key"] for rule in agents.list_rules()} >= {
        "critical_actions_require_approval",
        "external_ai_enabled",
        "automatic_business_writes_enabled",
    }


def test_disabled_agent_run_is_blocked_and_idempotent(isolated_database):
    first = agents.create_run(
        "quotation", "prepare_draft", "test-user",
        {"company_id": "example"}, idempotency_key="request-1",
    )
    duplicate = agents.create_run(
        "quotation", "prepare_draft", "test-user",
        {"company_id": "example"}, idempotency_key="request-1",
    )

    assert first["status"] == "blocked"
    assert duplicate["id"] == first["id"]


def test_approval_is_bound_to_exact_payload_and_can_be_reviewed(isolated_database):
    from app import db
    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'quotation'")
    run = agents.create_run("quotation", "prepare_draft", "test-user")
    approval = agents.request_approval(
        run["id"], "create_quotation", {"company_id": "company-1"}, "test-user"
    )

    with pytest.raises(ValueError, match="payload changed"):
        agents.review_approval(
            approval["id"], "approved", "reviewer",
            current_payload={"company_id": "company-2"},
        )

    reviewed = agents.review_approval(
        approval["id"], "approved", "reviewer",
        current_payload={"company_id": "company-1"},
    )
    assert reviewed["status"] == "approved"


def test_unknown_agent_and_invalid_ttl_are_rejected(isolated_database):
    with pytest.raises(ValueError, match="unknown agent"):
        agents.create_run("not-an-agent", "task", "test-user")

    run = agents.create_run("audit", "inspect", "test-user")
    with pytest.raises(ValueError, match="ttl_seconds"):
        agents.request_approval(run["id"], "dangerous_action", {}, "test-user", ttl_seconds=0)


def test_blocked_run_cannot_receive_approval(isolated_database):
    run = agents.create_run("quotation", "prepare_draft", "test-user")

    with pytest.raises(ValueError, match="not eligible"):
        agents.request_approval(
            run["id"], "create_quotation", {"company_id": "company-1"}, "test-user"
        )


def test_read_models_include_run_approval_and_audit_records(isolated_database):
    run = agents.create_run(
        "audit", "inspect_records", "test-user", idempotency_key="audit-run-1"
    )
    assert agents.list_runs()[0]["id"] == run["id"]
    assert agents.list_audit_logs()[0]["event_type"] == "run_blocked"
    assert agents.list_approvals() == []


def test_idempotency_key_cannot_be_reused_for_different_payload(isolated_database):
    agents.create_run(
        "audit", "inspect_records", "test-user",
        {"scope": "companies"}, idempotency_key="same-key",
    )

    with pytest.raises(ValueError, match="different request"):
        agents.create_run(
            "audit", "inspect_records", "test-user",
            {"scope": "quotes"}, idempotency_key="same-key",
        )


def test_expired_approval_state_is_persisted(isolated_database):
    from datetime import datetime, timedelta, timezone
    from app import db

    with db.connect() as connection:
        connection.execute("UPDATE agents SET enabled = 1 WHERE id = 'audit'")
    run = agents.create_run("audit", "inspect_records", "test-user")
    approval = agents.request_approval(
        run["id"], "inspect", {"scope": "audit"}, "test-user"
    )
    with db.connect() as connection:
        connection.execute(
            "UPDATE agent_approvals SET expires_at = ? WHERE id = ?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), approval["id"]),
        )

    with pytest.raises(ValueError, match="expired"):
        agents.review_approval(approval["id"], "approved", "reviewer")

    assert agents.list_approvals()[0]["status"] == "expired"


def test_reporting_agent_can_be_explicitly_enabled_and_disabled_with_audit(isolated_database):
    enabled = agents.set_agent_enabled("reporting", True, "test-user")
    assert enabled["enabled"] is True

    disabled = agents.set_agent_enabled("reporting", False, "test-user")
    assert disabled["enabled"] is False

    events = [item["event_type"] for item in agents.list_audit_logs()]
    assert events[:2] == ["agent_disabled", "agent_enabled"]


def test_agent_status_change_rejects_unknown_agent_and_invalid_actor(isolated_database):
    with pytest.raises(ValueError, match="unknown agent"):
        agents.set_agent_enabled("missing", True, "test-user")

    with pytest.raises(ValueError, match="actor"):
        agents.set_agent_enabled("reporting", True, "")

    with pytest.raises(ValueError, match="boolean"):
        agents.set_agent_enabled("reporting", 1, "test-user")
