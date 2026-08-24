"""Migration simulation tests for the dashboard_layouts table."""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.event import listen

_NOW = datetime(2026, 1, 1)


def _create_pre_migration_schema(engine: Engine) -> None:
    """Create tables as they look at revision o1p2q3r4s5t6 (no dashboard_layouts yet)."""
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL,
                username VARCHAR(100) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE semantic_databases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER,
                created_by INTEGER,
                display_name VARCHAR(200) NOT NULL,
                db_type VARCHAR(50) NOT NULL,
                conn_url_enc TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'draft',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )


def _import_add_dashboard_layouts_migration():
    """Import the actual migration module from alembic/versions/."""
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*_add_dashboard_layouts.py"))
    if not migration_files:
        pytest.fail("Migration file '*_add_dashboard_layouts.py' not found in alembic/versions/.")

    spec = importlib.util.spec_from_file_location("_add_dashboard_layouts_migration", migration_files[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules["_add_dashboard_layouts_migration"] = module
    spec.loader.exec_module(module)
    return module


def _run_upgrade(db_engine: Engine) -> None:
    """Run the migration's upgrade() against the given engine."""
    module = _import_add_dashboard_layouts_migration()

    with db_engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.upgrade()
        conn.commit()


def _run_downgrade(db_engine: Engine) -> None:
    """Run the migration's downgrade() against the given engine."""
    module = _import_add_dashboard_layouts_migration()

    with db_engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.downgrade()
        conn.commit()


@pytest.fixture()
def migrated_engine(tmp_path):
    """Yield a file-based SQLite engine upgraded to include dashboard_layouts."""
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard_layouts.db'}")

    def _enable_sqlite_fk(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    listen(engine, "connect", _enable_sqlite_fk)
    _create_pre_migration_schema(engine)
    _run_upgrade(engine)
    yield engine
    engine.dispose()


def _seed_user_and_db(engine: Engine) -> tuple[int, int]:
    """Insert one user and one semantic database; return their ids."""
    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users (email, username, hashed_password, full_name, status, created_at, updated_at) "
                "VALUES ('u@test.com', 'editor', 'hash', 'Editor', 'active', :now, :now)"
            ),
            {"now": _NOW},
        ).lastrowid
        db_id = conn.execute(
            text(
                "INSERT INTO semantic_databases (org_id, created_by, display_name, db_type, conn_url_enc, "
                "status, created_at, updated_at) VALUES (NULL, NULL, 'DB', 'postgres', 'enc', 'draft', :now, :now)"
            ),
            {"now": _NOW},
        ).lastrowid
    return user_id, db_id


class TestUpgradeCreatesDashboardLayouts:
    """upgrade() creates the singleton dashboard_layouts table."""

    def test_table_exists_with_expected_columns(self, migrated_engine):
        """The dashboard_layouts table exists with all required columns."""
        inspector = sa.inspect(migrated_engine)
        assert inspector.has_table("dashboard_layouts")

        columns = {col["name"]: col for col in inspector.get_columns("dashboard_layouts")}
        assert set(columns) == {"id", "db_id", "layout_json", "version", "updated_by", "created_at", "updated_at"}
        assert columns["db_id"]["nullable"] is False
        assert columns["layout_json"]["nullable"] is False
        assert columns["updated_by"]["nullable"] is True

    def test_unique_constraint_on_db_id(self, migrated_engine):
        """A named unique constraint uq_dashboard_layouts_db_id covers db_id."""
        inspector = sa.inspect(migrated_engine)
        unique_constraints = inspector.get_unique_constraints("dashboard_layouts")
        matching = [uc for uc in unique_constraints if uc["name"] == "uq_dashboard_layouts_db_id"]
        assert len(matching) == 1
        assert matching[0]["column_names"] == ["db_id"]

    def test_duplicate_db_id_is_rejected(self, migrated_engine):
        """Inserting a second layout for the same database violates the unique constraint."""
        _, db_id = _seed_user_and_db(migrated_engine)

        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dashboard_layouts (db_id, layout_json, version, created_at, updated_at) "
                    "VALUES (:db_id, '{}', 1, :now, :now)"
                ),
                {"db_id": db_id, "now": _NOW},
            )

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            with migrated_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO dashboard_layouts (db_id, layout_json, version, created_at, updated_at) "
                        "VALUES (:db_id, '{}', 1, :now, :now)"
                    ),
                    {"db_id": db_id, "now": _NOW},
                )


class TestForeignKeyBehavior:
    """Foreign keys enforce CASCADE and SET NULL delete rules."""

    def test_deleting_semantic_database_cascades_layout(self, migrated_engine):
        """Deleting the owning semantic database removes its layout row."""
        _, db_id = _seed_user_and_db(migrated_engine)

        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dashboard_layouts (db_id, layout_json, version, created_at, updated_at) "
                    "VALUES (:db_id, '{}', 1, :now, :now)"
                ),
                {"db_id": db_id, "now": _NOW},
            )
            conn.execute(text("DELETE FROM semantic_databases WHERE id = :db_id"), {"db_id": db_id})

        with migrated_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM dashboard_layouts")).scalar_one()
        assert count == 0

    def test_deleting_user_sets_updated_by_null(self, migrated_engine):
        """Deleting the last editor keeps the layout and nulls updated_by."""
        user_id, db_id = _seed_user_and_db(migrated_engine)

        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dashboard_layouts (db_id, layout_json, version, updated_by, created_at, updated_at) "
                    "VALUES (:db_id, '{}', 1, :user_id, :now, :now)"
                ),
                {"db_id": db_id, "user_id": user_id, "now": _NOW},
            )
            conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})

        with migrated_engine.connect() as conn:
            row = conn.execute(
                text("SELECT updated_by FROM dashboard_layouts WHERE db_id = :db_id"), {"db_id": db_id}
            ).scalar_one()
        assert row is None


class TestVersionDefaultAndDowngrade:
    """version defaults to 1 server-side; downgrade removes the table."""

    def test_version_defaults_to_one(self, migrated_engine):
        """Inserting without version stores 1 via server default."""
        _, db_id = _seed_user_and_db(migrated_engine)

        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dashboard_layouts (db_id, layout_json, created_at, updated_at) "
                    "VALUES (:db_id, '{}', :now, :now)"
                ),
                {"db_id": db_id, "now": _NOW},
            )

        with migrated_engine.connect() as conn:
            version = conn.execute(
                text("SELECT version FROM dashboard_layouts WHERE db_id = :db_id"), {"db_id": db_id}
            ).scalar_one()
        assert version == 1

    def test_downgrade_removes_table(self, tmp_path):
        """downgrade() drops the dashboard_layouts table."""
        engine = create_engine(f"sqlite:///{tmp_path / 'dashboard_downgrade.db'}")
        try:
            _create_pre_migration_schema(engine)
            _run_upgrade(engine)
            _run_downgrade(engine)

            inspector = sa.inspect(engine)
            assert not inspector.has_table("dashboard_layouts")
        finally:
            engine.dispose()
