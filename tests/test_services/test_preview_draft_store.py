"""Tests for bounded owner-bound process-local preview drafts."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.schema_metadata import SchemaDialect
from src.services.preview_draft_store import (
    InMemoryPreviewDraftStore,
    PreviewDraftCapacityError,
    PreviewDraftNotFoundError,
)
from src.services.sql_dump_parser import parse_sql_dump
from src.services.sql_dump_scanner import scan_sql_dump


async def _chunks():
    yield b"CREATE TABLE accounts (id integer PRIMARY KEY);"


async def _parse_result():
    scan = await scan_sql_dump(
        _chunks(),
        "schema.sql",
        dialect_override=SchemaDialect.POSTGRESQL,
    )
    return await parse_sql_dump(scan)


@pytest.mark.asyncio
async def test_draft_expires_and_is_no_longer_visible() -> None:
    now = [datetime(2026, 8, 5, tzinfo=UTC)]
    store = InMemoryPreviewDraftStore(60, 2, clock=lambda: now[0])
    draft = await store.create(1, await _parse_result())

    assert await store.get(1, draft.draft_id) == draft
    now[0] += timedelta(seconds=61)

    with pytest.raises(PreviewDraftNotFoundError):
        await store.get(1, draft.draft_id)


@pytest.mark.asyncio
async def test_foreign_owner_cannot_read_or_approve_draft() -> None:
    store = InMemoryPreviewDraftStore(60, 2)
    draft = await store.create(1, await _parse_result())

    with pytest.raises(PreviewDraftNotFoundError):
        await store.get(2, draft.draft_id)
    with pytest.raises(PreviewDraftNotFoundError):
        await store.approve(2, draft.draft_id)


@pytest.mark.asyncio
async def test_capacity_is_bounded_without_evicting_live_draft() -> None:
    store = InMemoryPreviewDraftStore(60, 1)
    result = await _parse_result()
    first = await store.create(1, result)

    with pytest.raises(PreviewDraftCapacityError):
        await store.create(1, result)

    assert await store.get(1, first.draft_id) == first


@pytest.mark.asyncio
async def test_approval_changes_only_process_local_status() -> None:
    store = InMemoryPreviewDraftStore(60, 1)
    draft = await store.create(1, await _parse_result())

    approved = await store.approve(1, draft.draft_id)

    assert approved.status == "approved_preview"
    assert approved.raw_schema == draft.raw_schema
    assert approved.persistence == "none"
