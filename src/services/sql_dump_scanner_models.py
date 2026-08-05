"""Public value types for the SQL dump scanner."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from src.config import get_settings
from src.models.schema_metadata import CanonicalModel, ParseDiagnostic, SchemaDialect

HARD_MAX_FILE_BYTES = 20 * 1024 * 1024
HARD_MAX_STATEMENT_BYTES = 1024 * 1024


class StatementKind(StrEnum):
    """Core DDL statement kinds accepted by the Phase 3 scanner."""

    CREATE_SCHEMA = "create_schema"
    CREATE_TABLE = "create_table"
    ALTER_TABLE = "alter_table"


class ScannedStatement(CanonicalModel):
    """A bounded core DDL candidate with its source position."""

    text: str = Field(min_length=1)
    kind: StatementKind
    statement_index: int = Field(ge=0)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    default_schema_name: str | None = None
    default_schema_quoted: bool = False


class ScannerLimits(CanonicalModel):
    """Resource limits that may be lowered but never exceed tested maxima."""

    max_file_bytes: int = Field(gt=0, le=HARD_MAX_FILE_BYTES)
    max_statement_bytes: int = Field(gt=0, le=HARD_MAX_STATEMENT_BYTES)
    max_diagnostics: int = Field(ge=1, le=1000)
    max_nesting_depth: int = Field(ge=1, le=512)

    @classmethod
    def configured(cls) -> ScannerLimits:
        """Build scanner limits from application settings."""
        settings = get_settings()
        return cls(
            max_file_bytes=settings.sql_dump_max_file_bytes,
            max_statement_bytes=settings.sql_dump_max_statement_bytes,
            max_diagnostics=settings.sql_dump_max_diagnostics,
            max_nesting_depth=settings.sql_dump_max_nesting_depth,
        )


class ScanResult(CanonicalModel):
    """Safe scanner output containing DDL candidates but never row payloads."""

    dialect: SchemaDialect
    statements: tuple[ScannedStatement, ...]
    diagnostics: tuple[ParseDiagnostic, ...] = ()
    total_bytes: int = Field(ge=0)
    max_diagnostics: int = Field(default=100, ge=1, le=1000, exclude=True)


class SqlDumpScanError(ValueError):
    """Fatal scanner error represented by one stable safe diagnostic."""

    def __init__(self, diagnostic: ParseDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class ScannerMode(StrEnum):
    """Internal lexical states retained across input chunks."""

    NEUTRAL = "neutral"
    SINGLE_QUOTE = "single_quote"
    DOUBLE_QUOTE = "double_quote"
    BACKTICK = "backtick"
    LINE_COMMENT = "line_comment"
    BLOCK_COMMENT = "block_comment"
    DOLLAR_QUOTE = "dollar_quote"
    COPY_DATA = "copy_data"


class StatementCategory(StrEnum):
    """Internal early classification used to bound retained text."""

    CANDIDATE = "candidate"
    DATA = "data"
    COPY = "copy"
    SKIP = "skip"
    UNSUPPORTED = "unsupported"
    DIRECTIVE = "directive"
    NAMESPACE = "namespace"
