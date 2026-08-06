"""Orchestration service for SQL dump technical previews."""

from collections.abc import AsyncIterable

from src.models.schema_metadata import SchemaDialect
from src.models.schemas import SqlDumpPreviewResponse
from src.services.sql_dump_parser import parse_sql_dump
from src.services.sql_dump_scanner import scan_sql_dump


async def parse_sql_dump_preview(
    chunks: AsyncIterable[bytes],
    filename: str,
    dialect_override: SchemaDialect | None = None,
) -> SqlDumpPreviewResponse:
    """Scan a dump and return canonical technical schema metadata."""
    scan_result = await scan_sql_dump(
        chunks,
        filename,
        dialect_override=dialect_override,
    )
    parse_result = await parse_sql_dump(scan_result)
    return SqlDumpPreviewResponse(
        dialect=parse_result.schema_metadata.dialect,
        raw_schema=parse_result.schema_metadata,
        diagnostics=parse_result.diagnostics,
    )
