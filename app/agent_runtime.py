"""Safe deterministic agent execution handlers.

The first runtime capability is a read-only sales overview. SQL aggregates are
computed in the database so customer details are never loaded into the handler.
"""
from __future__ import annotations

import json
from typing import Any

from app import db
from app import agent_foundation as foundation


def _sales_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("sales_overview does not accept input fields")

    with db.connect() as connection:
        companies = connection.execute("SELECT COUNT(*) AS total FROM companies").fetchone()["total"]
        meetings = connection.execute("SELECT COUNT(*) AS total FROM meetings").fetchone()["total"]
        products = connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]
        quotations = connection.execute("SELECT COUNT(*) AS total FROM quotations").fetchone()["total"]
        quote_statuses = connection.execute(
            "SELECT status, COUNT(*) AS total FROM quotations GROUP BY status ORDER BY status"
        ).fetchall()
        quote_currencies = connection.execute(
            "SELECT currency, COUNT(*) AS total FROM quotations GROUP BY currency ORDER BY currency"
        ).fetchall()
        follow_up_statuses = connection.execute(
            "SELECT status, COUNT(*) AS total FROM follow_up_tasks GROUP BY status ORDER BY status"
        ).fetchall()

    return {
        "report": "sales_overview",
        "scope": "aggregate_counts_only",
        "companies": companies,
        "meetings": meetings,
        "products": products,
        "quotations": quotations,
        "quotations_by_status": {str(row["status"] or "unknown"): row["total"] for row in quote_statuses},
        "quotations_by_currency": {str(row["currency"] or "unknown"): row["total"] for row in quote_currencies},
        "follow_ups_by_status": {str(row["status"] or "unknown"): row["total"] for row in follow_up_statuses},
    }


HANDLERS = {
    ("reporting", "sales_overview"): _sales_overview,
}


def execute_run(run_id: str, executed_by: str) -> dict[str, Any]:
    """Execute one queued, enabled, allowlisted read-only agent task."""
    if not executed_by or not executed_by.strip():
        raise ValueError("executed_by must be non-empty")

    with db.connect() as connection:
        row = connection.execute(
            """SELECT r.id, r.agent_id, r.task_type, r.status, r.input_json,
                      a.enabled
               FROM agent_runs r JOIN agents a ON a.id = r.agent_id
               WHERE r.id = ?""",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown run")
        if not row["enabled"]:
            raise ValueError("agent is disabled")
        if row["status"] != "queued":
            raise ValueError("run is not queued")
        handler = HANDLERS.get((row["agent_id"], row["task_type"]))
        if handler is None:
            raise ValueError("unsupported agent task")
        changed = connection.execute(
            "UPDATE agent_runs SET status = 'running' WHERE id = ? AND status = 'queued'",
            (run_id,),
        ).rowcount
        if changed != 1:
            raise ValueError("run is not queued")
        foundation._audit(
            connection, "run_started", actor=executed_by.strip(),
            agent_id=row["agent_id"], run_id=run_id,
            details={"task_type": row["task_type"]},
        )
        input_data = json.loads(row["input_json"])

    try:
        output = handler(input_data)
    except Exception as exc:
        with db.connect() as connection:
            connection.execute(
                """UPDATE agent_runs SET status = 'failed', finished_at = ?,
                   output_json = ? WHERE id = ? AND status = 'running'""",
                (foundation._now(), json.dumps({"error": str(exc)}, ensure_ascii=False), run_id),
            )
            foundation._audit(
                connection, "run_failed", actor=executed_by.strip(),
                agent_id=row["agent_id"], run_id=run_id,
                details={"error": str(exc), "task_type": row["task_type"]},
            )
        raise

    serialized = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with db.connect() as connection:
        changed = connection.execute(
            """UPDATE agent_runs SET status = 'succeeded', output_json = ?,
               finished_at = ? WHERE id = ? AND status = 'running'""",
            (serialized, foundation._now(), run_id),
        ).rowcount
        if changed != 1:
            raise RuntimeError("run state changed during execution")
        foundation._audit(
            connection, "run_succeeded", actor=executed_by.strip(),
            agent_id=row["agent_id"], run_id=run_id,
            details={"task_type": row["task_type"]},
        )
    return {"id": run_id, "status": "succeeded", "output": output}
