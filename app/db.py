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
                website TEXT,
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
                notes TEXT NOT NULL
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


def create_company(record: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            "INSERT INTO companies (id, name, website, notes) VALUES (?, ?, ?, ?)",
            (record["id"], record["name"], record.get("website"), record.get("notes")),
        )
    return record


def list_companies(search: str | None = None) -> list[dict[str, Any]]:
    """List companies, optionally filtering by name or website using a bound parameter."""
    with connect() as connection:
        if search and search.strip():
            term = f"%{search.strip()}%"
            rows = connection.execute(
                """SELECT id, name, website, notes FROM companies
                   WHERE name LIKE ? COLLATE NOCASE OR website LIKE ? COLLATE NOCASE
                   ORDER BY name, id""",
                (term, term),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id, name, website, notes FROM companies ORDER BY name, id"
            ).fetchall()
    return [dict(row) for row in rows]


def list_companies_page(
    search: str | None = None, *, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """Return a bounded page of company list fields using parameterized SQL."""
    with connect() as connection:
        if search and search.strip():
            term = f"%{search.strip()}%"
            rows = connection.execute(
                """SELECT id, name, website FROM companies
                   WHERE name LIKE ? COLLATE NOCASE OR website LIKE ? COLLATE NOCASE
                   ORDER BY name, id LIMIT ? OFFSET ?""",
                (term, term, limit, offset),
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT id, name, website FROM companies
                   ORDER BY name, id LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
    return [dict(row) for row in rows]


def get_company(company_id: str) -> dict[str, Any] | None:
    """Fetch a company record by its primary key."""
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, website, notes FROM companies WHERE id = ?",
            (company_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def update_company(company_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE companies SET name = ?, website = ?, notes = ? WHERE id = ?",
            (record["name"], record.get("website"), record.get("notes"), company_id),
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
            "INSERT INTO meetings (id, company_id, meeting_date, notes) VALUES (?, ?, ?, ?)",
            (record["id"], record["company_id"], record["meeting_date"], record["notes"]),
        )
    return record


def list_company_meetings(company_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, company_id, meeting_date, notes
               FROM meetings WHERE company_id = ?
               ORDER BY meeting_date DESC, id""",
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_meetings() -> list[dict[str, Any]]:
    """List persisted meetings with their company names for the authenticated browser UI."""
    with connect() as connection:
        rows = connection.execute(
            """SELECT m.id, m.company_id, c.name AS company_name, m.meeting_date, m.notes
               FROM meetings AS m JOIN companies AS c ON c.id = m.company_id
               ORDER BY m.meeting_date DESC, m.id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]



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
             record["discount_rate"], record["discount_amount"], record["tax_rate"],
             record["tax_amount"], record["total"], record["status"], record["created_at"]),
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
