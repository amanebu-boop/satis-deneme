import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DATABASE_PATH = "data/sales.db"


def database_path() -> Path:
    return Path(os.environ.get("SALES_DATABASE_PATH", DEFAULT_DATABASE_PATH))


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                authorized_people TEXT NOT NULL DEFAULT '[]',
                phone_numbers TEXT NOT NULL DEFAULT '[]',
                address TEXT,
                website TEXT,
                email TEXT,
                tax_office TEXT,
                tax_number TEXT,
                mersis_number TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                meeting_date TEXT NOT NULL,
                notes TEXT NOT NULL,
                meeting_type TEXT NOT NULL DEFAULT 'phone',
                topic TEXT NOT NULL DEFAULT 'Genel görüşme'
            );
            CREATE TABLE IF NOT EXISTS follow_up_tasks (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'done')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                currency TEXT NOT NULL CHECK(length(currency) = 3),
                unit_price TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quotations (
                id TEXT PRIMARY KEY,
                company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
                currency TEXT NOT NULL CHECK(length(currency) = 3),
                subtotal TEXT NOT NULL,
                discount_rate TEXT NOT NULL,
                discount_amount TEXT NOT NULL,
                tax_rate TEXT NOT NULL,
                tax_amount TEXT NOT NULL,
                total TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status = 'draft'),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quotation_lines (
                id TEXT PRIMARY KEY,
                quotation_id TEXT NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                quantity TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                line_total TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                csrf_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry
                ON auth_sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_meetings_company_date
                ON meetings(company_id, meeting_date);
            CREATE INDEX IF NOT EXISTS idx_contacts_company
                ON contacts(company_id, name);
            """
        )
        # Safe in-place migration for existing SQLite databases.
        meeting_columns = {row["name"] for row in connection.execute("PRAGMA table_info(meetings)")}
        if "meeting_type" not in meeting_columns:
            connection.execute("ALTER TABLE meetings ADD COLUMN meeting_type TEXT NOT NULL DEFAULT 'phone'")
        if "topic" not in meeting_columns:
            connection.execute("ALTER TABLE meetings ADD COLUMN topic TEXT NOT NULL DEFAULT 'Genel görüşme'")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_follow_up_due ON follow_up_tasks(status, due_date)")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(companies)")}
        additions = {
            "authorized_people": "TEXT NOT NULL DEFAULT '[]'",
            "phone_numbers": "TEXT NOT NULL DEFAULT '[]'",
            "address": "TEXT",
            "email": "TEXT",
            "tax_office": "TEXT",
            "tax_number": "TEXT",
            "mersis_number": "TEXT",
        }
        for column, definition in additions.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE companies ADD COLUMN {column} {definition}")


def _company_record(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    for key in ("authorized_people", "phone_numbers"):
        value = record.get(key, "[]")
        try:
            record[key] = json.loads(value) if isinstance(value, str) else (value or [])
        except (TypeError, json.JSONDecodeError):
            record[key] = []
    return record


def create_company(record: dict[str, Any]) -> dict[str, Any]:
    stored = {**record}
    stored["authorized_people"] = json.dumps(record.get("authorized_people") or [], ensure_ascii=False)
    stored["phone_numbers"] = json.dumps(record.get("phone_numbers") or [], ensure_ascii=False)
    with connect() as connection:
        connection.execute(
            """INSERT INTO companies
               (id, name, authorized_people, phone_numbers, address, website, email,
                tax_office, tax_number, mersis_number, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (stored["id"], stored["name"], stored["authorized_people"], stored["phone_numbers"],
             stored.get("address"), stored.get("website"), stored.get("email"),
             stored.get("tax_office"), stored.get("tax_number"), stored.get("mersis_number"),
             stored.get("notes")),
        )
    return {**record}


def list_companies(search: str | None = None) -> list[dict[str, Any]]:
    """List companies with full details, optionally filtering by name or website."""
    with connect() as connection:
        if search and search.strip():
            term = f"%{search.strip()}%"
            rows = connection.execute(
                """SELECT * FROM companies
                   WHERE name LIKE ? COLLATE NOCASE OR website LIKE ? COLLATE NOCASE
                   OR email LIKE ? COLLATE NOCASE OR tax_number LIKE ? COLLATE NOCASE
                   ORDER BY name, id""",
                (term, term, term, term),
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM companies ORDER BY name, id").fetchall()
    return [_company_record(row) for row in rows]


def list_companies_page(
    search: str | None = None, *, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """Return a bounded page of company details using parameterized SQL."""
    with connect() as connection:
        if search and search.strip():
            term = f"%{search.strip()}%"
            rows = connection.execute(
                """SELECT * FROM companies
                   WHERE name LIKE ? COLLATE NOCASE OR website LIKE ? COLLATE NOCASE
                   OR email LIKE ? COLLATE NOCASE OR tax_number LIKE ? COLLATE NOCASE
                   ORDER BY name, id LIMIT ? OFFSET ?""",
                (term, term, term, term, limit, offset),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM companies ORDER BY name, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [_company_record(row) for row in rows]


def get_company(company_id: str) -> dict[str, Any] | None:
    """Fetch a full company record by its primary key."""
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
    return _company_record(row) if row is not None else None


def update_company(company_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
    stored = {**record}
    stored["authorized_people"] = json.dumps(record.get("authorized_people") or [], ensure_ascii=False)
    stored["phone_numbers"] = json.dumps(record.get("phone_numbers") or [], ensure_ascii=False)
    with connect() as connection:
        cursor = connection.execute(
            """UPDATE companies SET name=?, authorized_people=?, phone_numbers=?, address=?,
               website=?, email=?, tax_office=?, tax_number=?, mersis_number=?, notes=?
               WHERE id=?""",
            (stored["name"], stored["authorized_people"], stored["phone_numbers"],
             stored.get("address"), stored.get("website"), stored.get("email"),
             stored.get("tax_office"), stored.get("tax_number"), stored.get("mersis_number"),
             stored.get("notes"), company_id),
        )
        if cursor.rowcount == 0:
            return None
    return {"id": company_id, **record}


def company_exists(company_id: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
    return row is not None


def create_contact(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """INSERT INTO contacts (id, company_id, name, email, phone, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record["id"], record["company_id"], record["name"], record.get("email"),
             record.get("phone"), record.get("notes")),
        )
    return record


def list_company_contacts(company_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, company_id, name, email, phone, notes
               FROM contacts WHERE company_id = ? ORDER BY name, id""",
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_meeting(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """INSERT INTO meetings
               (id, company_id, meeting_date, notes, meeting_type, topic)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record["id"], record["company_id"], record["meeting_date"], record["notes"],
             record.get("meeting_type", "phone"), record.get("topic", "Genel görüşme")),
        )
    return record


def update_meeting(meeting_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as connection:
        cursor = connection.execute(
            """UPDATE meetings SET company_id = ?, meeting_date = ?, notes = ?,
               meeting_type = ?, topic = ? WHERE id = ?""",
            (record["company_id"], record["meeting_date"], record["notes"],
             record.get("meeting_type", "phone"), record.get("topic", "Genel görüşme"), meeting_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            """SELECT m.id, m.company_id, c.name AS company_name, m.meeting_date,
                      m.notes, m.meeting_type, m.topic
               FROM meetings AS m JOIN companies AS c ON c.id = m.company_id
               WHERE m.id = ?""",
            (meeting_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_company_meetings(company_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, company_id, meeting_date, notes, meeting_type, topic
               FROM meetings WHERE company_id = ?
               ORDER BY meeting_date DESC, id""",
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_meetings() -> list[dict[str, Any]]:
    """List persisted meetings with their company names for the authenticated browser UI."""
    with connect() as connection:
        rows = connection.execute(
            """SELECT m.id, m.company_id, c.name AS company_name, m.meeting_date,
                      m.notes, m.meeting_type, m.topic
               FROM meetings AS m JOIN companies AS c ON c.id = m.company_id
               ORDER BY m.meeting_date DESC, m.id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def create_follow_up(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """INSERT INTO follow_up_tasks (id, company_id, title, due_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record["id"], record["company_id"], record["title"], record["due_date"],
             record.get("status", "open"), record["created_at"]),
        )
    return record


def list_follow_ups() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT t.id, t.company_id, c.name AS company_name, t.title, t.due_date,
                      t.status, t.created_at
               FROM follow_up_tasks AS t JOIN companies AS c ON c.id = t.company_id
               ORDER BY CASE t.status WHEN 'open' THEN 0 ELSE 1 END, t.due_date, t.id"""
        ).fetchall()
    return [dict(row) for row in rows]


def complete_follow_up(task_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE follow_up_tasks SET status = 'done' WHERE id = ?", (task_id,)
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            """SELECT t.id, t.company_id, c.name AS company_name, t.title, t.due_date,
                      t.status, t.created_at
               FROM follow_up_tasks AS t JOIN companies AS c ON c.id = t.company_id
               WHERE t.id = ?""", (task_id,)
        ).fetchone()
    return dict(row) if row is not None else None



def create_product(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """INSERT INTO products (id, sku, name, description, currency, unit_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record["id"], record["sku"], record["name"], record.get("description"),
             record["currency"], record["unit_price"]),
        )
    return record


def list_products() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, sku, name, description, currency, unit_price
               FROM products ORDER BY name, sku"""
        ).fetchall()
    return [dict(row) for row in rows]


def create_quotation(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """INSERT INTO quotations
               (id, company_id, currency, subtotal, discount_rate, discount_amount,
                tax_rate, tax_amount, total, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record["id"], record.get("company_id"), record["currency"], record["subtotal"],
             "0", "0.00", record["tax_rate"], record["tax_amount"],
             record["total"], record["status"], record["created_at"]),
        )
        for line in record["lines"]:
            connection.execute(
                """INSERT INTO quotation_lines
                   (id, quotation_id, description, quantity, unit_price, line_total)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (line["id"], record["id"], line["description"], line["quantity"],
                 line["unit_price"], line["line_total"]),
            )
    return record


def get_quotation(quotation_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """SELECT id, company_id, currency, subtotal, discount_rate, discount_amount,
                      tax_rate, tax_amount, total, status, created_at
               FROM quotations WHERE id = ?""",
            (quotation_id,),
        ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["lines"] = [
            dict(line) for line in connection.execute(
                """SELECT id, description, quantity, unit_price, line_total
                   FROM quotation_lines WHERE quotation_id = ? ORDER BY rowid""",
                (quotation_id,),
            ).fetchall()
        ]
    return record


def list_quotations() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, company_id, currency, subtotal, discount_rate, discount_amount,
                      tax_rate, tax_amount, total, status, created_at
               FROM quotations ORDER BY created_at DESC, id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]
