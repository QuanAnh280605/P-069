"""Tests for zero-data live schema extraction."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Integer
from sqlalchemy.engine import URL, Connection
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import SQLAlchemyError

from src.models.raw_schema import LiveSchemaRequest, SchemaExtractionResult, TableMetadata
from src.services.database import decrypt_conn_url, encrypt_conn_url
from src.services.introspection import (
    ConnectionIntrospectionError,
    SchemaIntrospectionError,
    UnsupportedDatabaseTypeError,
    _normalize_url,
    _read_live_schema,
    _sample_column_values,
    _should_sample,
    extract_raw_schema,
)

TEST_FERNET_KEY = "FiqLMBulPbTUShiUnFKXgt2OHpPv9Y3mBstowcTSKRc="
SQLITE_SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT DEFAULT 'none@example.com'
);
CREATE UNIQUE INDEX idx_cust_email ON customers (email);
CREATE TABLE orders (
    order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    amount NUMERIC DEFAULT 0.00,
    PRIMARY KEY (order_id, customer_id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
"""


@pytest.fixture
def sqlite_memory_url() -> str:
    """Keep a named in-memory SQLite database alive for async inspection."""
    database_name = f"raw_schema_{uuid4().hex}"
    memory_uri = f"file:{database_name}?mode=memory&cache=shared"
    anchor = sqlite3.connect(memory_uri, uri=True)
    anchor.executescript(SQLITE_SCHEMA)
    try:
        yield f"sqlite:///file:{database_name}?mode=memory&cache=shared&uri=true"
    finally:
        anchor.close()


def _table(tables: list[TableMetadata], name: str) -> TableMetadata:
    return next(table for table in tables if table["table_name"] == name)


async def _extract_sqlite(url: str) -> SchemaExtractionResult:
    encrypted_url = encrypt_conn_url(url, key=TEST_FERNET_KEY)
    request: LiveSchemaRequest = {
        "conn_url_enc": encrypted_url,
        "db_type": "sqlite",
        "connection_id": 42,
    }
    with patch("src.services.introspection.decrypt_conn_url") as decrypt:
        decrypt.side_effect = lambda value: decrypt_conn_url(value, key=TEST_FERNET_KEY)
        return await extract_raw_schema(request)


def _inspector() -> MagicMock:
    inspector = MagicMock(spec=Inspector)
    inspector.default_schema_name = "public"
    inspector.get_table_names.return_value = ["orders"]
    inspector.get_columns.return_value = [{"name": "id", "type": Integer(), "nullable": False, "default": None}]
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    inspector.get_foreign_keys.return_value = []
    inspector.get_indexes.return_value = []
    return inspector


@pytest.mark.asyncio
async def test_live_sqlite_returns_complete_zero_data_contract(sqlite_memory_url: str) -> None:
    """Return normalized metadata without row counts or sample values."""
    result = await _extract_sqlite(sqlite_memory_url)
    raw_schema = result["raw_schema"]
    source = raw_schema["source"]
    assert source["type"] == "live_connection"
    assert source["connection_id"] == 42
    assert datetime.fromisoformat(source["extracted_at"].replace("Z", "+00:00")).tzinfo
    orders = _table(raw_schema["tables"], "orders")
    assert orders["schema_name"] == "main"
    assert orders["primary_keys"] == ["order_id", "customer_id"]
    assert orders["row_count_estimate"] is None
    customer_id = next(item for item in orders["columns"] if item["column_name"] == "customer_id")
    assert customer_id["sample_values"] is None
    assert customer_id["is_foreign_key"] is True
    assert customer_id["references"] == {"table": "customers", "column": "id", "schema": "main"}


@pytest.mark.asyncio
async def test_live_sqlite_returns_explicit_index_and_relationship(sqlite_memory_url: str) -> None:
    """Preserve explicit indexes and derive one relationship per FK pair."""
    result = await _extract_sqlite(sqlite_memory_url)
    raw_schema = result["raw_schema"]
    customers = _table(raw_schema["tables"], "customers")
    assert customers["indexes"] == [{"index_name": "idx_cust_email", "columns": ["email"], "is_unique": True}]
    assert raw_schema["relationships"] == [
        {
            "from_table": "orders",
            "from_column": "customer_id",
            "to_table": "customers",
            "to_column": "id",
            "relationship_type": "many_to_one",
        }
    ]


def test_mysql_inspector_uses_only_schema_metadata_methods() -> None:
    """Pass current database to the allowed SQLAlchemy Inspector methods."""
    inspector = _inspector()
    connection = cast(
        Connection,
        SimpleNamespace(engine=SimpleNamespace(url=URL.create("mysql", database="sales"))),
    )
    request: LiveSchemaRequest = {
        "conn_url_enc": "ciphertext",
        "db_type": "mysql",
        "connection_id": 7,
    }
    with patch("src.services.introspection.inspect", return_value=inspector):
        result = _read_live_schema(connection, request)
    assert result["raw_schema"]["tables"][0]["schema_name"] == "sales"
    inspector.get_table_names.assert_called_once_with(schema="sales")
    inspector.get_columns.assert_called_once_with("orders", schema="sales")
    inspector.get_pk_constraint.assert_called_once_with("orders", schema="sales")
    inspector.get_foreign_keys.assert_called_once_with("orders", schema="sales")
    inspector.get_indexes.assert_called_once_with("orders", schema="sales")


def test_partial_live_introspection_returns_sanitized_warning() -> None:
    """Skip one inaccessible table while preserving successful metadata."""
    inspector = _inspector()
    inspector.get_table_names.return_value = ["denied", "orders"]
    inspector.get_columns.side_effect = [
        SQLAlchemyError("permission denied for secret"),
        [{"name": "id", "type": Integer(), "nullable": False, "default": None}],
    ]
    connection = cast(Connection, SimpleNamespace(engine=SimpleNamespace(url=URL.create("postgresql"))))
    request: LiveSchemaRequest = {
        "conn_url_enc": "ciphertext",
        "db_type": "postgresql",
        "connection_id": 8,
    }
    with patch("src.services.introspection.inspect", return_value=inspector):
        result = _read_live_schema(connection, request)
    assert [table["table_name"] for table in result["raw_schema"]["tables"]] == ["orders"]
    assert result["warnings"] == ["Could not inspect table 'denied' (SQLAlchemyError)."]
    assert "secret" not in result["warnings"][0]


def test_all_live_tables_failing_raises_schema_error() -> None:
    """Fail the extraction when no listed table can be inspected."""
    inspector = _inspector()
    inspector.get_columns.side_effect = SQLAlchemyError("permission denied")
    connection = cast(Connection, SimpleNamespace(engine=SimpleNamespace(url=URL.create("postgresql"))))
    request: LiveSchemaRequest = {
        "conn_url_enc": "ciphertext",
        "db_type": "postgresql",
        "connection_id": 8,
    }
    with (
        patch("src.services.introspection.inspect", return_value=inspector),
        pytest.raises(SchemaIntrospectionError),
    ):
        _read_live_schema(connection, request)


def test_normalize_url_rejects_mismatched_database_type() -> None:
    """Reject a URL whose dialect conflicts with the declared type."""
    with pytest.raises(UnsupportedDatabaseTypeError):
        _normalize_url("sqlite:///:memory:", "postgresql")


@pytest.mark.asyncio
async def test_live_extraction_rejects_non_positive_connection_id() -> None:
    """Require the persisted semantic database ID in the source contract."""
    request: LiveSchemaRequest = {
        "conn_url_enc": "ciphertext",
        "db_type": "sqlite",
        "connection_id": 0,
    }
    with pytest.raises(ConnectionIntrospectionError, match="valid connection ID"):
        await extract_raw_schema(request)


# ---------------------------------------------------------------------------
# Value sampling: _should_sample heuristic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("column_name", "data_type", "expected"),
    [
        # Categorical VARCHAR with name pattern → True
        ("status", "VARCHAR(20)", True),
        ("gender", "CHAR(1)", True),
        ("role", "VARCHAR(30)", True),
        ("priority", "VARCHAR(10)", True),
        # BOOLEAN/BOOL → always True
        ("is_active", "BOOLEAN", True),
        ("is_deleted", "BOOL", True),
        # ENUM → always True
        ("color", "ENUM('red','blue')", True),
        # INTEGER/SMALLINT with categorical name → True
        ("is_completed", "INTEGER", True),
        ("level", "SMALLINT", True),
        ("category_id", "TINYINT", True),
        # Plain INTEGER without categorical name → False
        ("amount", "INTEGER", False),
        ("total", "DECIMAL", False),
        ("created_at", "TIMESTAMP", False),
        ("price", "FLOAT", False),
        # VARCHAR > 50 without categorical pattern → False
        ("name", "VARCHAR(255)", False),
        ("title", "VARCHAR(100)", False),
        # PII blacklist → always False
        ("email", "VARCHAR(100)", False),
        ("password_hash", "VARCHAR(255)", False),
        ("secret_key", "VARCHAR(50)", False),
        ("token", "VARCHAR(64)", False),
        ("description", "TEXT", False),
        ("notes", "VARCHAR(500)", False),
        ("phone", "VARCHAR(20)", False),
        ("address", "VARCHAR(200)", False),
        # TEXT, BLOB → always False
        ("body", "TEXT", False),
        ("data", "BLOB", False),
    ],
    ids=lambda param: f"{param}" if isinstance(param, str) else None,
)
def test_should_sample_heuristic(column_name: str, data_type: str, expected: bool) -> None:
    """Heuristic correctly identifies categorical vs non-categorical columns."""
    assert _should_sample(column_name, data_type) is expected


# ---------------------------------------------------------------------------
# Value sampling: _sample_column_values
# ---------------------------------------------------------------------------


def test_sample_column_values_returns_distinct_values() -> None:
    """SELECT DISTINCT should return unique non-null values."""
    conn = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [("active",), ("inactive",), ("pending",)]
    conn.exec_driver_sql.return_value = result_mock

    values = _sample_column_values(conn, "orders", "status", "main", "sqlite")

    assert values == ["active", "inactive", "pending"]
    sql = conn.exec_driver_sql.call_args[0][0]
    assert "SELECT DISTINCT" in sql
    assert "IS NOT NULL" in sql
    assert "LIMIT 20" in sql


def test_sample_column_values_returns_none_on_empty() -> None:
    """Return None when no rows are returned."""
    conn = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    conn.exec_driver_sql.return_value = result_mock

    values = _sample_column_values(conn, "orders", "status", "main", "sqlite")
    assert values is None


def test_sample_column_values_returns_none_on_failure() -> None:
    """Graceful degradation: return None on any exception."""
    conn = MagicMock()
    conn.exec_driver_sql.side_effect = SQLAlchemyError("boom")

    values = _sample_column_values(conn, "orders", "status", "main", "sqlite")
    assert values is None


# ---------------------------------------------------------------------------
# Integration: sample_values populated in live schema extraction
# ---------------------------------------------------------------------------

SQLITE_SCHEMA_WITH_CATEGORIES = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    status VARCHAR(10) NOT NULL DEFAULT 'active',
    category VARCHAR(20),
    is_featured BOOLEAN DEFAULT 0,
    name VARCHAR(255),
    email VARCHAR(100),
    description TEXT,
    amount NUMERIC DEFAULT 0
);
INSERT INTO products (status, category, is_featured, name, email, description, amount) VALUES
    ('active', 'electronics', 1, 'Widget A', 'a@test.com', 'Desc A', 10.00),
    ('inactive', 'electronics', 0, 'Widget B', 'b@test.com', 'Desc B', 20.00),
    ('active', 'clothing', 1, 'Widget C', 'c@test.com', 'Desc C', 30.00);
"""


@pytest.fixture
def sqlite_categorized_url() -> str:
    """SQLite DB with categorical and PII columns for sampling tests."""
    database_name = f"sampling_{uuid4().hex}"
    memory_uri = f"file:{database_name}?mode=memory&cache=shared"
    anchor = sqlite3.connect(memory_uri, uri=True)
    anchor.executescript(SQLITE_SCHEMA_WITH_CATEGORIES)
    try:
        yield f"sqlite:///file:{database_name}?mode=memory&cache=shared&uri=true"
    finally:
        anchor.close()


@pytest.mark.asyncio
async def test_sample_values_populated_for_categorical_column(sqlite_categorized_url: str) -> None:
    """VARCHAR status column should have sample_values extracted."""
    result = await _extract_sqlite(sqlite_categorized_url)
    products = _table(result["raw_schema"]["tables"], "products")
    status_col = next(c for c in products["columns"] if c["column_name"] == "status")
    assert status_col["sample_values"] is not None
    assert set(status_col["sample_values"]) == {"active", "inactive"}


@pytest.mark.asyncio
async def test_sample_values_none_for_pii_column(sqlite_categorized_url: str) -> None:
    """PII columns (email, description) should NOT be sampled."""
    result = await _extract_sqlite(sqlite_categorized_url)
    products = _table(result["raw_schema"]["tables"], "products")
    email_col = next(c for c in products["columns"] if c["column_name"] == "email")
    desc_col = next(c for c in products["columns"] if c["column_name"] == "description")
    assert email_col["sample_values"] is None
    assert desc_col["sample_values"] is None


@pytest.mark.asyncio
async def test_sample_values_none_for_long_varchar(sqlite_categorized_url: str) -> None:
    """VARCHAR(255) name column should NOT be sampled."""
    result = await _extract_sqlite(sqlite_categorized_url)
    products = _table(result["raw_schema"]["tables"], "products")
    name_col = next(c for c in products["columns"] if c["column_name"] == "name")
    assert name_col["sample_values"] is None


@pytest.mark.asyncio
async def test_sample_values_populated_for_boolean(sqlite_categorized_url: str) -> None:
    """BOOLEAN is_featured column should have sample_values."""
    result = await _extract_sqlite(sqlite_categorized_url)
    products = _table(result["raw_schema"]["tables"], "products")
    featured_col = next(c for c in products["columns"] if c["column_name"] == "is_featured")
    assert featured_col["sample_values"] is not None
    assert set(featured_col["sample_values"]) == {"0", "1"}
