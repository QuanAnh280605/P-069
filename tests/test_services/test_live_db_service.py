"""Tests for Live Target Database Service and Introspection."""

import os
import sqlite3
import tempfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema_metadata import SchemaDialect
from src.services.live_db_service import (
    create_live_target_db,
    delete_live_target_db,
    get_live_target_db,
    introspect_live_database,
    list_live_target_dbs,
)


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database with test schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE
        );
    """)
    cursor.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
    """)
    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


def test_introspect_live_database(temp_sqlite_db: str):
    """Test zero-data schema introspection on a SQLite database file."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    schema = introspect_live_database(conn_url, SchemaDialect.POSTGRESQL)
    assert schema.tables is not None
    table_names = [table.table_name.raw_name for table in schema.tables]
    assert "customers" in table_names
    assert "orders" in table_names

    orders_table = next(t for t in schema.tables if t.table_name.raw_name == "orders")
    col_names = [c.column_name.raw_name for c in orders_table.columns]
    assert "order_id" in col_names
    assert "customer_id" in col_names
    assert "total_amount" in col_names
    assert len(orders_table.foreign_keys) == 1


def test_introspect_live_database_with_string_auto_dialect(temp_sqlite_db: str):
    """Test introspect_live_database when passed string 'auto' as dialect."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    schema = introspect_live_database(conn_url, "auto")
    assert schema.dialect == SchemaDialect.SQLITE
    assert schema.tables is not None


@pytest.mark.asyncio
async def test_create_and_manage_live_target_db(async_session: AsyncSession, temp_sqlite_db: str):
    """Test full CRUD lifecycle for live target database records."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    user_id = 1
    display_name = "Test Retail Live DB"

    # Create & Introspect
    created = await create_live_target_db(
        db=async_session,
        user_id=user_id,
        display_name=display_name,
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )
    assert created.id > 0
    assert created.display_name == display_name
    assert created.table_count == 2

    # List
    summary_list = await list_live_target_dbs(async_session, user_id)
    assert len(summary_list) == 1
    assert summary_list[0].id == created.id

    # Get Single
    fetched = await get_live_target_db(async_session, user_id, created.id)
    assert fetched is not None
    assert fetched.display_name == display_name
    assert len(fetched.raw_schema.tables) == 2

    # Delete
    deleted = await delete_live_target_db(async_session, user_id, created.id)
    assert deleted is True

    # Verify deleted
    fetched_after = await get_live_target_db(async_session, user_id, created.id)
    assert fetched_after is None


def test_resolve_and_validate_dialect_auto_and_strict():
    """Test auto-detection and strict matching validation logic."""
    from src.services.live_db_service import resolve_and_validate_dialect

    # Auto detect tests
    assert resolve_and_validate_dialect("postgresql://localhost/db", "auto") == SchemaDialect.POSTGRESQL
    assert resolve_and_validate_dialect("mysql+pymysql://localhost/db", "auto") == SchemaDialect.MYSQL
    assert resolve_and_validate_dialect("sqlite:///test.db", None) == SchemaDialect.SQLITE

    # Strict match success
    assert resolve_and_validate_dialect("mysql+pymysql://localhost/db", "mysql") == SchemaDialect.MYSQL
    assert resolve_and_validate_dialect("postgresql://localhost/db", "postgresql") == SchemaDialect.POSTGRESQL

    # Strict match failure (mismatched URL scheme)
    with pytest.raises(ValueError, match="does not match selected dialect"):
        resolve_and_validate_dialect("postgresql://localhost/db", "mysql")
