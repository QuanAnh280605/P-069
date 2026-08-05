"""Thin orchestration service for the experimental SQL dump preview."""

from collections.abc import AsyncIterable

from src.models.schema_metadata import SchemaDialect
from src.models.schemas import SqlDumpPreviewResponse
from src.services.preview_draft_store import InMemoryPreviewDraftStore
from src.services.sql_dump_parser import parse_sql_dump
from src.services.sql_dump_scanner import scan_sql_dump


async def create_sql_dump_preview(
    chunks: AsyncIterable[bytes],
    filename: str,
    owner_id: int,
    draft_store: InMemoryPreviewDraftStore,
    dialect_override: SchemaDialect | None = None,
) -> SqlDumpPreviewResponse:
    """Scan, parse, and retain only canonical metadata in an in-memory draft."""
    scan_result = await scan_sql_dump(
        chunks,
        filename,
        dialect_override=dialect_override,
    )
    parse_result = await parse_sql_dump(scan_result)
    return await draft_store.create(owner_id, parse_result)
