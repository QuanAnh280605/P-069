"""Safe raw-schema extraction from live databases or SQL schema dumps."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import cast

from cryptography.fernet import InvalidToken
from sqlalchemy import inspect
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.engine.interfaces import ReflectedColumn, ReflectedForeignKeyConstraint, ReflectedIndex
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from src.models.raw_schema import (
    ColumnMetadata,
    ColumnReference,
    DatabaseType,
    DumpSchemaRequest,
    ForeignKeyMetadata,
    IndexMetadata,
    LiveSchemaRequest,
    RawSchema,
    RelationshipMetadata,
    SchemaExtractionRequest,
    SchemaExtractionResult,
    TableMetadata,
)
from src.services.database import decrypt_conn_url
from src.services.introspection_errors import (
    ConnectionIntrospectionError,
    IntrospectionError,
    InvalidCredentialError,
    InvalidSchemaDumpError,
    SchemaIntrospectionError,
    UnsupportedDatabaseTypeError,
)
from src.services.schema_dump import parse_schema_dump
from src.services.schema_normalization import build_fk_links, normalize_data_type, utc_timestamp

__all__ = [
    "ConnectionIntrospectionError",
    "DumpSchemaRequest",
    "IntrospectionError",
    "InvalidCredentialError",
    "InvalidSchemaDumpError",
    "LiveSchemaRequest",
    "RawSchema",
    "SchemaIntrospectionError",
    "UnsupportedDatabaseTypeError",
    "extract_raw_schema",
]

ASYNC_DRIVERS: dict[DatabaseType, str] = {
    "postgresql": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "sqlite": "sqlite+aiosqlite",
}


@dataclass(frozen=True)
class _LiveContext:
    inspector: Inspector
    schema_name: str | None
    request: LiveSchemaRequest


@dataclass
class _LiveOutput:
    tables: list[TableMetadata] = field(default_factory=list)
    relationships: list[RelationshipMetadata] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _LiveTableParts:
    columns: list[ReflectedColumn]
    primary_keys: list[str]
    foreign_keys: list[ForeignKeyMetadata]
    indexes: list[IndexMetadata]
    references: dict[str, ColumnReference]


async def extract_raw_schema(request: SchemaExtractionRequest) -> SchemaExtractionResult:
    """Extract one deterministic raw-schema contract without reading row data."""
    if "conn_url_enc" in request:
        live_request = cast(LiveSchemaRequest, request)
        _validate_live_request(live_request)
        return await _extract_live_schema(live_request)
    if "sql_content" in request:
        dump_request = cast(DumpSchemaRequest, request)
        return await asyncio.to_thread(parse_schema_dump, dump_request)
    raise UnsupportedDatabaseTypeError("Invalid schema extraction request parameters.")


def _validate_live_request(request: LiveSchemaRequest) -> None:
    if request["db_type"] not in ASYNC_DRIVERS:
        raise UnsupportedDatabaseTypeError("Unsupported database type.")
    if request["connection_id"] <= 0:
        raise ConnectionIntrospectionError("A valid connection ID is required.")


async def _extract_live_schema(request: LiveSchemaRequest) -> SchemaExtractionResult:
    plain_url = _decrypt_url(request["conn_url_enc"])
    normalized_url = _normalize_url(plain_url, request["db_type"])
    engine = create_async_engine(normalized_url, echo=False)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_read_live_schema, request)
    except IntrospectionError:
        raise
    except SQLAlchemyError as exc:
        raise ConnectionIntrospectionError("Cannot connect to target database.") from exc
    finally:
        await engine.dispose()


def _decrypt_url(conn_url_enc: str) -> str:
    try:
        return decrypt_conn_url(conn_url_enc)
    except (InvalidToken, ValueError, TypeError) as exc:
        raise InvalidCredentialError("Invalid encrypted database credential.") from exc


def _normalize_url(plain_url: str, db_type: DatabaseType) -> URL:
    if db_type not in ASYNC_DRIVERS:
        raise UnsupportedDatabaseTypeError("Unsupported database type.")
    try:
        url = make_url(plain_url)
    except (ArgumentError, ValueError) as exc:
        raise ConnectionIntrospectionError("Invalid database connection settings.") from exc
    if url.get_backend_name() != db_type:
        raise UnsupportedDatabaseTypeError("Database type does not match connection settings.")
    return url.set(drivername=ASYNC_DRIVERS[db_type])


def _read_live_schema(connection: Connection, request: LiveSchemaRequest) -> SchemaExtractionResult:
    inspector = inspect(connection)
    schema_name = _schema_name(inspector, connection, request["db_type"])
    context = _LiveContext(inspector=inspector, schema_name=schema_name, request=request)
    table_names = _table_names(context)
    output = _read_live_tables(context, table_names)
    if table_names and not output.tables:
        raise SchemaIntrospectionError("No database tables could be inspected.")
    return _live_result(context, output)


def _schema_name(inspector: Inspector, connection: Connection, db_type: DatabaseType) -> str | None:
    if db_type == "sqlite":
        return "main"
    if db_type == "postgresql":
        return inspector.default_schema_name or "public"
    if db_type == "mysql":
        return connection.engine.url.database
    return None


def _table_names(context: _LiveContext) -> list[str]:
    try:
        names = context.inspector.get_table_names(schema=context.schema_name)
    except SQLAlchemyError as exc:
        raise ConnectionIntrospectionError("Cannot read target database schema.") from exc
    return sorted(names)


def _read_live_tables(context: _LiveContext, table_names: list[str]) -> _LiveOutput:
    output = _LiveOutput()
    for table_name in table_names:
        try:
            table, relationships = _read_live_table(context, table_name)
            output.tables.append(table)
            output.relationships.extend(relationships)
        except (SQLAlchemyError, ValueError) as exc:
            warning = f"Could not inspect table '{table_name}' ({type(exc).__name__})."
            output.warnings.append(warning)
    return output


def _read_live_table(
    context: _LiveContext,
    table_name: str,
) -> tuple[TableMetadata, list[RelationshipMetadata]]:
    inspector = context.inspector
    schema = context.schema_name
    columns = inspector.get_columns(table_name, schema=schema)
    primary_keys = list(inspector.get_pk_constraint(table_name, schema=schema).get("constrained_columns") or [])
    foreign_keys = [_foreign_key(item) for item in inspector.get_foreign_keys(table_name, schema=schema)]
    indexes = [_index(item) for item in inspector.get_indexes(table_name, schema=schema)]
    references, relationships = _foreign_key_links(table_name, schema, foreign_keys)
    parts = _LiveTableParts(columns, primary_keys, foreign_keys, indexes, references)
    return _table_metadata(context, table_name, parts), relationships


def _table_metadata(
    context: _LiveContext,
    table_name: str,
    parts: _LiveTableParts,
) -> TableMetadata:
    primary_keys = set(parts.primary_keys)
    columns = [_column(item, primary_keys, parts.references) for item in parts.columns]
    return {
        "table_name": table_name,
        "schema_name": context.schema_name,
        "table_type": "BASE TABLE",
        "row_count_estimate": None,
        "columns": columns,
        "primary_keys": parts.primary_keys,
        "foreign_keys": parts.foreign_keys,
        "indexes": sorted(parts.indexes, key=lambda item: item["index_name"]),
    }


def _foreign_key_links(
    table_name: str,
    schema_name: str | None,
    foreign_keys: list[ForeignKeyMetadata],
) -> tuple[dict[str, ColumnReference], list[RelationshipMetadata]]:
    references: dict[str, ColumnReference] = {}
    relationships: list[RelationshipMetadata] = []
    for foreign_key in foreign_keys:
        links, pairs = build_fk_links(table_name, schema_name, foreign_key)
        references.update(links)
        relationships.extend(pairs)
    return references, relationships


def _column(
    column: ReflectedColumn,
    primary_keys: set[str],
    references: dict[str, ColumnReference],
) -> ColumnMetadata:
    name = str(column["name"])
    default_value = column.get("default")
    return {
        "column_name": name,
        "data_type": normalize_data_type(column["type"]),
        "is_nullable": bool(column.get("nullable", True)),
        "is_primary_key": name in primary_keys,
        "is_foreign_key": name in references,
        "default_value": str(default_value) if default_value is not None else None,
        "sample_values": None,
        "references": references.get(name),
    }


def _foreign_key(value: ReflectedForeignKeyConstraint) -> ForeignKeyMetadata:
    constraint_name = value.get("name")
    referred_table = value.get("referred_table")
    if not referred_table:
        raise ValueError("Foreign key target table is missing.")
    return {
        "constraint_name": str(constraint_name) if constraint_name else None,
        "constrained_columns": [str(item) for item in value.get("constrained_columns") or []],
        "referred_schema": value.get("referred_schema"),
        "referred_table": str(referred_table),
        "referred_columns": [str(item) for item in value.get("referred_columns") or []],
    }


def _index(value: ReflectedIndex) -> IndexMetadata:
    return {
        "index_name": str(value.get("name") or ""),
        "columns": [str(item) for item in value.get("column_names") or []],
        "is_unique": bool(value.get("unique")),
    }


def _live_result(context: _LiveContext, output: _LiveOutput) -> SchemaExtractionResult:
    raw_schema: RawSchema = {
        "source": {
            "type": "live_connection",
            "db_engine": context.request["db_type"],
            "connection_id": context.request["connection_id"],
            "extracted_at": utc_timestamp(),
        },
        "tables": output.tables,
        "relationships": sorted(output.relationships, key=_relationship_key),
    }
    return {"raw_schema": raw_schema, "warnings": output.warnings}


def _relationship_key(value: RelationshipMetadata) -> tuple[str, str, str, str]:
    return value["from_table"], value["from_column"], value["to_table"], value["to_column"]
