from decimal import Decimal
from types import SimpleNamespace

import pytest

from app import ai_usage, db


@pytest.fixture
def usage_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "usage.db"))
    db.init_db()
    ai_usage.init_ai_usage()
    return ai_usage


def test_gpt55_cost_uses_uncached_cached_and_output_rates():
    cost = ai_usage.calculate_cost("gpt-5.5", 1000, 200, 500)
    assert cost == Decimal("0.0191")


def test_unknown_model_cost_is_not_guessed():
    assert ai_usage.calculate_cost("unlisted-model", 100, 0, 50) is None


def test_response_usage_is_saved_without_prompt_or_completion_content(usage_db):
    response = SimpleNamespace(
        id="resp-usage-1",
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            input_tokens_details=SimpleNamespace(cached_tokens=200),
            output_tokens_details=SimpleNamespace(reasoning_tokens=100),
        ),
    )

    assert usage_db.record_response_usage(response, "gpt-5.5", "company", "hashed-session")
    assert not usage_db.record_response_usage(response, "gpt-5.5", "company", "hashed-session")

    summary = usage_db.usage_summary()
    row = summary["agents"][0]
    assert row["agent_id"] == "company"
    assert row["input_tokens"] == 1000
    assert row["cached_input_tokens"] == 200
    assert row["output_tokens"] == 500
    assert row["reasoning_tokens"] == 100
    assert row["requests"] == 1
    assert row["cost_usd"] == pytest.approx(0.0191)
    assert summary["totals"]["cost_usd"] == pytest.approx(0.0191)


def test_missing_usage_is_ignored(usage_db):
    assert not usage_db.record_response_usage(SimpleNamespace(id="resp-no-usage"), "gpt-5.5", "assistant")
    assert usage_db.usage_summary()["totals"]["requests"] == 0


def test_gpt55_long_context_multiplier_is_applied():
    cost = ai_usage.calculate_cost("gpt-5.5", 272001, 0, 1000)
    expected = (272001 * 5 * 2 + 1000 * 30 * 1.5) / 1_000_000
    assert cost == Decimal(str(expected))


def test_daily_budget_blocks_at_limit_and_unknown_pricing(tmp_path, monkeypatch):
    from app import db, ai_usage
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "usage-budget.db"))
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0.01")
    db.init_db()
    ai_usage.init_ai_usage()
    from datetime import datetime, timezone
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO agent_ai_usage
               (response_id, agent_id, model, input_tokens, output_tokens, cost_usd, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("priced", "assistant", "gpt-5.5", 100, 20, "0.02", datetime.now(timezone.utc).isoformat()),
        )
    assert ai_usage.daily_budget_exceeded() is True


def test_daily_budget_is_opt_in_when_not_configured(tmp_path, monkeypatch):
    from app import db, ai_usage
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "usage-no-budget.db"))
    monkeypatch.delenv("OPENAI_DAILY_BUDGET_USD", raising=False)
    db.init_db()
    ai_usage.init_ai_usage()
    assert ai_usage.daily_budget_exceeded() is False
