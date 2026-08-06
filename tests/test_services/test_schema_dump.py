"""Tests for non-executing PostgreSQL/MySQL dump extraction."""

from __future__ import annotations

from datetime import datetime
from typing import cast

import pytest

from src.models.raw_schema import DumpSchemaRequest, TableMetadata
from src.services.introspection import (
    InvalidSchemaDumpError,
    UnsupportedDatabaseTypeError,
    extract_raw_schema,
)

POSTGRES_DUMP = """
SET client_encoding = 'UTF8';
CREATE TABLE public.parents (
    id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    PRIMARY KEY (id, region_id)
);
CREATE TABLE public.children (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER REFERENCES public.parents(id),
    parent_id INTEGER,
    parent_region INTEGER,
    amount NUMERIC(12, 2) DEFAULT 0.00,
    FOREIGN KEY (parent_id, parent_region)
        REFERENCES public.parents(id, region_id)
);
CREATE UNIQUE INDEX idx_children_parent
    ON public.children (parent_id, parent_region);
"""

MYSQL_DUMP = """
USE sales_db;
CREATE TABLE parents (
    id INT NOT NULL,
    region_id INT NOT NULL,
    PRIMARY KEY (id, region_id)
);
CREATE TABLE children (
    id INT PRIMARY KEY,
    parent_id INT NOT NULL,
    parent_region INT NOT NULL
);
ALTER TABLE children
    ADD CONSTRAINT fk_children_parent
    FOREIGN KEY (parent_id, parent_region)
    REFERENCES parents (id, region_id);
"""


def _table(tables: list[TableMetadata], schema: str | None, name: str) -> TableMetadata:
    return next(table for table in tables if table["schema_name"] == schema and table["table_name"] == name)


@pytest.mark.asyncio
async def test_postgresql_dump_preserves_inline_and_unnamed_composite_fks() -> None:
    """Parse inline and unnamed table-level foreign keys without dropping either."""
    request: DumpSchemaRequest = {"sql_content": POSTGRES_DUMP, "db_type": "postgresql"}
    result = await extract_raw_schema(request)
    raw_schema = result["raw_schema"]
    assert raw_schema["source"]["type"] == "sql_dump"
    assert raw_schema["source"]["connection_id"] is None
    assert datetime.fromisoformat(raw_schema["source"]["extracted_at"].replace("Z", "+00:00")).tzinfo
    children = _table(raw_schema["tables"], "public", "children")
    assert len(children["foreign_keys"]) == 2
    composite = next(item for item in children["foreign_keys"] if len(item["constrained_columns"]) == 2)
    assert composite["constraint_name"] is None
    assert composite["constrained_columns"] == ["parent_id", "parent_region"]
    assert len(raw_schema["relationships"]) == 3


@pytest.mark.asyncio
async def test_postgresql_dump_normalizes_types_defaults_and_indexes() -> None:
    """Normalize type text while preserving defaults and explicit indexes."""
    result = await extract_raw_schema({"sql_content": POSTGRES_DUMP, "db_type": "postgresql"})
    children = _table(result["raw_schema"]["tables"], "public", "children")
    amount = next(item for item in children["columns"] if item["column_name"] == "amount")
    assert amount["data_type"] == "decimal(12,2)"
    assert amount["default_value"] == "0.00"
    assert amount["sample_values"] is None
    assert children["indexes"] == [
        {
            "index_name": "idx_children_parent",
            "columns": ["parent_id", "parent_region"],
            "is_unique": True,
        }
    ]


@pytest.mark.asyncio
async def test_mysql_dump_applies_alter_table_composite_fk() -> None:
    """Apply named composite foreign keys added after CREATE TABLE."""
    result = await extract_raw_schema({"sql_content": MYSQL_DUMP, "db_type": "mysql"})
    children = _table(result["raw_schema"]["tables"], "sales_db", "children")
    foreign_key = children["foreign_keys"][0]
    assert foreign_key["constraint_name"] == "fk_children_parent"
    assert foreign_key["constrained_columns"] == ["parent_id", "parent_region"]
    flagged = [column for column in children["columns"] if column["is_foreign_key"]]
    assert [column["column_name"] for column in flagged] == ["parent_id", "parent_region"]
    assert len(result["raw_schema"]["relationships"]) == 2


@pytest.mark.asyncio
async def test_schema_qualified_same_name_tables_do_not_collide() -> None:
    """Preserve tables with equal names in separate PostgreSQL schemas."""
    sql = "CREATE TABLE b.users (id INT); CREATE TABLE a.users (id INT);"
    result = await extract_raw_schema({"sql_content": sql, "db_type": "postgresql"})
    identities = [(table["schema_name"], table["table_name"]) for table in result["raw_schema"]["tables"]]
    assert identities == [("a", "users"), ("b", "users")]


@pytest.mark.asyncio
async def test_dump_contract_uses_expected_json_field_names() -> None:
    """Expose the stable JSON field names consumed by AI nodes."""
    result = await extract_raw_schema({"sql_content": POSTGRES_DUMP, "db_type": "postgresql"})
    table = result["raw_schema"]["tables"][0]
    column = table["columns"][0]
    assert set(column) == {
        "column_name",
        "data_type",
        "is_nullable",
        "is_primary_key",
        "is_foreign_key",
        "default_value",
        "sample_values",
        "references",
    }
    assert all(table["row_count_estimate"] is None for table in result["raw_schema"]["tables"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql_content",
    ["", "SELECT * FROM users;", "CREATE TABLE broken (identifier);"],
)
async def test_invalid_or_non_schema_dump_is_rejected(sql_content: str) -> None:
    """Reject empty, data-query-only, and malformed table DDL."""
    with pytest.raises(InvalidSchemaDumpError, match="Invalid SQL schema dump"):
        await extract_raw_schema({"sql_content": sql_content, "db_type": "postgresql"})


@pytest.mark.asyncio
async def test_unsupported_dump_dialect_is_rejected() -> None:
    """Reject SQLite dumps because the task supports PostgreSQL/MySQL only."""
    request = cast(DumpSchemaRequest, {"sql_content": "CREATE TABLE x (id INT);", "db_type": "sqlite"})
    with pytest.raises(UnsupportedDatabaseTypeError):
        await extract_raw_schema(request)


@pytest.mark.asyncio
async def test_invalid_dump_does_not_echo_sql(capsys: pytest.CaptureFixture[str]) -> None:
    """Keep malformed dump content out of stdout and stderr."""
    secret_sql = "CREATE TABLE credential_super_secret (id"
    with pytest.raises(InvalidSchemaDumpError):
        await extract_raw_schema({"sql_content": secret_sql, "db_type": "postgresql"})
    captured = capsys.readouterr()
    assert "credential_super_secret" not in captured.out
    assert "credential_super_secret" not in captured.err


@pytest.mark.asyncio
async def test_non_schema_statements_are_ignored() -> None:
    """Ignore harmless dump setup statements while retaining table metadata."""
    sql = "SET client_encoding = 'UTF8'; CREATE TABLE public.safe (id INT);"
    result = await extract_raw_schema({"sql_content": sql, "db_type": "postgresql"})
    assert [(item["schema_name"], item["table_name"]) for item in result["raw_schema"]["tables"]] == [
        ("public", "safe")
    ]
