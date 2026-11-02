import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py"
SPEC = importlib.util.spec_from_file_location("sqlite_to_postgres_migration", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(migration)


@pytest.mark.parametrize("identifier", ["companies", "quote_sequences", "auth_sessions"])
def test_migration_identifier_quotes_known_schema_names(identifier):
    assert migration.quote_identifier(identifier) == f'"{identifier}"'


@pytest.mark.parametrize("identifier", ["", "bad-name", "x; DROP TABLE companies", 'x"y'])
def test_migration_identifier_rejects_unsafe_names(identifier):
    with pytest.raises(ValueError):
        migration.quote_identifier(identifier)
