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



def test_product_migration_orders_parent_before_child_independent_of_source_order():
    rows = [
        {"id": "child", "parent_product_id": "parent"},
        {"id": "parent", "parent_product_id": None},
    ]
    ordered = migration.order_product_rows(rows)
    assert [row["id"] for row in ordered] == ["parent", "child"]


def test_product_migration_rejects_missing_parent():
    rows = [{"id": "child", "parent_product_id": "missing"}]
    with pytest.raises(RuntimeError, match="missing parent"):
        migration.order_product_rows(rows)


def test_product_migration_rejects_parent_cycles():
    rows = [
        {"id": "first", "parent_product_id": "second"},
        {"id": "second", "parent_product_id": "first"},
    ]
    with pytest.raises(RuntimeError, match="cycle"):
        migration.order_product_rows(rows)
