"""Token usage metering and per-agent cost attribution for Responses API calls.

Only aggregate token metadata is stored; prompts, completions, credentials and customer data
are deliberately excluded. Business sub-agents are deterministic and do not incur model
tokens unless they are explicitly invoked through the AI assistant.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os
from decimal import Decimal
from typing import Any

from app import db

# USD per 1M tokens. Unknown model prices are never guessed.
MODEL_PRICES = {
    "gpt-5.5": {
        "input": Decimal("5.00"),
        "cached_input": Decimal("0.50"),
        "output": Decimal("30.00"),
    },
    "gpt-5.5-2026-04-23": {
        "input": Decimal("5.00"),
        "cached_input": Decimal("0.50"),
        "output": Decimal("30.00"),
    },
}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        result = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, result)


def init_ai_usage() -> None:
    with db.connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS agent_ai_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id TEXT NOT NULL UNIQUE,
                agent_id TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd TEXT,
                session_hash TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_ai_usage_created ON agent_ai_usage(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_ai_usage_agent ON agent_ai_usage(agent_id, created_at)"
        )


def calculate_cost(model: str, input_tokens: int, cached_input_tokens: int,
                   output_tokens: int) -> Decimal | None:
    rates = MODEL_PRICES.get(model)
    if rates is None:
        return None
    cached = min(max(0, cached_input_tokens), max(0, input_tokens))
    uncached = max(0, input_tokens - cached)
    input_multiplier = Decimal("2") if input_tokens > 272_000 else Decimal("1")
    output_multiplier = Decimal("1.5") if input_tokens > 272_000 else Decimal("1")
    return (
        Decimal(uncached) * rates["input"] * input_multiplier
        + Decimal(cached) * rates["cached_input"] * input_multiplier
        + Decimal(max(0, output_tokens)) * rates["output"] * output_multiplier
    ) / Decimal(1_000_000)


def record_response_usage(response: Any, model: str, agent_id: str,
                          session_hash: str | None = None) -> bool:
    usage = _field(response, "usage")
    if usage is None:
        return False
    response_id = _field(response, "id")
    if not isinstance(response_id, str) or not response_id:
        return False
    input_tokens = _nonnegative_int(_field(usage, "input_tokens"))
    output_tokens = _nonnegative_int(_field(usage, "output_tokens"))
    input_details = _field(usage, "input_tokens_details", {}) or {}
    output_details = _field(usage, "output_tokens_details", {}) or {}
    cached_tokens = min(input_tokens, _nonnegative_int(_field(input_details, "cached_tokens")))
    reasoning_tokens = min(output_tokens, _nonnegative_int(_field(output_details, "reasoning_tokens")))
    cost = calculate_cost(model, input_tokens, cached_tokens, output_tokens)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.connect() as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO agent_ai_usage
               (response_id, agent_id, model, input_tokens, cached_input_tokens,
                output_tokens, reasoning_tokens, cost_usd, session_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (response_id, agent_id if agent_id else "assistant", model,
             input_tokens, cached_tokens, output_tokens, reasoning_tokens,
             str(cost) if cost is not None else None,
             session_hash, created_at),
        )
    return cursor.rowcount == 1


def usage_summary() -> dict[str, Any]:
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT agent_id, COUNT(*) AS requests,
                      SUM(input_tokens) AS input_tokens,
                      SUM(cached_input_tokens) AS cached_input_tokens,
                      SUM(output_tokens) AS output_tokens,
                      SUM(reasoning_tokens) AS reasoning_tokens,
                      SUM(CASE WHEN cost_usd IS NOT NULL THEN CAST(cost_usd AS REAL) ELSE 0 END) AS cost_usd,
                      SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced_requests
               FROM agent_ai_usage GROUP BY agent_id ORDER BY agent_id"""
        ).fetchall()
        totals = connection.execute(
            """SELECT COUNT(*) AS requests, COALESCE(SUM(input_tokens),0) AS input_tokens,
                      COALESCE(SUM(cached_input_tokens),0) AS cached_input_tokens,
                      COALESCE(SUM(output_tokens),0) AS output_tokens,
                      COALESCE(SUM(reasoning_tokens),0) AS reasoning_tokens,
                      COALESCE(SUM(CASE WHEN cost_usd IS NOT NULL THEN CAST(cost_usd AS REAL) ELSE 0 END),0) AS cost_usd,
                      COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END),0) AS unpriced_requests
               FROM agent_ai_usage"""
        ).fetchone()
    return {
        "currency": "USD",
        "pricing": {key: str(value) for key, value in MODEL_PRICES.get("gpt-5.5", {}).items()},
        "agents": [dict(row) for row in rows],
        "totals": dict(totals),
    }


def daily_spend_usd() -> Decimal:
    """Return priced API usage recorded since UTC midnight."""
    start = datetime.now(timezone.utc).date().isoformat()
    with db.connect() as connection:
        row = connection.execute(
            """SELECT COALESCE(SUM(CAST(cost_usd AS REAL)), 0) AS cost
               FROM agent_ai_usage WHERE created_at >= ?""",
            (start,),
        ).fetchone()
    return Decimal(str(row["cost"] or 0))


def daily_budget_status() -> dict[str, Any]:
    raw = os.environ.get("OPENAI_DAILY_BUDGET_USD", "").strip()
    try:
        limit = Decimal(raw) if raw else None
    except InvalidOperation:
        limit = None
    spent = daily_spend_usd()
    enabled = limit is not None and limit > 0
    return {
        "enabled": enabled,
        "limit_usd": str(limit) if enabled else None,
        "spent_usd": str(spent),
        "remaining_usd": str(max(Decimal("0"), limit - spent)) if enabled else None,
        "exceeded": bool(enabled and spent >= limit),
    }


def daily_budget_exceeded() -> bool:
    return bool(daily_budget_status()["exceeded"])
