"""Unit tests for schema cron scheduler service."""

import asyncio

import pytest

from src.services.schema_cron_service import (
    _seconds_until_next_run,
    run_daily_schema_sync_job,
    start_schema_cron_scheduler,
    stop_schema_cron_scheduler,
)


def test_seconds_until_next_run():
    """Verify seconds calculation is positive."""
    secs = _seconds_until_next_run(target_hour=2, target_minute=0)
    assert secs > 0
    assert secs <= 86400


@pytest.mark.asyncio
async def test_run_daily_schema_sync_job_empty(async_session):
    """Test running daily schema sync when no live databases exist."""
    results = await run_daily_schema_sync_job(async_session)
    assert results["total"] >= 0
    assert results["errors"] == 0


@pytest.mark.asyncio
async def test_start_and_stop_scheduler():
    """Test starting and stopping scheduler task."""
    task = start_schema_cron_scheduler()
    assert task is not None
    assert not task.done()
    stop_schema_cron_scheduler()
    await asyncio.sleep(0.01)
    assert task.cancelled() or task.done()
