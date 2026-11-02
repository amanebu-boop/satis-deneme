#!/usr/bin/env python3
"""Explicit, empty-target SQLite to PostgreSQL migration.

Dry-run is the default. The --apply switch is mandatory for writes.
The target URL is read only from SALES_DATABASE_URL and is never printed.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

TABLES = (
    "companies",
    "contacts",
    "meetings",
    "follow_up_tasks",
    "products",
    "meeting_products",
    "quote_sequences",
    "quotations",
    "quotation_lines",
    "auth_sessions",
)


def quote_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or not value:
        raise ValueError(f"Unexpected SQL identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def migrate(source_path: Path, *, apply: bool) -> dict[str, int]:
    target_url = os.environ.get("SALES_DATABASE_URL")
    if not target_url:
        raise RuntimeError("Set SALES_DATABASE_URL in the environment; do not pass credentials as command-line arguments.")

    import psycopg
    from psycopg.rows import dict_row

    if apply:
        # Create/update the target schema from the same application schema code.
        # This is only done after the operator explicitly supplies --apply.
        from app import db
        db.init_db()

    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source file does not exist: {source_path}")

    source = sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        source_tables = {
            row["name"]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing_source = set(TABLES) - source_tables
        if missing_source:
            raise RuntimeError(f"SQLite source is missing required tables: {', '.join(sorted(missing_source))}")

        rows_by_table: dict[str, list[sqlite3.Row]] = {}
        columns_by_table: dict[str, list[str]] = {}
        for table in TABLES:
            columns = [row["name"] for row in source.execute(f"PRAGMA table_info({quote_identifier(table)})")]
            columns_by_table[table] = columns
            rows_by_table[table] = source.execute(
                f"SELECT * FROM {quote_identifier(table)}"
            ).fetchall()

        counts = {table: len(rows_by_table[table]) for table in TABLES}

        with psycopg.connect(target_url, row_factory=dict_row, connect_timeout=10) as target:
            schema = os.environ.get("SALES_DATABASE_SCHEMA")
            if schema:
                if not schema.replace("_", "").isalnum() or not schema[0].isalpha():
                    raise ValueError("SALES_DATABASE_SCHEMA must be a simple identifier.")
                target.execute(f'SET search_path TO "{schema}"')

            target_tables = {
                row["table_name"]
                for row in target.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
                ).fetchall()
            }
            missing_target = set(TABLES) - target_tables
            if missing_target:
                raise RuntimeError(
                    "Target schema is not initialized. Start the application once against the empty target "
                    "or create the schema from the current application code first."
                )

            target_counts = {
                table: int(target.execute(
                    f"SELECT COUNT(*) AS count FROM {quote_identifier(table)}"
                ).fetchone()["count"])
                for table in TABLES
            }
            if any(target_counts.values()):
                raise RuntimeError(
                    "Refusing to import into a non-empty target. Take a backup and use a separately reviewed merge plan."
                )

            for table in TABLES:
                target_columns = [
                    row["column_name"]
                    for row in target.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = %s "
                        "ORDER BY ordinal_position",
                        (table,),
                    ).fetchall()
                ]
                if columns_by_table[table] != target_columns:
                    raise RuntimeError(
                        f"Schema mismatch for {table}. Source columns={columns_by_table[table]!r}; "
                        f"target columns={target_columns!r}. No rows were imported."
                    )

            if apply:
                with target.transaction():
                    for table in TABLES:
                        if not rows_by_table[table]:
                            continue
                        columns = columns_by_table[table]
                        column_sql = ", ".join(quote_identifier(column) for column in columns)
                        placeholders = ", ".join(["%s"] * len(columns))
                        insert_sql = (
                            f"INSERT INTO {quote_identifier(table)} ({column_sql}) "
                            f"VALUES ({placeholders})"
                        )
                        target.executemany(
                            insert_sql,
                            [tuple(row[column] for column in columns) for row in rows_by_table[table]],
                        )

                    # Restore the annual quote counter to at least the maximum quote number
                    # only when the source already contains a counter row; never guess IDs.
                    for table in TABLES:
                        actual = int(target.execute(
                            f"SELECT COUNT(*) AS count FROM {quote_identifier(table)}"
                        ).fetchone()["count"])
                        if actual != counts[table]:
                            raise RuntimeError(
                                f"Post-import row-count mismatch for {table}: expected {counts[table]}, got {actual}."
                            )

        return counts
    finally:
        source.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Path to the SQLite database file.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually import rows. Without this flag the command performs a read-only dry run.",
    )
    args = parser.parse_args()

    counts = migrate(args.source, apply=args.apply)
    mode = "IMPORTED" if args.apply else "DRY RUN — no rows written"
    print(mode)
    for table, count in counts.items():
        print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Migration stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(1)
