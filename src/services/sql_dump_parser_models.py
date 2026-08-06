"""Internal builders and public errors for SQL dump AST extraction."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import exp

from src.models.schema_metadata import (
    ColumnMetadata,
    DiagnosticCode,
    DiagnosticSeverity,
    Identifier,
    ParseDiagnostic,
    QualifiedIdentifier,
)
from src.services.sql_dump_scanner_models import ScannedStatement


class SqlDumpParseError(ValueError):
    """Fatal parser error containing only safe structured diagnostics."""

    def __init__(self, diagnostics: tuple[ParseDiagnostic, ...]) -> None:
        super().__init__(diagnostics[0].message)
        self.diagnostics = diagnostics

    @property
    def diagnostic(self) -> ParseDiagnostic:
        """Return the first fatal diagnostic for simple service adapters."""
        return self.diagnostics[0]


@dataclass(frozen=True)
class SourceLocation:
    """Scanner-provided source location for safe parser diagnostics."""

    statement_index: int
    line: int
    column: int

    @classmethod
    def from_statement(cls, statement: ScannedStatement) -> SourceLocation:
        """Build a source location from a scanned DDL candidate."""
        return cls(statement.statement_index, statement.line, statement.column)


@dataclass(frozen=True)
class ColumnBuilder:
    """Mutable-phase column values before PK flags are resolved."""

    name: Identifier
    ordinal_position: int
    raw_data_type: str
    data_type: str
    nullable: bool
    default_expression: str | None


@dataclass(frozen=True)
class PrimaryKeySpec:
    """Deferred exact primary-key mapping."""

    columns: tuple[Identifier, ...]
    constraint_name: Identifier | None
    source: SourceLocation


@dataclass(frozen=True)
class ForeignKeySpec:
    """Deferred exact foreign-key mapping."""

    columns: tuple[Identifier, ...]
    constraint_name: Identifier | None
    referred_schema: Identifier
    referred_table: Identifier
    referred_columns: tuple[Identifier, ...]
    source: SourceLocation


@dataclass
class TableBuilder:
    """First-pass table registry entry resolved after every table exists."""

    schema_name: Identifier
    table_name: Identifier
    columns: list[ColumnBuilder]
    source: SourceLocation
    primary_keys: list[PrimaryKeySpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        """Return the deterministic qualified table key."""
        return self.schema_name.normalized_name, self.table_name.normalized_name


@dataclass(frozen=True)
class AlterRecord:
    """Deferred ALTER TABLE AST applied after CREATE registration."""

    expression: exp.Alter
    source: SourceLocation
    default_schema: Identifier | None = None


def target_has_columns(table: TableBuilder, columns: tuple[Identifier, ...]) -> bool:
    """Return whether a deferred target contains every referenced column."""
    target_names = {item.name.normalized_name for item in table.columns}
    return bool(columns) and all(item.normalized_name in target_names for item in columns)


def build_column(column: ColumnBuilder, primary_names: set[str]) -> ColumnMetadata:
    """Build immutable column metadata after primary keys are resolved."""
    primary = column.name.normalized_name in primary_names
    return ColumnMetadata(
        column_name=column.name,
        ordinal_position=column.ordinal_position,
        raw_data_type=column.raw_data_type,
        data_type=column.data_type,
        nullable=column.nullable and not primary,
        default_expression=column.default_expression,
        primary_key=primary,
    )


def fatal_parse_error(
    source: SourceLocation,
    code: DiagnosticCode,
    message: str,
    table: TableBuilder | None = None,
) -> SqlDumpParseError:
    """Build a safe fatal diagnostic for API error mapping."""
    object_name = None
    if table is not None:
        object_name = QualifiedIdentifier(schema_name=table.schema_name, object_name=table.table_name)
    diagnostic = ParseDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        statement_index=source.statement_index,
        line=source.line,
        column=source.column,
        object_name=object_name,
        recoverable=False,
    )
    return SqlDumpParseError((diagnostic,))
