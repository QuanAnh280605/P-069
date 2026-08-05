"""Bounded process-local draft storage for the experimental import preview."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from src.config import get_settings
from src.models.schema_metadata import ParseResult
from src.models.schemas import SqlDumpPreviewResponse


class PreviewDraftNotFoundError(LookupError):
    """Raised for missing, expired, or foreign-owner preview drafts."""


class PreviewDraftCapacityError(RuntimeError):
    """Raised when the bounded in-memory preview store is full."""


@dataclass(frozen=True)
class _DraftRecord:
    owner_id: int
    draft: SqlDumpPreviewResponse


class InMemoryPreviewDraftStore:
    """Owner-bound TTL store intended only for single-process preview use."""

    def __init__(
        self,
        ttl_seconds: int,
        max_drafts: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_drafts = max_drafts
        self._clock = clock or _utc_now
        self._records: dict[str, _DraftRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, owner_id: int, result: ParseResult) -> SqlDumpPreviewResponse:
        """Create an opaque owner-bound draft without writing domain records."""
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            if len(self._records) >= self._max_drafts:
                raise PreviewDraftCapacityError("Preview draft capacity reached")
            draft = self._build_draft(result, now)
            self._records[draft.draft_id] = _DraftRecord(owner_id, draft)
            return draft

    async def get(self, owner_id: int, draft_id: str) -> SqlDumpPreviewResponse:
        """Load a live draft only when it belongs to the requesting owner."""
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            return self._owned_record(owner_id, draft_id).draft

    async def approve(self, owner_id: int, draft_id: str) -> SqlDumpPreviewResponse:
        """Mark a preview approved in memory without invoking persistence."""
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            record = self._owned_record(owner_id, draft_id)
            approved = record.draft.model_copy(update={"status": "approved_preview"})
            self._records[draft_id] = _DraftRecord(owner_id, approved)
            return approved

    async def clear(self) -> None:
        """Clear process-local drafts for deterministic tests and shutdown."""
        async with self._lock:
            self._records.clear()

    def _build_draft(self, result: ParseResult, now: datetime) -> SqlDumpPreviewResponse:
        return SqlDumpPreviewResponse(
            draft_id=secrets.token_urlsafe(24),
            status="pending_review",
            dialect=result.schema_metadata.dialect.value,
            raw_schema=result.schema_metadata,
            diagnostics=result.diagnostics,
            parse_completeness=result.completeness,
            expires_at=now + self._ttl,
        )

    def _owned_record(self, owner_id: int, draft_id: str) -> _DraftRecord:
        record = self._records.get(draft_id)
        if record is None or record.owner_id != owner_id:
            raise PreviewDraftNotFoundError("Preview draft not found")
        return record

    def _purge_expired(self, now: datetime) -> None:
        expired = [key for key, item in self._records.items() if item.draft.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@lru_cache
def get_preview_draft_store() -> InMemoryPreviewDraftStore:
    """Return the process-local preview store configured for this worker."""
    settings = get_settings()
    return InMemoryPreviewDraftStore(
        ttl_seconds=settings.sql_dump_preview_ttl_seconds,
        max_drafts=settings.sql_dump_preview_max_drafts,
    )
