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
