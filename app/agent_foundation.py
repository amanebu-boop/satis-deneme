"""Deterministic agent foundation.

This module provides persistence and safety primitives only. It does not execute
business actions, call external AI services, or grant agents access to customer data.
All agents start disabled and must be explicitly enabled in a later, authenticated
administration workflow.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from app import db


AGENT_DEFINITIONS = (
    ("company", "Firma Ajanı", "Firma kayıtlarını analiz etmek ve düzenlemek için altyapı."),
    ("product", "Ürün Ajanı", "Ürün kataloğunu analiz etmek için altyapı."),
    ("meeting", "Görüşme Ajanı", "Görüşme kayıtlarını yapılandırmak için altyapı."),
    ("quotation", "Teklif Ajanı", "Teklif hazırlama akışını desteklemek için altyapı."),
    ("warehouse", "Depo Ajanı", "Stok altyapısı tamamlanana kadar pasif tutulur."),
    ("sales", "Satış Ajanı", "Satış süreçlerini analiz etmek için altyapı."),
    ("reporting", "Raporlama Ajanı", "Raporlama ve özetleme için altyapı."),
    ("audit", "Denetim Ajanı", "İşlem ve güvenlik kayıtlarını incelemek için altyapı."),
)

DEFAULT_RULES = (
    ("critical_actions_require_approval", {"enabled": True}),
    ("approval_ttl_seconds", {"value": 900}),
    ("external_ai_enabled", {"enabled": False}),
    ("automatic_business_writes_enabled", {"enabled": False}),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _audit(
    connection,
    event_type: str,
    actor: str = "system",
    agent_id: str | None = None,
    run_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """INSERT INTO agent_audit_logs
           (id, agent_id, run_id, actor, event_type, details_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid4()), agent_id, run_id, actor, event_type, _json(details or {}), _now()),
    )


def init_agent_foundation() -> None:
    """Create agent tables and idempotently seed the disabled agent registry."""
    with db.connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                task_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('blocked', 'pending_approval', 'queued', 'running', 'succeeded', 'failed', 'cancelled')),
                input_json TEXT NOT NULL DEFAULT '{}',
                output_json TEXT,
                requested_by TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_rules (
                id TEXT PRIMARY KEY,
                rule_key TEXT NOT NULL UNIQUE,
                config_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_approvals (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                action_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'expired')),
                requested_by TEXT NOT NULL,
                reviewed_by TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_audit_logs (
                id TEXT PRIMARY KEY,
                agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
                run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_created
                ON agent_runs(agent_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_agent_approvals_status_expiry
                ON agent_approvals(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_agent_audit_created
                ON agent_audit_logs(created_at);
            CREATE TABLE IF NOT EXISTS agent_approval_actions (
                approval_id TEXT PRIMARY KEY REFERENCES agent_approvals(id),
                action_type TEXT NOT NULL,
                quotation_id TEXT NOT NULL UNIQUE,
                executed_at TEXT NOT NULL
            );
            """
        )
        now = _now()
        for agent_id, name, description in AGENT_DEFINITIONS:
            connection.execute(
                """INSERT OR IGNORE INTO agents
                   (id, name, description, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, 0, ?, ?)""",
                (agent_id, name, description, now, now),
            )
        for rule_key, config in DEFAULT_RULES:
            connection.execute(
                """INSERT OR IGNORE INTO agent_rules
                   (id, rule_key, config_json, updated_at) VALUES (?, ?, ?, ?)""",
                (str(uuid4()), rule_key, _json(config), now),
            )
        _audit(connection, "agent_foundation_initialized", details={"agents_seeded": len(AGENT_DEFINITIONS)})


def set_agent_enabled(agent_id: str, enabled: bool, actor: str) -> dict[str, Any]:
    """Explicitly enable or disable one registered agent and audit the change."""
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    if not actor or not actor.strip():
        raise ValueError("actor must be non-empty")
    with db.connect() as connection:
        row = connection.execute(
            "SELECT id, name, enabled FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown agent")
        previous = bool(row["enabled"])
        connection.execute(
            "UPDATE agents SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, _now(), agent_id),
        )
        if previous != enabled:
            _audit(
                connection,
                "agent_enabled" if enabled else "agent_disabled",
                actor=actor.strip(),
                agent_id=agent_id,
                details={"previous_enabled": previous, "enabled": enabled},
            )
        updated = connection.execute(
            """SELECT id, name, description, enabled, created_at, updated_at
               FROM agents WHERE id = ?""",
            (agent_id,),
        ).fetchone()
    return {**dict(updated), "enabled": bool(updated["enabled"])}


def list_agents() -> list[dict[str, Any]]:
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT id, name, description, enabled, created_at, updated_at
               FROM agents ORDER BY rowid"""
        ).fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"])} for row in rows]


def list_rules() -> list[dict[str, Any]]:
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT rule_key, config_json, updated_at FROM agent_rules ORDER BY rule_key"
        ).fetchall()
    return [
        {"key": row["rule_key"], "config": json.loads(row["config_json"]), "updated_at": row["updated_at"]}
        for row in rows
    ]


def create_run(
    agent_id: str,
    task_type: str,
    requested_by: str,
    input_data: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Record a run request; disabled agents are blocked and nothing is executed."""
    if not task_type or not task_type.strip():
        raise ValueError("task_type must be non-empty")
    if not requested_by or not requested_by.strip():
        raise ValueError("requested_by must be non-empty")
    payload = input_data or {}
    serialized = _json(payload)
    with db.connect() as connection:
        if idempotency_key:
            existing = connection.execute(
                "SELECT * FROM agent_runs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if existing is not None:
                same_request = (
                    existing["agent_id"] == agent_id
                    and existing["task_type"] == task_type.strip()
                    and existing["requested_by"] == requested_by.strip()
                    and existing["input_json"] == serialized
                )
                if not same_request:
                    raise ValueError("idempotency key was already used for a different request")
                return dict(existing)
        agent = connection.execute("SELECT enabled FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if agent is None:
            raise ValueError("unknown agent")
        run_id = str(uuid4())
        status = "queued" if agent["enabled"] else "blocked"
        connection.execute(
            """INSERT INTO agent_runs
               (id, agent_id, task_type, status, input_json, requested_by,
                idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, agent_id, task_type.strip(), status, serialized, requested_by.strip(),
             idempotency_key, _now()),
        )
        _audit(
            connection, "run_requested" if status == "queued" else "run_blocked",
            actor=requested_by, agent_id=agent_id, run_id=run_id,
            details={"task_type": task_type.strip(), "status": status},
        )
        row = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row)


def request_approval(
    run_id: str,
    action_type: str,
    payload: dict[str, Any],
    requested_by: str,
    ttl_seconds: int = 900,
) -> dict[str, Any]:
    """Create an expiring approval bound to an immutable payload hash."""
    if not action_type or not action_type.strip():
        raise ValueError("action_type must be non-empty")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 86400:
        raise ValueError("ttl_seconds must be between 1 and 86400")
    serialized = _json(payload)
    digest = sha256(serialized.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    approval_id = str(uuid4())
    with db.connect() as connection:
        run = connection.execute("SELECT id, agent_id, task_type, status FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise ValueError("unknown run")
        if run["status"] not in {"queued", "running", "pending_approval"} and not (
            run["status"] == "succeeded" and run["agent_id"] == "quotation"
            and run["task_type"] == "prepare_from_meeting"
        ):
            raise ValueError("run is not eligible for approval")
        connection.execute(
            """INSERT INTO agent_approvals
               (id, run_id, action_type, payload_json, payload_sha256, status,
                requested_by, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (approval_id, run_id, action_type.strip(), serialized, digest, requested_by,
             now.isoformat(timespec="seconds"),
             (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")),
        )
        connection.execute(
            "UPDATE agent_runs SET status = 'pending_approval' WHERE id = ?",
            (run_id,),
        )
        _audit(
            connection, "approval_requested", actor=requested_by, agent_id=run["agent_id"],
            run_id=run_id, details={"approval_id": approval_id, "action_type": action_type.strip()},
        )
        row = connection.execute("SELECT * FROM agent_approvals WHERE id = ?", (approval_id,)).fetchone()
    return dict(row)


def review_approval(
    approval_id: str,
    decision: str,
    reviewed_by: str,
    current_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Approve/reject only an unexpired request whose payload has not changed."""
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    with db.connect() as connection:
        row = connection.execute(
            "SELECT * FROM agent_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown approval")
        if row["status"] != "pending":
            raise ValueError("approval is no longer pending")
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromisoformat(row["expires_at"])
        if now >= expires_at:
            connection.execute(
                "UPDATE agent_approvals SET status = 'expired' WHERE id = ?", (approval_id,)
            )
            connection.execute(
                "UPDATE agent_runs SET status = 'cancelled', finished_at = ? WHERE id = ? AND status = 'pending_approval'",
                (now.isoformat(timespec="seconds"), row["run_id"]),
            )
            connection.commit()
            raise ValueError("approval has expired")
        stored_payload = json.loads(row["payload_json"])
        candidate = stored_payload if current_payload is None else current_payload
        digest = sha256(_json(candidate).encode("utf-8")).hexdigest()
        if digest != row["payload_sha256"]:
            connection.execute("UPDATE agent_approvals SET status = 'expired' WHERE id = ?", (approval_id,))
            connection.execute(
                "UPDATE agent_runs SET status = 'cancelled', finished_at = ? WHERE id = ? AND status = 'pending_approval'",
                (now.isoformat(timespec="seconds"), row["run_id"]),
            )
            connection.commit()
            raise ValueError("approval payload changed; request a new approval")
        connection.execute(
            """UPDATE agent_approvals
               SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?""",
            (decision, reviewed_by, now.isoformat(timespec="seconds"), approval_id),
        )
        run = connection.execute(
            "SELECT agent_id FROM agent_runs WHERE id = ?", (row["run_id"],)
        ).fetchone()
        if decision == "rejected":
            connection.execute(
                "UPDATE agent_runs SET status = 'cancelled', finished_at = ? WHERE id = ? AND status = 'pending_approval'",
                (now.isoformat(timespec="seconds"), row["run_id"]),
            )
        _audit(
            connection, "approval_" + decision, actor=reviewed_by,
            agent_id=run["agent_id"] if run else None, run_id=row["run_id"],
            details={"approval_id": approval_id},
        )
        updated = connection.execute(
            "SELECT * FROM agent_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
    return dict(updated)


def list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT id, agent_id, run_id, actor, event_type, details_json, created_at
               FROM agent_audit_logs ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {**dict(row), "details": json.loads(row["details_json"])}
        for row in rows
    ]



def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT r.id, r.agent_id, a.name AS agent_name, r.task_type, r.status,
                      r.requested_by, r.created_at, r.finished_at
               FROM agent_runs r JOIN agents a ON a.id = r.agent_id
               ORDER BY r.created_at DESC, r.rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def list_approvals(limit: int = 100) -> list[dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT p.id, p.run_id, r.agent_id, a.name AS agent_name,
                      p.action_type, p.payload_json, p.payload_sha256, p.status, p.requested_by, p.reviewed_by,
                      p.created_at, p.expires_at, p.reviewed_at
               FROM agent_approvals p
               JOIN agent_runs r ON r.id = p.run_id
               JOIN agents a ON a.id = r.agent_id
               ORDER BY p.created_at DESC, p.rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
