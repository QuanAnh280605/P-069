"""Typed raw-schema contract shared by extraction adapters and AI nodes."""

from __future__ import annotations

from typing import Literal, TypeAlias

from typing_extensions import TypedDict

DatabaseType = Literal["postgresql", "mysql", "sqlite"]
DumpDatabaseType = Literal["postgresql", "mysql"]


class SourceMetadata(TypedDict):
    """Describe where and when schema metadata was extracted."""

    type: Literal["live_connection", "sql_dump"]
    db_engine: DatabaseType
    connection_id: int | None
    extracted_at: str


class ColumnReference(TypedDict):
    """Identify the target of a foreign-key column."""

    table: str
    column: str
    schema: str | None


class ColumnMetadata(TypedDict):
    """Normalized metadata for one database column."""

    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    default_value: str | None
    sample_values: None
    references: ColumnReference | None


class ForeignKeyMetadata(TypedDict):
    """Preserve the grouping of a foreign-key constraint."""

    constraint_name: str | None
    constrained_columns: list[str]
    referred_schema: str | None
    referred_table: str
    referred_columns: list[str]


class IndexMetadata(TypedDict):
    """Normalized metadata for an explicit database index."""

    index_name: str
    columns: list[str]

    is_unique: bool


class TableMetadata(TypedDict):
    """Normalized metadata for one base table."""

    table_name: str
    schema_name: str | None
    table_type: Literal["BASE TABLE"]
    row_count_estimate: None
    columns: list[ColumnMetadata]
    primary_keys: list[str]
    foreign_keys: list[ForeignKeyMetadata]
    indexes: list[IndexMetadata]


class RelationshipMetadata(TypedDict):
    """Represent one column pair from a foreign-key relationship."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relationship_type: Literal["many_to_one"]


class RawSchema(TypedDict):
    """Stable common input consumed by AI pipeline nodes."""

    source: SourceMetadata
    tables: list[TableMetadata]
    relationships: list[RelationshipMetadata]


class LiveSchemaRequest(TypedDict):
    """Request encrypted live-database schema extraction."""

    conn_url_enc: str
    db_type: DatabaseType
    connection_id: int


class DumpSchemaRequest(TypedDict):
    """Request non-executing SQL dump schema extraction."""

    sql_content: str
    db_type: DumpDatabaseType


SchemaExtractionRequest: TypeAlias = LiveSchemaRequest | DumpSchemaRequest


class SchemaExtractionResult(TypedDict):
    """Return normalized schema and recoverable sanitized warnings."""

    raw_schema: RawSchema
    warnings: list[str]
