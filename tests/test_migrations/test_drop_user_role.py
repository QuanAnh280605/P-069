"""Tests for removing the obsolete account-level user role."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture
def engine() -> sa.Engine:
    """Create a SQLite database using the pre-migration users schema."""
    db = sa.create_engine("sqlite:///:memory:")
    with db.begin() as connection:
        connection.execute(
            sa.text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                username VARCHAR(100) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) NOT NULL DEFAULT '',
                role VARCHAR(50) NOT NULL DEFAULT 'analyst',
                status VARCHAR(50) NOT NULL DEFAULT 'active'
            )
        """)
        )
        connection.execute(
            sa.text("""
            INSERT INTO users (id, email, username, hashed_password, role)
            VALUES (1, 'user@example.com', 'user', 'hash', 'admin')
        """)
        )
    yield db
    db.dispose()


def _load_migration():
    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_path = next(versions.glob("*_drop_user_account_role.py"))
    spec = importlib.util.spec_from_file_location("drop_user_account_role", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_migration(engine: sa.Engine, direction: str) -> None:
    migration = _load_migration()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        getattr(migration, direction)()


def test_upgrade_drops_role_and_preserves_user(engine: sa.Engine) -> None:
    """Upgrade removes users.role without losing account data."""
    _run_migration(engine, "upgrade")

    columns = {column["name"] for column in sa.inspect(engine).get_columns("users")}
    with engine.connect() as connection:
        row = connection.execute(sa.text("SELECT id, email FROM users")).one()

    assert "role" not in columns
    assert row == (1, "user@example.com")


def test_downgrade_restores_non_authoritative_legacy_role(engine: sa.Engine) -> None:
    """Downgrade restores a nullable legacy role with an analyst default."""
    _run_migration(engine, "upgrade")
    _run_migration(engine, "downgrade")

    role = next(column for column in sa.inspect(engine).get_columns("users") if column["name"] == "role")
    with engine.connect() as connection:
        value = connection.execute(sa.text("SELECT role FROM users WHERE id = 1")).scalar_one()

    assert role["nullable"] is True
    assert "analyst" in str(role["default"])
    assert value == "analyst"
