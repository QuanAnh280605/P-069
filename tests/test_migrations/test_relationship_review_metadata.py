"""Tests for the relationship review metadata migration.

These simulate the Alembic upgrade/downgrade against a pre-migration SQLite
schema to prove the nullable -> backfill -> enforce sequence and the
valid->approved / invalid->pending_review governance branching.
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture
def engine() -> sa.Engine:
    """Create a SQLite database using the pre-migration canonical schema."""
    db = sa.create_engine("sqlite:///:memory:")
    with db.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                CREATE TABLE semantic_tables (
                    id INTEGER PRIMARY KEY,
                    db_id INTEGER NOT NULL,
                    table_name VARCHAR(200) NOT NULL
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                CREATE TABLE canonical_relationships (
                    id INTEGER PRIMARY KEY,
                    connection_id INTEGER NOT NULL,
                    from_entity_id INTEGER NOT NULL,
                    to_entity_id INTEGER NOT NULL,
                    relationship_type VARCHAR(50) NOT NULL,
                    join_condition TEXT NOT NULL,
                    relationship_key VARCHAR(500) NOT NULL,
                    constraint_name VARCHAR(200),
                    column_pairs TEXT NOT NULL,
                    validation_status VARCHAR(20) NOT NULL DEFAULT 'valid',
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(sa.text("INSERT INTO users (id) VALUES (1), (2)"))
        connection.execute(
            sa.text("INSERT INTO semantic_tables (id, db_id, table_name) VALUES (1, 1, 'customers'), (2, 1, 'orders')")
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO canonical_relationships
                    (id, connection_id, from_entity_id, to_entity_id, relationship_type,
                     join_condition, relationship_key, constraint_name, column_pairs, validation_status, created_at)
                VALUES
                    (1, 1, 1, 2, 'one_to_many', 'orders.customer_id = customers.id',
                     'rel:1:2', 'fk_orders_customer_id', '[]', 'valid', '2026-01-01 00:00:00'),
                    (2, 1, 2, 1, 'many_to_one', 'orders.customer_id = customers.id',
                     'rel:2:1', NULL, '[]', 'invalid', '2026-01-01 00:00:00'),
                    (3, 1, 1, 2, 'one_to_many', 'orders.customer_id = customers.id',
                     'rel:3:2', NULL, '[]', 'needs_review', '2026-01-01 00:00:00')
                """
            )
        )
    yield db
    db.dispose()


def _load_migration():
    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_path = next(versions.glob("*_add_relationship_review_metadata.py"))
    spec = importlib.util.spec_from_file_location("add_relationship_review_metadata", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_migration(engine: sa.Engine, direction: str) -> None:
    migration = _load_migration()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        getattr(migration, direction)()


def _columns(engine: sa.Engine) -> dict:
    return {column["name"]: column for column in sa.inspect(engine).get_columns("canonical_relationships")}


def test_upgrade_adds_governance_columns(engine: sa.Engine) -> None:
    """Upgrade introduces the business-name and review-state columns."""
    _run_migration(engine, "upgrade")

    names = set(_columns(engine))
    assert {
        "business_name",
        "description",
        "review_status",
        "ai_business_name",
        "ai_description",
        "reviewed_at",
        "reviewed_by",
        "updated_by",
    } <= names


def test_upgrade_backfills_valid_to_approved(engine: sa.Engine) -> None:
    """A technically valid legacy relationship is auto-approved with a label."""
    _run_migration(engine, "upgrade")

    with engine.connect() as connection:
        row = connection.execute(
            sa.text("SELECT business_name, review_status FROM canonical_relationships WHERE id = 1")
        ).one()

    assert row[1] == "approved"
    assert row[0] == "customers -> orders (fk_orders_customer_id)"


def test_upgrade_backfills_invalid_and_unknown_to_pending_review(engine: sa.Engine) -> None:
    """Invalid and unknown validity both stay pending_review for a human."""
    _run_migration(engine, "upgrade")

    with engine.connect() as connection:
        rows = {
            r[0]: r[1]
            for r in connection.execute(
                sa.text("SELECT id, review_status FROM canonical_relationships WHERE id IN (2, 3)")
            )
        }

    assert rows[2] == "pending_review"
    assert rows[3] == "pending_review"


def test_upgrade_label_omits_constraint_when_unavailable(engine: sa.Engine) -> None:
    """Deterministic label uses only table names when no FK constraint exists."""
    _run_migration(engine, "upgrade")

    with engine.connect() as connection:
        name = connection.execute(
            sa.text("SELECT business_name FROM canonical_relationships WHERE id = 3")
        ).scalar_one()

    assert name == "customers -> orders"


def test_upgrade_enforces_not_null_and_defaults(engine: sa.Engine) -> None:
    """Required columns become NOT NULL and review_status defaults to pending_review."""
    _run_migration(engine, "upgrade")

    columns = _columns(engine)
    assert columns["business_name"]["nullable"] is False
    assert columns["review_status"]["nullable"] is False
    assert columns["description"]["nullable"] is True
    assert "pending_review" in str(columns["review_status"]["default"])


def test_upgrade_creates_foreign_keys_and_check(engine: sa.Engine) -> None:
    """Reviewer/updater FKs and the review_status check constraint are present."""
    _run_migration(engine, "upgrade")

    fks = {fk["name"] for fk in sa.inspect(engine).get_foreign_keys("canonical_relationships")}
    assert "fk_canonical_relationships_reviewed_by" in fks
    assert "fk_canonical_relationships_updated_by" in fks

    checks = {c["name"] for c in sa.inspect(engine).get_check_constraints("canonical_relationships")}
    assert "ck_canonical_relationships_review_status" in checks


def test_downgrade_removes_columns_and_constraints(engine: sa.Engine) -> None:
    """Downgrade restores the pre-migration schema without the governance fields."""
    _run_migration(engine, "upgrade")
    _run_migration(engine, "downgrade")

    names = set(_columns(engine))
    assert "business_name" not in names
    assert "review_status" not in names
    assert "description" not in names

    fks = {fk["name"] for fk in sa.inspect(engine).get_foreign_keys("canonical_relationships")}
    assert "fk_canonical_relationships_reviewed_by" not in fks
    assert "fk_canonical_relationships_updated_by" not in fks


def _index_names(engine: sa.Engine) -> set[str]:
    return {idx["name"] for idx in sa.inspect(engine).get_indexes("canonical_relationships")}


def test_upgrade_creates_review_index(engine: sa.Engine) -> None:
    """Upgrade creates idx_canonical_relationships_review on the table."""
    _run_migration(engine, "upgrade")
    assert "idx_canonical_relationships_review" in _index_names(engine)


def test_downgrade_removes_review_index(engine: sa.Engine) -> None:
    """Downgrade drops idx_canonical_relationships_review from the table."""
    _run_migration(engine, "upgrade")
    _run_migration(engine, "downgrade")
    assert "idx_canonical_relationships_review" not in _index_names(engine)
