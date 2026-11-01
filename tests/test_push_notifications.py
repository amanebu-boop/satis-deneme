from datetime import datetime
from zoneinfo import ZoneInfo

from app import db, push_notifications


def test_due_time_uses_ten_am_istanbul():
    result = push_notifications.due_time_for("2026-11-03")
    assert result == datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Istanbul"))


def test_push_schema_and_idempotent_delivery_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    db.init_db()
    push_notifications.initialize()
    with db.connect() as conn:
        conn.execute("""INSERT INTO companies(id,name) VALUES ('co1','TEST FİRMA')""")
        conn.execute("""INSERT INTO follow_up_tasks
            (id,company_id,title,due_date,status,created_at)
            VALUES ('task1','co1','Arama yap','2026-11-03','open','2026-11-01T00:00:00+00:00')""")
    push_notifications.save_subscription({
        "endpoint": "https://push.example.test/subscription/abc",
        "keys": {"p256dh": "p" * 40, "auth": "a" * 20},
    })
    now = datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Istanbul"))
    push_notifications._queue_deliveries(now)
    push_notifications._queue_deliveries(now)
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM push_deliveries").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"


def test_configuration_requires_all_vapid_secrets(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private")
    monkeypatch.delenv("VAPID_CLAIMS_SUB", raising=False)
    assert push_notifications.configured() is False
    monkeypatch.setenv("VAPID_CLAIMS_SUB", "mailto:admin@example.com")
    assert push_notifications.configured() is True
