"""Canonical schema metadata contract shared by all acquisition adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_METADATA_VERSION: Literal["1.0"] = "1.0"
MYSQL_DEFAULT_NAMESPACE = "__default__"
POSTGRESQL_DEFAULT_NAMESPACE = "public"


class SchemaDialect(StrEnum):
    """SQL dialects supported by the P1 metadata contract."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class ParseCompleteness(StrEnum):
    """Whether parsing proved that all supported core DDL was captured."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class DiagnosticSeverity(StrEnum):
    """Stable diagnostic severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(StrEnum):
    """Stable machine-readable diagnostic codes for SQL dump ingestion."""

    EMPTY_FILE = "EMPTY_FILE"
    INVALID_EXTENSION = "INVALID_EXTENSION"
    INVALID_ENCODING = "INVALID_ENCODING"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    STATEMENT_TOO_LARGE = "STATEMENT_TOO_LARGE"
    DIALECT_AMBIGUOUS = "DIALECT_AMBIGUOUS"
    DIALECT_CONFLICT = "DIALECT_CONFLICT"
    UNSUPPORTED_STATEMENT = "UNSUPPORTED_STATEMENT"
    DATA_STATEMENTS_IGNORED = "DATA_STATEMENTS_IGNORED"
    DDL_PARSE_ERROR = "DDL_PARSE_ERROR"
    DUPLICATE_OBJECT = "DUPLICATE_OBJECT"
    CONFLICTING_CONSTRAINT = "CONFLICTING_CONSTRAINT"
    UNRESOLVED_FOREIGN_KEY = "UNRESOLVED_FOREIGN_KEY"
    NO_SUPPORTED_DDL = "NO_SUPPORTED_DDL"


class CanonicalModel(BaseModel):
    """Base configuration for immutable, versioned contract values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def normalize_identifier(name: str, dialect: SchemaDialect, quoted: bool) -> str:
    """Return the deterministic exact-match key for an SQL identifier."""
    if quoted:
        return name
    if dialect in (SchemaDialect.POSTGRESQL, SchemaDialect.MYSQL, SchemaDialect.SQLITE):
        return name.lower()
    raise ValueError(f"Unsupported dialect: {dialect}")


class Identifier(CanonicalModel):
    """An identifier with source spelling and its deterministic match key."""

    raw_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    quoted: bool = False

    @classmethod
    def from_raw(cls, raw_name: str, dialect: SchemaDialect, quoted: bool = False) -> Self:
        """Build an identifier using the P1 dialect normalization policy."""
        normalized_name = normalize_identifier(raw_name, dialect, quoted)
        return cls(raw_name=raw_name, normalized_name=normalized_name, quoted=quoted)

    @model_validator(mode="after")
    def reject_unsafe_value(self) -> Self:
        if "\x00" in self.raw_name or "\x00" in self.normalized_name:
            raise ValueError("Identifiers cannot contain NUL characters")
        return self


class QualifiedIdentifier(CanonicalModel):
    """A schema-qualified table or diagnostic object identity."""

    schema_name: Identifier
    object_name: Identifier

    @property
    def canonical_key(self) -> tuple[str, str]:
        """Return the exact qualified lookup key used by resolvers."""
        return self.schema_name.normalized_name, self.object_name.normalized_name


class SchemaMetadata(CanonicalModel):
    """A database namespace represented independently of persistence."""

    schema_name: Identifier


class ColumnMetadata(CanonicalModel):
    """Canonical technical metadata for one ordered table column."""

    column_name: Identifier
    ordinal_position: int = Field(ge=1)
    raw_data_type: str = Field(min_length=1)
    data_type: str = Field(min_length=1, description="Dialect-normalized safe type text")
    nullable: bool
    default_expression: str | None = None
    primary_key: bool = False
    sample_values: tuple[str, ...] | None = None


class PrimaryKeyMetadata(CanonicalModel):
    """An ordered primary-key column mapping."""

    constraint_name: Identifier | None = None
    constrained_columns: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_columns(self) -> Self:
        _reject_duplicate_identifiers(self.constrained_columns, "primary key column")
        return self


class ForeignKeyMetadata(CanonicalModel):
    """An ordered, schema-qualified foreign-key mapping."""

    constraint_name: Identifier | None = None
    constrained_columns: tuple[Identifier, ...] = Field(min_length=1)
    referred_schema: Identifier
    referred_table: Identifier
    referred_columns: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_column_mapping(self) -> Self:
        if len(self.constrained_columns) != len(self.referred_columns):
            raise ValueError("Foreign key local and referred column arity must match")
        _reject_duplicate_identifiers(self.constrained_columns, "foreign key column")
        _reject_duplicate_identifiers(self.referred_columns, "referred column")
        return self

    @property
    def referred_identity(self) -> QualifiedIdentifier:
        """Return the exact qualified identity of the referenced table."""
        return QualifiedIdentifier(schema_name=self.referred_schema, object_name=self.referred_table)


class TableMetadata(CanonicalModel):
    """Canonical metadata for one schema-qualified table."""

    schema_name: Identifier
    table_name: Identifier
    columns: tuple[ColumnMetadata, ...] = Field(min_length=1)
    primary_key: PrimaryKeyMetadata | None = None
    foreign_keys: tuple[ForeignKeyMetadata, ...] = ()

    @field_validator("columns")
    @classmethod
    def order_columns(cls, columns: tuple[ColumnMetadata, ...]) -> tuple[ColumnMetadata, ...]:
        return tuple(sorted(columns, key=lambda column: column.ordinal_position))

    @field_validator("foreign_keys")
    @classmethod
    def order_foreign_keys(cls, foreign_keys: tuple[ForeignKeyMetadata, ...]) -> tuple[ForeignKeyMetadata, ...]:
        return tuple(sorted(foreign_keys, key=_foreign_key_sort_key))

    @model_validator(mode="after")
    def validate_local_constraints(self) -> Self:
        columns = {column.column_name.normalized_name: column for column in self.columns}
        if len(columns) != len(self.columns):
            raise ValueError("Duplicate normalized column identity")
        if len({column.ordinal_position for column in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column ordinal position")
        _validate_local_column_references(self, columns)
        _reject_duplicate_foreign_keys(self.foreign_keys)
        return self

    @property
    def qualified_identity(self) -> QualifiedIdentifier:
        """Return the table's exact schema-qualified identity."""
        return QualifiedIdentifier(schema_name=self.schema_name, object_name=self.table_name)


class RawSchemaMetadata(CanonicalModel):
    """Persistence-free canonical metadata produced by any acquisition adapter."""

    contract_version: Literal["1.0"] = SCHEMA_METADATA_VERSION
    dialect: SchemaDialect
    schemas: tuple[SchemaMetadata, ...] = ()
    tables: tuple[TableMetadata, ...] = ()

    @field_validator("schemas")
    @classmethod
    def order_schemas(cls, schemas: tuple[SchemaMetadata, ...]) -> tuple[SchemaMetadata, ...]:
        return tuple(sorted(schemas, key=lambda item: _identifier_sort_key(item.schema_name)))

    @field_validator("tables")
    @classmethod
    def order_tables(cls, tables: tuple[TableMetadata, ...]) -> tuple[TableMetadata, ...]:
        return tuple(sorted(tables, key=lambda table: table.qualified_identity.canonical_key))

    @model_validator(mode="after")
    def validate_qualified_graph(self) -> Self:
        _validate_identifier_normalization(self)
        schemas = _index_schemas(self.schemas)
        tables = _index_tables(self.tables)
        _validate_table_namespaces(tables, schemas)
        _validate_foreign_key_targets(tables)
        return self


class ParseDiagnostic(CanonicalModel):
    """Safe parser feedback kept outside canonical domain metadata."""

    severity: DiagnosticSeverity
    code: DiagnosticCode
    message: str = Field(min_length=1, max_length=1000)
    statement_index: int | None = Field(default=None, ge=0)
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    object_name: QualifiedIdentifier | None = None
    recoverable: bool

    @model_validator(mode="after")
    def validate_severity_policy(self) -> Self:
        if self.recoverable == (self.severity == DiagnosticSeverity.ERROR):
            raise ValueError("Errors must be fatal and non-errors must be recoverable")
        return self


class ParseResult(CanonicalModel):
    """Canonical schema plus separate ordered diagnostics and completeness."""

    schema_metadata: RawSchemaMetadata = Field(alias="schema")
    diagnostics: tuple[ParseDiagnostic, ...] = ()
    completeness: ParseCompleteness

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, diagnostics: tuple[ParseDiagnostic, ...]) -> tuple[ParseDiagnostic, ...]:
        return tuple(sorted(diagnostics, key=_diagnostic_sort_key))

    @model_validator(mode="after")
    def validate_completeness_policy(self) -> Self:
        has_fatal = any(not item.recoverable for item in self.diagnostics)
        if self.completeness == ParseCompleteness.COMPLETE and (has_fatal or not self.schema_metadata.tables):
            raise ValueError("Complete results require tables and cannot contain fatal diagnostics")
        if self.completeness == ParseCompleteness.INCOMPLETE and not has_fatal:
            raise ValueError("Incomplete results require at least one fatal diagnostic")
        _validate_diagnostic_identifiers(self)
        return self


def default_schema_identifier(dialect: SchemaDialect) -> Identifier:
    """Return the non-null default namespace required by the P1 contract."""
    raw_name = POSTGRESQL_DEFAULT_NAMESPACE if dialect == SchemaDialect.POSTGRESQL else MYSQL_DEFAULT_NAMESPACE
    return Identifier.from_raw(raw_name, dialect)


def _identifier_sort_key(identifier: Identifier) -> tuple[str, str, bool]:
    return identifier.normalized_name, identifier.raw_name, identifier.quoted


def _foreign_key_sort_key(foreign_key: ForeignKeyMetadata) -> tuple[object, ...]:
    return (
        tuple(column.normalized_name for column in foreign_key.constrained_columns),
        foreign_key.referred_schema.normalized_name,
        foreign_key.referred_table.normalized_name,
        tuple(column.normalized_name for column in foreign_key.referred_columns),
    )


def _diagnostic_sort_key(diagnostic: ParseDiagnostic) -> tuple[object, ...]:
    object_key = diagnostic.object_name.canonical_key if diagnostic.object_name else ("", "")
    return (
        diagnostic.statement_index if diagnostic.statement_index is not None else -1,
        diagnostic.line if diagnostic.line is not None else -1,
        diagnostic.column if diagnostic.column is not None else -1,
        diagnostic.code.value,
        object_key,
    )


def _reject_duplicate_identifiers(identifiers: tuple[Identifier, ...], label: str) -> None:
    keys = [identifier.normalized_name for identifier in identifiers]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate normalized {label} identity")


def _reject_duplicate_foreign_keys(foreign_keys: tuple[ForeignKeyMetadata, ...]) -> None:
    keys = [_foreign_key_sort_key(foreign_key) for foreign_key in foreign_keys]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate foreign key mapping")


def _validate_local_column_references(table: TableMetadata, columns: dict[str, ColumnMetadata]) -> None:
    primary_names = set()
    if table.primary_key:
        primary_names = {item.normalized_name for item in table.primary_key.constrained_columns}
        if not primary_names.issubset(columns):
            raise ValueError("Primary key references an unknown local column")
    flagged_names = {key for key, column in columns.items() if column.primary_key}
    if flagged_names != primary_names:
        raise ValueError("Column primary_key flags must match the table primary key")
    for foreign_key in table.foreign_keys:
        local_names = {item.normalized_name for item in foreign_key.constrained_columns}
        if not local_names.issubset(columns):
            raise ValueError("Foreign key references an unknown local column")


def _iter_identifiers(schema: RawSchemaMetadata) -> tuple[Identifier, ...]:
    identifiers = [item.schema_name for item in schema.schemas]
    for table in schema.tables:
        identifiers.extend((table.schema_name, table.table_name))
        identifiers.extend(column.column_name for column in table.columns)
        if table.primary_key:
            identifiers.extend(table.primary_key.constrained_columns)
            if table.primary_key.constraint_name:
                identifiers.append(table.primary_key.constraint_name)
        for foreign_key in table.foreign_keys:
            identifiers.extend(foreign_key.constrained_columns)
            identifiers.extend((foreign_key.referred_schema, foreign_key.referred_table))
            identifiers.extend(foreign_key.referred_columns)
            if foreign_key.constraint_name:
                identifiers.append(foreign_key.constraint_name)
    return tuple(identifiers)


def _validate_identifier_normalization(schema: RawSchemaMetadata) -> None:
    for identifier in _iter_identifiers(schema):
        expected = normalize_identifier(identifier.raw_name, schema.dialect, identifier.quoted)
        if identifier.normalized_name != expected:
            raise ValueError(f"Non-canonical identifier normalization: {identifier.raw_name!r}")


def _validate_diagnostic_identifiers(result: ParseResult) -> None:
    for diagnostic in result.diagnostics:
        if diagnostic.object_name is None:
            continue
        identifiers = (diagnostic.object_name.schema_name, diagnostic.object_name.object_name)
        for identifier in identifiers:
            expected = normalize_identifier(identifier.raw_name, result.schema_metadata.dialect, identifier.quoted)
            if identifier.normalized_name != expected:
                raise ValueError("Diagnostic object uses non-canonical identifier normalization")


def _index_schemas(schemas: tuple[SchemaMetadata, ...]) -> dict[str, SchemaMetadata]:
    result = {item.schema_name.normalized_name: item for item in schemas}
    if len(result) != len(schemas):
        raise ValueError("Duplicate normalized schema identity")
    return result


def _index_tables(tables: tuple[TableMetadata, ...]) -> dict[tuple[str, str], TableMetadata]:
    result = {item.qualified_identity.canonical_key: item for item in tables}
    if len(result) != len(tables):
        raise ValueError("Duplicate qualified table identity")
    return result


def _validate_table_namespaces(
    tables: dict[tuple[str, str], TableMetadata], schemas: dict[str, SchemaMetadata]
) -> None:
    if any(schema_name not in schemas for schema_name, _ in tables):
        raise ValueError("Every table namespace must be declared in schemas")


def _validate_foreign_key_targets(tables: dict[tuple[str, str], TableMetadata]) -> None:
    for table in tables.values():
        for foreign_key in table.foreign_keys:
            target = tables.get(foreign_key.referred_identity.canonical_key)
            if target is None:
                raise ValueError("Foreign key references an unknown qualified table")
            target_columns = {column.column_name.normalized_name for column in target.columns}
            referred_names = {column.normalized_name for column in foreign_key.referred_columns}
            if not referred_names.issubset(target_columns):
                raise ValueError("Foreign key references an unknown target column")
