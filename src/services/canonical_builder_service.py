"""Canonical Builder Service.

Centralized service for building and validating immutable RawSchemaMetadata
(Canonical Model) from live target databases or DDL SQL dumps.

Handles all normalization cases:
  - Case C-1.x: Basic uppercase/lowercase identifiers and ordinal positions.
  - Case C-2.x: Naming conventions (PascalCase, camelCase, abbreviations).
  - Case C-3.x: SQL reserved words and quoted identifiers (double-quotes, backticks).
  - Case C-4.x: Complex data types with dialect-specific modifiers.
  - Case C-5.x: Edge cases — NUL bytes, collision, composite keys, arity mismatch.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

from src.models.schema_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    ParseResult,
    RawSchemaMetadata,
    SchemaDialect,
    TableMetadata,
)
from src.services.live_db_service import (
    introspect_live_database,
    resolve_and_validate_dialect,
)
from src.services.sql_dump_parser import parse_sql_dump
from src.services.sql_dump_scanner import scan_sql_dump


class CanonicalBuilderService:
    """Service for building canonical schema metadata contracts from various sources."""

    @staticmethod
    def build_from_live_db(
        conn_url: str,
        dialect: str | SchemaDialect | None = None,
    ) -> RawSchemaMetadata:
        """Build canonical schema metadata from a live target database connection URL.

        Handles all naming convention cases (C-1.x to C-5.x). The SQLAlchemy
        Inspector extracts raw metadata; this service validates and finalizes
        the immutable Canonical contract.
        """
        resolved_dialect = resolve_and_validate_dialect(conn_url, dialect)
        raw_schema = introspect_live_database(conn_url, resolved_dialect)
        _validate_canonical_integrity(raw_schema)
        return raw_schema

    @staticmethod
    async def build_from_sql_dump(
        chunks: AsyncIterable[bytes],
        filename: str,
        dialect_override: SchemaDialect | None = None,
    ) -> ParseResult:
        """Build canonical schema metadata and diagnostics from a DDL SQL dump stream.

        Handles quoted identifiers (C-3.x), complex data types (C-4.x), and
        edge cases detected at parse time (C-5.x).
        """
        scan_result = await scan_sql_dump(
            chunks,
            filename,
            dialect_override=dialect_override,
        )
        parse_result = await parse_sql_dump(scan_result)
        _validate_canonical_integrity(parse_result.schema_metadata)
        return parse_result

    @staticmethod
    def build_from_raw_dict(data: dict[str, Any]) -> RawSchemaMetadata:
        """Reconstruct and validate canonical schema metadata from a raw dictionary.

        Used to restore previously persisted schema metadata (e.g., from JSON
        stored in the Metadata Store) back into the immutable Canonical contract.
        Pydantic model_validate enforces all field types and frozen constraints.
        """
        raw_schema = RawSchemaMetadata.model_validate(data)
        _validate_canonical_integrity(raw_schema)
        return raw_schema


# ---------------------------------------------------------------------------
# Internal integrity validators
# ---------------------------------------------------------------------------


def _validate_canonical_integrity(raw_schema: RawSchemaMetadata) -> None:
    """Run all post-build integrity checks on a fully constructed Canonical schema.

    Checks performed:
      - Column ordinal positions are unique within each table (C-1.4).
      - Normalized column names have no collisions within a table (C-5.3).
      - All FK target tables exist in the schema graph (C-5.5, C-5.6).
      - FK referred columns exist in the target table (C-5.6).
    """
    table_index = {table.qualified_identity.canonical_key: table for table in raw_schema.tables}
    for table in raw_schema.tables:
        _validate_column_ordinals(table)
        _validate_normalized_column_uniqueness(table)
        _validate_foreign_key_targets(table, table_index)


def _validate_column_ordinals(table: TableMetadata) -> None:
    """Ensure column ordinal positions are unique and start at 1 (C-1.4).

    RawSchemaMetadata.validate_local_constraints in schema_metadata.py also
    performs this check, but we repeat it here as an explicit service-layer
    guard to catch any programmatic bypass.
    """
    ordinals = [col.ordinal_position for col in table.columns]
    if len(ordinals) != len(set(ordinals)):
        raise ValueError(
            f"Table '{table.table_name.raw_name}': "
            "duplicate column ordinal_position detected in canonical schema."
        )


def _validate_normalized_column_uniqueness(table: TableMetadata) -> None:
    """Ensure no two columns share the same normalized_name within a table (C-5.3).

    A collision occurs when two differently-cased unquoted names resolve to
    the same lowercase key, e.g. 'Email' and 'email' in the same table.
    """
    seen: set[str] = set()
    for col in table.columns:
        key = col.column_name.normalized_name
        if key in seen:
            raise ValueError(
                f"Table '{table.table_name.raw_name}': "
                f"duplicate normalized column identity '{key}' — "
                "two unquoted column names resolve to the same canonical key."
            )
        seen.add(key)


def _validate_foreign_key_targets(
    table: TableMetadata,
    table_index: dict[tuple[str, str], TableMetadata],
) -> None:
    """Verify every FK in a table resolves to a known table and column set (C-5.5, C-5.6).

    Also catches arity mismatch at the service layer as a defensive check
    on top of the Pydantic model_validator in ForeignKeyMetadata (C-5.5).
    """
    for fk in table.foreign_keys:
        _validate_fk_arity(table, fk)
        _validate_fk_target_table(table, fk, table_index)
        _validate_fk_target_columns(table, fk, table_index)


def _validate_fk_arity(table: TableMetadata, fk: ForeignKeyMetadata) -> None:
    """Raise if the FK local and referred column counts differ (C-5.5)."""
    if len(fk.constrained_columns) != len(fk.referred_columns):
        raise ValueError(
            f"Table '{table.table_name.raw_name}': "
            "foreign key arity mismatch — "
            f"local columns ({len(fk.constrained_columns)}) "
            f"!= referred columns ({len(fk.referred_columns)})."
        )


def _validate_fk_target_table(
    table: TableMetadata,
    fk: ForeignKeyMetadata,
    table_index: dict[tuple[str, str], TableMetadata],
) -> None:
    """Raise if the FK target table does not exist in the schema graph (C-5.6)."""
    ref_key = fk.referred_identity.canonical_key
    if ref_key not in table_index:
        raise ValueError(
            f"Table '{table.table_name.raw_name}': "
            f"foreign key references unknown table "
            f"'{fk.referred_schema.normalized_name}.{fk.referred_table.normalized_name}'."
        )


def _validate_fk_target_columns(
    table: TableMetadata,
    fk: ForeignKeyMetadata,
    table_index: dict[tuple[str, str], TableMetadata],
) -> None:
    """Raise if any FK referred column is absent from the target table (C-5.6)."""
    ref_key = fk.referred_identity.canonical_key
    target = table_index.get(ref_key)
    if target is None:
        return
    target_cols: set[str] = {col.column_name.normalized_name for col in target.columns}
    referred_cols: set[str] = {col.normalized_name for col in fk.referred_columns}
    missing = referred_cols - target_cols
    if missing:
        raise ValueError(
            f"Table '{table.table_name.raw_name}': "
            f"foreign key refers to unknown columns {sorted(missing)} "
            f"in target table '{fk.referred_table.normalized_name}'."
        )


def summarize_canonical_schema(raw_schema: RawSchemaMetadata) -> dict[str, Any]:
    """Return a lightweight summary dict of a validated canonical schema.

    Useful for logging, debugging, and building prompts for Enrich/Metric nodes.
    Output contains: dialect, table count, per-table column names and types.
    """
    tables_summary = []
    for table in raw_schema.tables:
        columns_summary = _summarize_columns(table.columns)
        tables_summary.append({
            "table_name": table.table_name.raw_name,
            "schema_name": table.schema_name.normalized_name,
            "column_count": len(table.columns),
            "has_primary_key": table.primary_key is not None,
            "foreign_key_count": len(table.foreign_keys),
            "columns": columns_summary,
        })
    return {
        "dialect": raw_schema.dialect.value,
        "contract_version": raw_schema.contract_version,
        "table_count": len(raw_schema.tables),
        "tables": tables_summary,
    }


def _summarize_columns(columns: tuple[ColumnMetadata, ...]) -> list[dict[str, Any]]:
    """Build a compact column list suitable for LLM prompt injection."""
    return [
        {
            "column_name": col.column_name.raw_name,
            "normalized_name": col.column_name.normalized_name,
            "data_type": col.data_type,
            "nullable": col.nullable,
            "primary_key": col.primary_key,
        }
        for col in columns
    ]
