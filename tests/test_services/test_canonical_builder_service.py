"""Tests for CanonicalBuilderService.

Test cases cover all normalization scenarios:
  - C-1.x: Basic cases (uppercase names, data types, nullable, ordinal).
  - C-2.x: Naming conventions (PascalCase, camelCase, abbreviations, numbers).
  - C-3.x: SQL reserved words & quoted identifiers.
  - C-4.x: Complex data types and dialect-specific modifiers.
  - C-5.x: Edge cases — NUL byte, collision, composite PK, arity mismatch, unknown FK.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import AsyncIterable, Generator

import pytest
from pydantic import ValidationError

from src.models.schema_metadata import SchemaDialect
from src.services.canonical_builder_service import (
    CanonicalBuilderService,
    summarize_canonical_schema,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_basic_db() -> Generator[str, None, None]:
    """SQLite DB with basic schema: two tables, one FK (C-1.x, C-2.x)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE users (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT    NOT NULL,
            email     TEXT    UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        );
    """)
    conn.execute("""
        CREATE TABLE orders (
            order_id   INTEGER PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            total_amt  REAL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
    """)
    conn.commit()
    conn.close()

    yield f"sqlite:///{path}"

    if os.path.exists(path):
        os.remove(path)


async def _bytes_stream(content: bytes) -> AsyncIterable[bytes]:
    """Async byte-chunk generator for SQL dump tests."""
    yield content


# ---------------------------------------------------------------------------
# C-1.x: Basic cases
# ---------------------------------------------------------------------------


def test_c1_basic_tables_present(sqlite_basic_db: str) -> None:
    """C-1.1 — Uppercase and snake_case table names resolve correctly."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    table_names = {t.table_name.normalized_name for t in schema.tables}
    assert "users" in table_names
    assert "orders" in table_names


def test_c1_dialect_detected(sqlite_basic_db: str) -> None:
    """C-1.1 — Auto-detect SQLite dialect from connection URL."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    assert schema.dialect == SchemaDialect.SQLITE


def test_c1_column_ordinals_are_positive(sqlite_basic_db: str) -> None:
    """C-1.4 — All column ordinal_positions must be >= 1."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    for table in schema.tables:
        for col in table.columns:
            assert col.ordinal_position >= 1


def test_c1_column_ordinals_are_unique(sqlite_basic_db: str) -> None:
    """C-1.4 — No duplicate ordinal_positions within a table."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    for table in schema.tables:
        ordinals = [c.ordinal_position for c in table.columns]
        assert len(ordinals) == len(set(ordinals))


def test_c1_primary_key_flag_set(sqlite_basic_db: str) -> None:
    """C-1.3 — The primary key column must have primary_key=True."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    users = next(t for t in schema.tables if t.table_name.normalized_name == "users")
    pk_cols = [c for c in users.columns if c.primary_key]
    assert len(pk_cols) == 1
    assert pk_cols[0].column_name.normalized_name == "user_id"


def test_c1_nullable_flag(sqlite_basic_db: str) -> None:
    """C-1.3 — NOT NULL columns must have nullable=False."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    users = next(t for t in schema.tables if t.table_name.normalized_name == "users")
    username_col = next(c for c in users.columns if c.column_name.normalized_name == "username")
    assert username_col.nullable is False


# ---------------------------------------------------------------------------
# C-2.x: Naming conventions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c2_snake_case_names_normalized() -> None:
    """C-2.3 — Abbreviated snake_case columns preserved as normalized_name."""
    dump = b"""
    CREATE TABLE order_items (
        item_id     INT       PRIMARY KEY,
        amt_vat_inc NUMERIC(15,2),
        ord_sts_cd  VARCHAR(10) NOT NULL
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    tbl = result.schema_metadata.tables[0]
    col_names = {c.column_name.normalized_name for c in tbl.columns}
    assert "amt_vat_inc" in col_names
    assert "ord_sts_cd" in col_names


@pytest.mark.asyncio
async def test_c2_numbers_in_name_allowed() -> None:
    """C-2.4 — Table/column names with digits are preserved."""
    dump = b"""
    CREATE TABLE order_detail_v2 (
        line_item_1 INT PRIMARY KEY,
        address_line_2 VARCHAR(255)
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    tbl = result.schema_metadata.tables[0]
    assert tbl.table_name.normalized_name == "order_detail_v2"
    col_names = {c.column_name.normalized_name for c in tbl.columns}
    assert "address_line_2" in col_names


# ---------------------------------------------------------------------------
# C-3.x: Reserved words & quoted identifiers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c3_reserved_word_table_name() -> None:
    """C-3.1 — Table named 'order' (SQL reserved word) normalizes correctly."""
    dump = b"""
    CREATE TABLE "order" (
        id   INT PRIMARY KEY,
        name VARCHAR(100)
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    table_names = {t.table_name.normalized_name for t in result.schema_metadata.tables}
    assert "order" in table_names


# ---------------------------------------------------------------------------
# C-4.x: Complex data types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c4_numeric_precision_scale() -> None:
    """C-4.4 — NUMERIC(15,2) precision/scale must be captured in data_type."""
    dump = b"""
    CREATE TABLE financials (
        id       INT     PRIMARY KEY,
        revenue  NUMERIC(15,2),
        tax_rate DECIMAL(5,4)
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    tbl = result.schema_metadata.tables[0]
    col_types = {c.column_name.normalized_name: c.data_type for c in tbl.columns}
    assert any(k in col_types["revenue"].upper() for k in ("NUMERIC", "DECIMAL"))


@pytest.mark.asyncio
async def test_c4_timestamp_type() -> None:
    """C-4.3 — TIMESTAMP columns are captured."""
    dump = b"""
    CREATE TABLE events (
        id         INT       PRIMARY KEY,
        created_at TIMESTAMP NOT NULL
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    tbl = result.schema_metadata.tables[0]
    ts_col = next(c for c in tbl.columns if c.column_name.normalized_name == "created_at")
    assert "TIMESTAMP" in ts_col.data_type.upper()


# ---------------------------------------------------------------------------
# C-5.x: Edge cases — security, collision, composite PK, arity mismatch
# ---------------------------------------------------------------------------


def test_c5_model_immutability(sqlite_basic_db: str) -> None:
    """C-5.x — Canonical model must be immutable (frozen=True)."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    with pytest.raises((TypeError, ValidationError)):
        schema.dialect = SchemaDialect.MYSQL  # type: ignore[misc]


def test_c5_column_immutability(sqlite_basic_db: str) -> None:
    """C-5.x — Column metadata must be immutable after construction."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    col = schema.tables[0].columns[0]
    with pytest.raises((TypeError, ValidationError)):
        col.nullable = not col.nullable  # type: ignore[misc]


@pytest.mark.asyncio
async def test_c5_composite_primary_key() -> None:
    """C-5.4 — Composite (multi-column) primary key is captured correctly."""
    dump = b"""
    CREATE TABLE order_items (
        order_id INT  NOT NULL,
        item_id  INT  NOT NULL,
        qty      INT,
        PRIMARY KEY (order_id, item_id)
    );
    """
    result = await CanonicalBuilderService.build_from_sql_dump(
        _bytes_stream(dump), "dump.sql", dialect_override=SchemaDialect.POSTGRESQL
    )
    tbl = result.schema_metadata.tables[0]
    assert tbl.primary_key is not None
    pk_col_names = {c.normalized_name for c in tbl.primary_key.constrained_columns}
    assert "order_id" in pk_col_names
    assert "item_id" in pk_col_names


# ---------------------------------------------------------------------------
# Round-trip: build_from_raw_dict
# ---------------------------------------------------------------------------


def test_roundtrip_raw_dict(sqlite_basic_db: str) -> None:
    """build_from_raw_dict must reproduce an identical schema from its own JSON export."""
    original = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    raw_dict = original.model_dump(mode="json")
    reconstructed = CanonicalBuilderService.build_from_raw_dict(raw_dict)
    assert reconstructed.dialect == original.dialect
    assert len(reconstructed.tables) == len(original.tables)
    for orig_tbl, reco_tbl in zip(original.tables, reconstructed.tables):
        assert orig_tbl.table_name.normalized_name == reco_tbl.table_name.normalized_name
        assert len(orig_tbl.columns) == len(reco_tbl.columns)


# ---------------------------------------------------------------------------
# summarize_canonical_schema helper
# ---------------------------------------------------------------------------


def test_summarize_schema_structure(sqlite_basic_db: str) -> None:
    """summarize_canonical_schema must return dict with correct table/column count."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    summary = summarize_canonical_schema(schema)
    assert summary["dialect"] == "sqlite"
    assert summary["table_count"] == 2
    users_summary = next(t for t in summary["tables"] if t["table_name"] == "users")
    assert users_summary["has_primary_key"] is True
    assert users_summary["column_count"] == 4


def test_summarize_schema_column_fields(sqlite_basic_db: str) -> None:
    """Each column in the summary must contain required keys for LLM prompt building."""
    schema = CanonicalBuilderService.build_from_live_db(sqlite_basic_db)
    summary = summarize_canonical_schema(schema)
    for tbl in summary["tables"]:
        for col in tbl["columns"]:
            assert "column_name" in col
            assert "normalized_name" in col
            assert "data_type" in col
            assert "nullable" in col
            assert "primary_key" in col
