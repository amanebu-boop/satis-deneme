"""Deterministic, read-only business workflow handlers for the agent system.

Each task reads the existing sales database and returns aggregate operational
summaries. No handler mutates company, product, meeting, quotation or stock data.
"""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
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
            "tax_rate": "0.20", "action": "quotation.create_from_meeting"}


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


def _company_data_quality(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("data_quality does not accept input fields")
    with db.connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN sector IS NULL OR trim(sector)='' THEN 1 ELSE 0 END) AS missing_sector,
                      SUM(CASE WHEN city IS NULL OR trim(city)='' THEN 1 ELSE 0 END) AS missing_city,
                      SUM(CASE WHEN address IS NULL OR trim(address)='' THEN 1 ELSE 0 END) AS missing_address,
                      SUM(CASE WHEN (phone_numbers IS NULL OR trim(phone_numbers) IN ('', '[]'))
                               AND NOT EXISTS (
                                 SELECT 1 FROM contacts ct
                                 WHERE ct.company_id=companies.id AND trim(COALESCE(ct.phone,'')) != ''
                               ) THEN 1 ELSE 0 END) AS missing_phone
               FROM companies"""
        ).fetchone()
        duplicates = connection.execute(
            """SELECT COUNT(*) AS total FROM (
                 SELECT lower(trim(name)) FROM companies
                 GROUP BY lower(trim(name)) HAVING COUNT(*) > 1
               )"""
        ).fetchone()["total"]
    return {
        "report": "company_data_quality", "scope": "aggregate_quality_counts",
        "companies": row["total"], "missing_sector": row["missing_sector"] or 0,
        "missing_city": row["missing_city"] or 0, "missing_address": row["missing_address"] or 0,
        "missing_phone": row["missing_phone"] or 0, "duplicate_name_groups": duplicates,
    }


def _product_catalog_health(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("catalog_health does not accept input fields")
    with db.connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN trim(COALESCE(description,''))='' THEN 1 ELSE 0 END) AS missing_description,
                      SUM(CASE WHEN trim(COALESCE(unit_price,''))='' OR unit_price GLOB '*[^0-9]*' THEN 1 ELSE 0 END) AS invalid_integer_price,
                      SUM(CASE WHEN length(trim(COALESCE(currency,''))) != 3 THEN 1 ELSE 0 END) AS invalid_currency,
                      SUM(CASE WHEN product_type='option' AND parent_product_id IS NULL THEN 1 ELSE 0 END) AS options_without_parent,
                      SUM(CASE WHEN product_type='option' AND parent_product_id IS NOT NULL AND
                               COALESCE((SELECT product_type FROM products parent WHERE parent.id=products.parent_product_id),'') != 'machine'
                               THEN 1 ELSE 0 END) AS options_with_non_machine_parent
               FROM products"""
        ).fetchone()
    return {
        "report": "product_catalog_health", "scope": "aggregate_quality_counts",
        "products": row["total"], "missing_description": row["missing_description"] or 0,
        "invalid_integer_price": row["invalid_integer_price"] or 0,
        "invalid_currency": row["invalid_currency"] or 0,
        "options_without_parent": row["options_without_parent"] or 0,
        "options_with_non_machine_parent": row["options_with_non_machine_parent"] or 0,
    }


def _meeting_follow_up_review(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("follow_up_review does not accept input fields")
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    horizon = (today + timedelta(days=7)).isoformat()
    today_text = today.isoformat()
    with db.connect() as connection:
        counts = connection.execute(
            """SELECT
                 SUM(CASE WHEN status='open' AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
                 SUM(CASE WHEN status='open' AND due_date >= ? AND due_date <= ? THEN 1 ELSE 0 END) AS due_soon
               FROM follow_up_tasks""",
            (today_text, today_text, horizon),
        ).fetchone()
        rows = connection.execute(
            """SELECT t.id, c.name AS company_name, t.title, t.due_date
               FROM follow_up_tasks t JOIN companies c ON c.id=t.company_id
               WHERE t.status='open' AND t.due_date <= ?
               ORDER BY t.due_date, c.name LIMIT 50""",
            (horizon,),
        ).fetchall()
    overdue = [dict(row) for row in rows if str(row["due_date"]) < today_text]
    due_soon = [dict(row) for row in rows if str(row["due_date"]) >= today_text]
    return {
        "report": "meeting_follow_up_review", "as_of": today_text,
        "overdue_count": counts["overdue"] or 0, "due_within_7_days_count": counts["due_soon"] or 0,
        "details_are_limited_to_50": True, "overdue": overdue, "due_soon": due_soon,
    }


def _audit_anomaly_review(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("anomaly_review does not accept input fields")
    with db.connect() as connection:
        run_counts = connection.execute(
            """SELECT status, COUNT(*) AS total FROM agent_runs
               WHERE status IN ('failed','blocked') GROUP BY status"""
        ).fetchall()
        approval_counts = connection.execute(
            """SELECT status, COUNT(*) AS total FROM agent_approvals
               WHERE status IN ('expired','rejected') GROUP BY status"""
        ).fetchall()
        unprocessed_expired = connection.execute(
            """SELECT COUNT(*) AS total FROM agent_approvals
               WHERE status='pending' AND expires_at <= ?""",
            (datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),),
        ).fetchone()["total"]
        failure_events = connection.execute(
            """SELECT event_type, COUNT(*) AS total FROM agent_audit_logs
               WHERE event_type IN ('run_failed','run_blocked','external_run_failed')
               GROUP BY event_type ORDER BY event_type"""
        ).fetchall()
    return {
        "report": "audit_anomaly_review", "scope": "counts_only_no_actor_details",
        "failed_or_blocked_runs": {str(row["status"]): row["total"] for row in run_counts},
        "rejected_or_expired_approvals": {str(row["status"]): row["total"] for row in approval_counts},
        "pending_approvals_past_expiry": unprocessed_expired,
        "failure_events": {str(row["event_type"]): row["total"] for row in failure_events},
    }


def _sales_period_summary(input_data: dict[str, Any]) -> dict[str, Any]:
    if set(input_data) != {"date_from", "date_to"}:
        raise ValueError("period_summary requires date_from and date_to")
    try:
        start = date.fromisoformat(str(input_data["date_from"]))
        end = date.fromisoformat(str(input_data["date_to"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("Tarih aralığı YYYY-MM-DD biçiminde olmalıdır") from exc
    if start.isoformat() != input_data["date_from"] or end.isoformat() != input_data["date_to"]:
        raise ValueError("Tarih biçimi tam olarak YYYY-MM-DD olmalıdır")
    if start > end or (end - start).days > 3660:
        raise ValueError("Tarih aralığı geçersiz veya 10 yıldan uzun")
    with db.connect() as connection:
        meetings = connection.execute(
            "SELECT COUNT(*) AS total FROM meetings WHERE meeting_date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()["total"]
        quotations = connection.execute(
            "SELECT COUNT(*) AS total FROM quotations WHERE substr(created_at,1,10) BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()["total"]
        total_rows = connection.execute(
            """SELECT currency, total FROM quotations
               WHERE substr(created_at,1,10) BETWEEN ? AND ? ORDER BY currency""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        statuses = connection.execute(
            """SELECT status, COUNT(*) AS total FROM quotations
               WHERE substr(created_at,1,10) BETWEEN ? AND ?
               GROUP BY status ORDER BY status""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for row in total_rows:
        currency = str(row["currency"])
        totals[currency] = totals.get(currency, Decimal("0")) + Decimal(str(row["total"] or "0"))
        counts[currency] = counts.get(currency, 0) + 1
    return {
        "report": "sales_period_summary", "date_from": start.isoformat(), "date_to": end.isoformat(),
        "meetings": meetings, "quotations": quotations,
        "quotation_totals_by_currency": {
            currency: {"count": counts[currency], "total": format(total, "f")}
            for currency, total in totals.items()
        },
        "quotations_by_status": {str(row["status"]): row["total"] for row in statuses},
        "currency_totals_are_not_converted": True,
    }


def _meeting_product_link_review(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("product_link_review does not accept input fields")
    sql = """SELECT COUNT(*) AS total,
        SUM(CASE WHEN mp.product_id IS NULL OR p.id IS NULL THEN 1 ELSE 0 END) AS missing_catalog_link,
        SUM(CASE WHEN trim(COALESCE(mp.name,''))='' THEN 1 ELSE 0 END) AS missing_product_name,
        SUM(CASE WHEN trim(COALESCE(mp.quantity,''))='' OR mp.quantity GLOB '*[^0-9]*' OR CAST(mp.quantity AS INTEGER)<1 THEN 1 ELSE 0 END) AS invalid_quantity,
        SUM(CASE WHEN trim(COALESCE(mp.unit_price,''))='' OR mp.unit_price GLOB '*[^0-9]*' OR CAST(mp.unit_price AS INTEGER)<0 THEN 1 ELSE 0 END) AS invalid_unit_price,
        SUM(CASE WHEN length(trim(COALESCE(mp.currency,'')))!=3 OR (p.currency IS NOT NULL AND trim(p.currency)!=trim(mp.currency)) THEN 1 ELSE 0 END) AS invalid_currency
        FROM meeting_products mp LEFT JOIN products p ON p.id=mp.product_id"""
    with db.connect() as connection:
        row = connection.execute(sql).fetchone()
    return {
        "report": "meeting_product_link_review", "scope": "aggregate_quality_counts",
        "meeting_product_lines": row["total"],
        "missing_catalog_link": row["missing_catalog_link"] or 0,
        "missing_product_name": row["missing_product_name"] or 0,
        "invalid_quantity": row["invalid_quantity"] or 0,
        "invalid_unit_price": row["invalid_unit_price"] or 0,
        "invalid_currency": row["invalid_currency"] or 0,
    }


def _quotation_integrity_review(input_data: dict[str, Any]) -> dict[str, Any]:
    if input_data:
        raise ValueError("integrity_review does not accept input fields")
    with db.connect() as connection:
        quotations = [dict(row) for row in connection.execute(
            "SELECT id, company_id, subtotal, tax_amount, total FROM quotations"
        ).fetchall()]
        lines = {
            quote["id"]: [dict(row) for row in connection.execute(
                "SELECT quantity, unit_price, line_total FROM quotation_lines WHERE quotation_id=?",
                (quote["id"],)
            ).fetchall()]
            for quote in quotations
        }
    missing_company = missing_lines = invalid_lines = subtotal_mismatches = total_mismatches = 0
    for quote in quotations:
        quote_lines = lines[quote["id"]]
        missing_company += int(not quote["company_id"])
        missing_lines += int(not quote_lines)
        computed = 0
        valid = True
        for line in quote_lines:
            try:
                quantity_text, price_text = str(line["quantity"]).strip(), str(line["unit_price"]).strip()
                quantity, price = int(quantity_text), int(price_text)
                if str(quantity) != quantity_text or str(price) != price_text or quantity < 1 or price < 0:
                    raise ValueError("invalid integer")
                computed += quantity * price
                if Decimal(str(line["line_total"])) != Decimal(quantity * price):
                    valid = False
            except (TypeError, ValueError, ArithmeticError):
                invalid_lines += 1
                valid = False
        try:
            subtotal = Decimal(str(quote["subtotal"]))
            tax = Decimal(str(quote["tax_amount"]))
            total = Decimal(str(quote["total"]))
            if subtotal != Decimal(computed) or not valid:
                subtotal_mismatches += 1
            if total != subtotal + tax:
                total_mismatches += 1
        except (TypeError, ValueError, ArithmeticError):
            subtotal_mismatches += 1
            total_mismatches += 1
    return {
        "report": "quotation_integrity_review", "scope": "aggregate_quality_counts",
        "quotations": len(quotations), "missing_company": missing_company,
        "missing_lines": missing_lines, "invalid_line_values": invalid_lines,
        "subtotal_or_line_total_mismatches": subtotal_mismatches,
        "total_mismatches": total_mismatches,
    }


HANDLERS = {
    ("reporting", "sales_overview"): _sales_overview,
    ("reporting", "period_summary"): _sales_period_summary,
    ("audit", "audit_overview"): _audit_overview,
    ("audit", "anomaly_review"): _audit_anomaly_review,
    ("company", "directory_overview"): _company_directory_overview,
    ("company", "data_quality"): _company_data_quality,
    ("product", "catalog_overview"): _product_catalog_overview,
    ("product", "catalog_health"): _product_catalog_health,
    ("meeting", "activity_overview"): _meeting_activity_overview,
    ("meeting", "follow_up_review"): _meeting_follow_up_review,
    ("meeting", "product_link_review"): _meeting_product_link_review,
    ("quotation", "pipeline_overview"): _quotation_pipeline_overview,
    ("quotation", "integrity_review"): _quotation_integrity_review,
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
