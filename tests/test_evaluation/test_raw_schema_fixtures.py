"""Tests that raw-schema fixtures match authoritative extraction adapters."""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from src.models.raw_schema import DumpDatabaseType, DumpSchemaRequest, RawSchema
from src.services.schema_dump import parse_schema_dump

DOMAIN_DIR = Path("eval/golden_dataset/ecommerce")


@pytest.mark.parametrize("dialect", ["postgresql", "mysql"])
def test_dump_raw_schema_matches_parser(dialect: DumpDatabaseType) -> None:
    """Keep stored dump metadata aligned with the current DDL parser contract."""
    dump_path = DOMAIN_DIR / f"sources/{dialect}/schema_dump.sql"
    stored_path = DOMAIN_DIR / f"raw_schema/{dialect}_dump.json"
    request: DumpSchemaRequest = {
        "sql_content": dump_path.read_text(encoding="utf-8"),
        "db_type": dialect,
    }
    actual = parse_schema_dump(request)["raw_schema"]
    stored = TypeAdapter(RawSchema).validate_python(_read_json(stored_path))

    assert _table_names(actual) == _table_names(stored)
    assert _relationship_keys(actual) == _relationship_keys(stored)


def test_inferred_fixture_omits_session_foreign_key() -> None:
    """Ensure the inferred-FK case cannot obtain session→order from metadata."""
    path = DOMAIN_DIR / "raw_schema/postgresql_inferred_sessions.json"
    schema = TypeAdapter(RawSchema).validate_python(_read_json(path))
    dump = DOMAIN_DIR / "sources/postgresql/inferred_sessions_dump.sql"
    request: DumpSchemaRequest = {
        "sql_content": dump.read_text(encoding="utf-8"),
        "db_type": "postgresql",
    }
    parsed = parse_schema_dump(request)["raw_schema"]
    session = next(table for table in schema["tables"] if table["table_name"] == "fact_sessions")

    assert _table_names(schema) == _table_names(parsed)
    assert _relationship_keys(schema) == _relationship_keys(parsed)
    assert session["foreign_keys"] == []
    assert not any(item["from_table"] == "fact_sessions" for item in schema["relationships"])


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _table_names(schema: RawSchema) -> set[str]:
    return {table["table_name"] for table in schema["tables"]}


def _relationship_keys(schema: RawSchema) -> set[tuple[str, str, str, str]]:
    return {
        (item["from_table"], item["from_column"], item["to_table"], item["to_column"])
        for item in schema["relationships"]
    }
