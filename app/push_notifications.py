"""Android Web Push subscriptions and idempotent follow-up delivery."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
from urllib.parse import urlparse

from app import db

log = logging.getLogger("sales_api.push")
TZ = ZoneInfo("Europe/Istanbul")
POLL_SECONDS = 30


def configured() -> bool:
    return all(os.environ.get(k) for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_CLAIMS_SUB"))


def initialize() -> None:
    with db.connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id TEXT PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL, auth TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS push_deliveries (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES follow_up_tasks(id) ON DELETE CASCADE,
            subscription_id TEXT NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
            due_day TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
            sent_at TEXT, last_error TEXT,
            UNIQUE(task_id, subscription_id, due_day)
        );
        CREATE INDEX IF NOT EXISTS idx_push_delivery_pending
            ON push_deliveries(status, next_attempt_at);
        """)


def save_subscription(payload: dict) -> dict:
    endpoint = payload["endpoint"]
    host = (urlparse(endpoint).hostname or "").lower()
    allowed_hosts = {
        "fcm.googleapis.com", "android.googleapis.com",
        "updates.push.services.mozilla.com", "push.services.mozilla.com",
        "web.push.apple.com",
    }
    if urlparse(endpoint).scheme != "https" or host not in allowed_hosts:
        raise ValueError("Unsupported push service endpoint")
    now = datetime.now(TZ).isoformat()
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM push_subscriptions WHERE endpoint=?", (endpoint,)).fetchone()
        if row:
            conn.execute("""UPDATE push_subscriptions SET p256dh=?, auth=?, updated_at=?
                            WHERE endpoint=?""",
                         (payload["keys"]["p256dh"], payload["keys"]["auth"], now, endpoint))
            sid = row["id"]
        else:
            sid = str(uuid4())
            conn.execute("""INSERT INTO push_subscriptions
                (id,endpoint,p256dh,auth,created_at,updated_at) VALUES (?,?,?,?,?,?)""",
                (sid, endpoint, payload["keys"]["p256dh"], payload["keys"]["auth"], now, now))
    return {"registered": True}


def remove_subscription(endpoint: str) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))


def _due_tasks(now: datetime) -> list[dict]:
    today = now.date().isoformat()
    with db.connect() as conn:
        rows = conn.execute("""SELECT t.id,t.title,t.due_date,c.name AS company_name
            FROM follow_up_tasks t JOIN companies c ON c.id=t.company_id
            WHERE t.status='open' AND substr(t.due_date,1,10)<=?
            ORDER BY t.due_date,t.id""", (today,)).fetchall()
    return [dict(r) for r in rows]


def _queue_deliveries(now: datetime) -> None:
    with db.connect() as conn:
        subs = conn.execute("SELECT id FROM push_subscriptions").fetchall()
        tasks = conn.execute("""SELECT id,substr(due_date,1,10) AS due_day
            FROM follow_up_tasks WHERE status='open' AND substr(due_date,1,10)<=?""",
            (now.date().isoformat(),)).fetchall()
        for task in tasks:
            for sub in subs:
                conn.execute("""INSERT OR IGNORE INTO push_deliveries
                    (id,task_id,subscription_id,due_day,status,attempts,next_attempt_at)
                    VALUES (?,?,?,?,'pending',0,?)""",
                    (str(uuid4()), task["id"], sub["id"], task["due_day"], now.isoformat()))


def _claim_one(now: datetime):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT d.id,d.task_id,d.subscription_id,s.endpoint,s.p256dh,s.auth,
                    t.title,c.name AS company_name,t.due_date
            FROM push_deliveries d
            JOIN push_subscriptions s ON s.id=d.subscription_id
            JOIN follow_up_tasks t ON t.id=d.task_id
            JOIN companies c ON c.id=t.company_id
            WHERE d.status='pending' AND d.attempts<5 AND d.next_attempt_at<=?
              AND t.status='open'
            ORDER BY d.next_attempt_at,d.id LIMIT 1""", (now.isoformat(),)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE push_deliveries SET attempts=attempts+1,next_attempt_at=? WHERE id=?",
                     ((now + timedelta(minutes=5)).isoformat(), row["id"]))
        return dict(row)


def _send(row: dict) -> None:
    from pywebpush import WebPushException, webpush
    payload = json.dumps({
        "title": "Satış Asistanı",
        "body": f'{row["company_name"]}: {row["title"]}',
        "tag": f'follow-up-{row["task_id"]}',
        "url": "/"
    }, ensure_ascii=False)
    try:
        webpush(
            subscription_info={"endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
            data=payload, vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ["VAPID_CLAIMS_SUB"]},
            ttl=86400,
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            remove_subscription(row["endpoint"])
            with db.connect() as conn:
                conn.execute("DELETE FROM push_deliveries WHERE id=?", (row["id"],))
            return
        raise
    with db.connect() as conn:
        conn.execute("UPDATE push_deliveries SET status='sent',sent_at=?,last_error=NULL WHERE id=?",
                     (datetime.now(TZ).isoformat(), row["id"]))


async def run_scheduler(stop_event: asyncio.Event) -> None:
    """Runs at 10:00 Istanbul time; durable queue supports restarts and retry."""
    while not stop_event.is_set():
        now = datetime.now(TZ)
        if now.hour >= 10:
            try:
                _queue_deliveries(now)
                for _ in range(500):
                    row = _claim_one(datetime.now(TZ))
                    if not row:
                        break
                    try:
                        await asyncio.to_thread(_send, row)
                    except Exception as exc:
                        log.warning("Push delivery failed; retry scheduled (delivery=%s, type=%s)",
                                    row["id"], type(exc).__name__)
                        with db.connect() as conn:
                            conn.execute("UPDATE push_deliveries SET last_error=? WHERE id=?",
                                         (type(exc).__name__, row["id"]))
            except Exception:
                log.exception("Push scheduler iteration failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass


def public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def due_time_for(value: str) -> datetime:
    """Date-only tasks are due at 10:00 Europe/Istanbul."""
    parsed_date = date.fromisoformat(value[:10])
    return datetime.combine(parsed_date, time(10, 0), TZ)
