from app import db_backend


def test_postgres_url_normalization(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db:5432/sales")
    assert db_backend.database_url() == "postgresql+psycopg://user:pass@db:5432/sales"


def test_translate_sqlite_pragmas_and_placeholders():
    sql, params = db_backend._translate("PRAGMA table_info(companies)", ())
    assert "information_schema.columns" in sql
    assert params == {"table_name": "companies"}

    sql, params = db_backend._translate(
        "SELECT * FROM companies WHERE name LIKE ? COLLATE NOCASE AND id = ?",
        ("%ACME%", "c-1"),
    )
    assert "ILIKE" in sql
    assert "COLLATE NOCASE" not in sql
    assert params == {"p0": "%ACME%", "p1": "c-1"}


def test_translate_rowid_and_conflict_syntax():
    sql, params = db_backend._translate(
        "SELECT id FROM quotation_lines WHERE quotation_id = ? ORDER BY rowid",
        ("q-1",),
    )
    assert "ORDER BY ctid" in sql
    assert params == {"p0": "q-1"}


def test_placeholder_mismatch_is_rejected():
    try:
        db_backend._translate("SELECT * FROM companies WHERE id = ?", ())
    except ValueError as exc:
        assert "placeholder mismatch" in str(exc)
    else:
        raise AssertionError("Expected placeholder mismatch to fail")
