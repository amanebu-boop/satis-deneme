"""Small SQLAlchemy compatibility adapter for the existing sqlite3-style repository layer.

The SQLite backend remains unchanged. PostgreSQL is selected with DATABASE_URL and
uses SQLAlchemy 2 + psycopg. This adapter intentionally supports only the SQL patterns
used by app.db; new queries should be portable SQL or covered by backend tests.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def database_url() -> str | None:
    value = __import__("os").environ.get("DATABASE_URL") or __import__("os").environ.get("SALES_DATABASE_URL")
    if not value:
        return None
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


def is_postgres_configured() -> bool:
    return bool(database_url())


def engine() -> Engine:
    global _engine
    if _engine is None:
        url = database_url()
        if not url:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL mode")
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=int(__import__("os").environ.get("DB_POOL_SIZE", "5")),
            max_overflow=int(__import__("os").environ.get("DB_MAX_OVERFLOW", "5")),
            pool_recycle=1800,
        )
    return _engine


class Row(dict):
    """Mapping row compatible with row['column'], row.get(), and dict(row)."""


class Result:
    def __init__(self, result: Any):
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self._result.fetchone()
        return Row(row._mapping) if row is not None else None

    def fetchall(self):
        return [Row(row._mapping) for row in self._result.fetchall()]

    def first(self):
        return self.fetchone()


def _translate(sql: str, parameters: Any):
    statement = sql.strip()
    if statement.upper().startswith("PRAGMA TABLE_INFO("):
        match = re.search(r"PRAGMA\s+table_info\(['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\)", statement, re.I)
        if not match:
            raise ValueError("Unsupported PRAGMA table_info statement")
        table = match.group(1)
        statement = (
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :table_name "
            "ORDER BY ordinal_position"
        )
        return statement, {"table_name": table}
    statement = re.sub(r"\s+COLLATE\s+NOCASE", "", statement, flags=re.I)
    statement = re.sub(r"\bLIKE\b", "ILIKE", statement, flags=re.I)
    statement = re.sub(r"\browid\b", "ctid", statement, flags=re.I)
    if isinstance(parameters, dict):
        return statement, parameters
    values = tuple(parameters or ())
    index = 0

    def replace(_match):
        nonlocal index
        key = f"p{index}"
        index += 1
        return f":{key}"

    statement = re.sub(r"\?", replace, statement)
    if index != len(values):
        raise ValueError(f"SQL placeholder mismatch: expected {index}, received {len(values)}")
    return statement, {f"p{i}": value for i, value in enumerate(values)}


class Connection:
    def __init__(self):
        self._connection = None
        self._transaction = None

    def __enter__(self):
        self._connection = engine().connect()
        self._transaction = self._connection.begin()
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                self._transaction.commit()
            else:
                self._transaction.rollback()
        finally:
            self._connection.close()
        return False

    def execute(self, sql: str, parameters: Any = ()):
        statement, values = _translate(sql, parameters)
        return Result(self._connection.execute(text(statement), values))

    def executescript(self, script: str):
        # The repository's bootstrap DDL contains no semicolons inside literals.
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)
        return Result(_EmptyResult())

    def close(self):
        if self._connection is not None:
            self._connection.close()


class _EmptyResult:
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []


def dispose_engine():
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
