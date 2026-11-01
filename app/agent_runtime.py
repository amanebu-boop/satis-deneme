"""Deterministic, read-only business workflow handlers for the agent system.

Each task reads the existing sales database and returns aggregate operational
summaries. No handler mutates company, product, meeting, quotation or stock data.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app import db
from app import agent_foundation as foundation
from app.agent_instructions import load_agent_instructions


def _sales_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("sales_overview does not accept input fields")
    with db.connect() as connection:
        companies = connection.execute("SELECT COUNT(*) AS total FROM companies").fetchone()["total"]
        meetings = connection.execute("SELECT COUNT(*) AS total FROM meetings").fetchone()["total"]
        products = connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]
        quotations = connection.execute("SELECT COUNT(*) AS total FROM quotations").fetchone()["total"]
        quote_statuses = connection.execute("SELECT status, COUNT(*) AS total FROM quotations GROUP BY status ORDER BY status").fetchall()
        quote_currencies = connection.execute("SELECT currency, COUNT(*) AS total FROM quotations GROUP BY currency ORDER BY currency").fetchall()
        follow_up_statuses = connection.execute("SELECT status, COUNT(*) AS total FROM follow_up_tasks GROUP BY status ORDER BY status").fetchall()
    return {
        "report": "sales_overview", "scope": "aggregate_counts_only",
        "companies": companies, "meetings": meetings, "products": products, "quotations": quotations,
        "quotations_by_status": {str(row["status"] or "unknown"): row["total"] for row in quote_statuses},
        "quotations_by_currency": {str(row["currency"] or "unknown"): row["total"] for row in quote_currencies},
        "follow_ups_by_status": {str(row["status"] or "unknown"): row["total"] for row in follow_up_statuses},
    }


def _company_directory_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("directory_overview does not accept input fields")
    with db.connect() as connection:
        companies = connection.execute("SELECT COUNT(*) AS total FROM companies").fetchone()["total"]
        contacts = connection.execute("SELECT COUNT(*) AS total FROM contacts").fetchone()["total"]
        companies_with_meetings = connection.execute(
            "SELECT COUNT(DISTINCT company_id) AS total FROM meetings"
        ).fetchone()["total"]
        companies_with_follow_ups = connection.execute(
            "SELECT COUNT(DISTINCT company_id) AS total FROM follow_up_tasks WHERE status = 'open'"
        ).fetchone()["total"]
    return {
        "report": "company_directory_overview", "scope": "aggregate_counts_only",
        "companies": companies, "contacts": contacts,
        "companies_with_meetings": companies_with_meetings,
        "companies_with_open_follow_ups": companies_with_follow_ups,
    }


def _product_catalog_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("catalog_overview does not accept input fields")
    with db.connect() as connection:
        total = connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]
        by_type = connection.execute(
            "SELECT product_type, COUNT(*) AS total FROM products GROUP BY product_type ORDER BY product_type"
        ).fetchall()
        by_currency = connection.execute(
            "SELECT currency, COUNT(*) AS total FROM products GROUP BY currency ORDER BY currency"
        ).fetchall()
        linked_options = connection.execute(
            "SELECT COUNT(*) AS total FROM products WHERE product_type = 'option' AND parent_product_id IS NOT NULL"
        ).fetchone()["total"]
    return {
        "report": "product_catalog_overview", "scope": "aggregate_counts_only",
        "products": total, "products_by_type": {str(r["product_type"]): r["total"] for r in by_type},
        "products_by_currency": {str(r["currency"]): r["total"] for r in by_currency},
        "linked_options": linked_options,
    }


def _meeting_activity_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("activity_overview does not accept input fields")
    with db.connect() as connection:
        total = connection.execute("SELECT COUNT(*) AS total FROM meetings").fetchone()["total"]
        by_type = connection.execute(
            "SELECT meeting_type, COUNT(*) AS total FROM meetings GROUP BY meeting_type ORDER BY meeting_type"
        ).fetchall()
        product_lines = connection.execute("SELECT COUNT(*) AS total FROM meeting_products").fetchone()["total"]
        meetings_with_products = connection.execute(
            "SELECT COUNT(DISTINCT meeting_id) AS total FROM meeting_products"
        ).fetchone()["total"]
        companies = connection.execute(
            "SELECT COUNT(DISTINCT company_id) AS total FROM meetings"
        ).fetchone()["total"]
    return {
        "report": "meeting_activity_overview", "scope": "aggregate_counts_only",
        "meetings": total, "meetings_by_type": {str(r["meeting_type"]): r["total"] for r in by_type},
        "meeting_product_lines": product_lines, "meetings_with_products": meetings_with_products,
        "companies_with_meetings": companies,
    }


def _quotation_pipeline_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("pipeline_overview does not accept input fields")
    with db.connect() as connection:
        total = connection.execute("SELECT COUNT(*) AS total FROM quotations").fetchone()["total"]
        by_status = connection.execute(
            "SELECT status, COUNT(*) AS total FROM quotations GROUP BY status ORDER BY status"
        ).fetchall()
        rows = connection.execute(
            "SELECT currency, total FROM quotations ORDER BY currency"
        ).fetchall()
    totals: dict[str, Decimal] = {}
    for row in rows:
        currency = str(row["currency"] or "unknown")
        totals[currency] = totals.get(currency, Decimal("0")) + Decimal(str(row["total"] or "0"))
    return {
        "report": "quotation_pipeline_overview", "scope": "aggregate_counts_only",
        "quotations": total, "quotations_by_status": {str(r["status"] or "unknown"): r["total"] for r in by_status},
        "quotation_value_by_currency": {key: format(value, "f") for key, value in totals.items()},
    }



def _prepare_quotation_from_meeting(input_data: dict[str, Any]) -> dict[str, Any]:
    meeting_id = input_data.get("meeting_id")
    if set(input_data) != {"meeting_id"} or not isinstance(meeting_id, str) or not meeting_id.strip():
        raise ValueError("prepare_from_meeting requires only a valid meeting_id")
    with db.connect() as connection:
        meeting = connection.execute(
            """SELECT m.id, m.company_id, c.name AS company_name
               FROM meetings m JOIN companies c ON c.id = m.company_id WHERE m.id = ?""",
            (meeting_id.strip(),),
        ).fetchone()
        if meeting is None:
            raise ValueError("Görüşme veya bağlı firma bulunamadı")
        rows = connection.execute(
            """SELECT id, product_id, sku, name, quantity, unit_price, currency
               FROM meeting_products WHERE meeting_id = ? ORDER BY rowid""",
            (meeting_id.strip(),),
        ).fetchall()
    if not rows:
        raise ValueError("Görüşmede teklif taslağına aktarılacak ürün bulunmuyor")
    currencies = {str(row["currency"] or "").strip() for row in rows}
    if len(currencies) != 1 or "" in currencies:
        raise ValueError("Görüşme ürünlerinin para birimleri aynı ve tanımlı olmalıdır")
    currency = next(iter(currencies))
    if currency != "EUR":
        raise ValueError("Mevcut teklif altyapısı yalnızca EUR para birimini destekliyor")
    lines = []
    for index, row in enumerate(rows, start=1):
        try:
            quantity_text, price_text = str(row["quantity"]).strip(), str(row["unit_price"]).strip()
            quantity, unit_price = int(quantity_text), int(price_text)
        except (TypeError, ValueError):
            raise ValueError(f"{index}. ürün satırında miktar veya birim fiyat tam sayı değil")
        if str(quantity) != quantity_text or str(unit_price) != price_text or quantity < 1 or unit_price < 0:
            raise ValueError(f"{index}. ürün satırında miktar en az 1, fiyat sıfır veya üzeri tam sayı olmalıdır")
        lines.append({"description": str(row["name"]).strip(), "quantity": quantity, "unit_price": unit_price,
                      "meeting_product_id": row["id"], "product_id": row["product_id"], "sku": row["sku"]})
    return {"report": "quotation_prepare_from_meeting", "scope": "draft_preview_only",
            "meeting_id": meeting["id"], "company_id": meeting["company_id"], "company_name": meeting["company_name"],
            "currency": currency, "lines": lines, "line_count": len(lines),
            "subtotal": str(sum(line["quantity"] * line["unit_price"] for line in lines)),
            "discount": "none", "tax_rate": "0.20", "action": "quotation.create_from_meeting"}


def _audit_overview(input_data: dict[str, Any]) -> dict[str, Any]:
    """Return aggregate audit health only; never expose actors or event details."""
    if input_data:
        raise ValueError("audit_overview does not accept input fields")
    with db.connect() as connection:
        total_events = connection.execute(
            "SELECT COUNT(*) AS total FROM agent_audit_logs"
        ).fetchone()["total"]
        events_by_type = connection.execute(
            "SELECT event_type, COUNT(*) AS total FROM agent_audit_logs GROUP BY event_type ORDER BY event_type"
        ).fetchall()
        runs_by_status = connection.execute(
            "SELECT status, COUNT(*) AS total FROM agent_runs GROUP BY status ORDER BY status"
        ).fetchall()
        approvals_by_status = connection.execute(
            "SELECT status, COUNT(*) AS total FROM agent_approvals GROUP BY status ORDER BY status"
        ).fetchall()
    return {
        "report": "audit_overview",
        "scope": "aggregate_counts_only",
        "audit_events": total_events,
        "events_by_type": {str(row["event_type"]): row["total"] for row in events_by_type},
        "agent_runs_by_status": {str(row["status"]): row["total"] for row in runs_by_status},
        "approvals_by_status": {str(row["status"]): row["total"] for row in approvals_by_status},
    }


HANDLERS = {
    ("reporting", "sales_overview"): _sales_overview,
    ("audit", "audit_overview"): _audit_overview,
    ("company", "directory_overview"): _company_directory_overview,
    ("product", "catalog_overview"): _product_catalog_overview,
    ("meeting", "activity_overview"): _meeting_activity_overview,
    ("quotation", "pipeline_overview"): _quotation_pipeline_overview,
    ("quotation", "prepare_from_meeting"): _prepare_quotation_from_meeting,
}


def execute_run(run_id: str, executed_by: str) -> dict[str, Any]:
    """Execute one queued, enabled, allowlisted read-only agent task."""
    if not executed_by or not executed_by.strip():
        raise ValueError("executed_by must be non-empty")
    with db.connect() as connection:
        row = connection.execute(
            """SELECT r.id, r.agent_id, r.task_type, r.status, r.input_json, a.enabled
               FROM agent_runs r JOIN agents a ON a.id = r.agent_id WHERE r.id = ?""",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown run")
        if not row["enabled"]:
            raise ValueError("agent is disabled")
        if row["status"] != "queued":
            raise ValueError("run is not queued")
        load_agent_instructions(row["agent_id"], row["task_type"])
        handler = HANDLERS.get((row["agent_id"], row["task_type"]))
        if handler is None:
            raise ValueError("unsupported agent task")
        changed = connection.execute(
            "UPDATE agent_runs SET status = 'running' WHERE id = ? AND status = 'queued'", (run_id,)
        ).rowcount
        if changed != 1:
            raise ValueError("run is not queued")
        foundation._audit(
            connection, "run_started", actor=executed_by.strip(),
            agent_id=row["agent_id"], run_id=run_id, details={"task_type": row["task_type"]},
        )
        input_data = json.loads(row["input_json"])
    try:
        output = handler(input_data)
    except Exception as exc:
        with db.connect() as connection:
            connection.execute(
                """UPDATE agent_runs SET status = 'failed', finished_at = ?, output_json = ?
                   WHERE id = ? AND status = 'running'""",
                (foundation._now(), json.dumps({"error": str(exc)}, ensure_ascii=False), run_id),
            )
            foundation._audit(
                connection, "run_failed", actor=executed_by.strip(), agent_id=row["agent_id"],
                run_id=run_id, details={"error": str(exc), "task_type": row["task_type"]},
            )
        raise
    serialized = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with db.connect() as connection:
        changed = connection.execute(
            """UPDATE agent_runs SET status = 'succeeded', output_json = ?, finished_at = ?
               WHERE id = ? AND status = 'running'""",
            (serialized, foundation._now(), run_id),
        ).rowcount
        if changed != 1:
            raise RuntimeError("run state changed during execution")
        foundation._audit(
            connection, "run_succeeded", actor=executed_by.strip(),
            agent_id=row["agent_id"], run_id=run_id, details={"task_type": row["task_type"]},
        )
    return {"id": run_id, "status": "succeeded", "output": output}
