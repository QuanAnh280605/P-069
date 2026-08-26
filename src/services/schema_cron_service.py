"""Background Daily Cron Service for Schema Auto-Sync (02:00 AM).

Provides:
  - run_daily_schema_sync_job: Execute schema drift detection & self-healing across all live databases.
  - start_schema_cron_scheduler: Background asyncio task runner.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import LiveTargetDbModel, SemanticDatabaseModel
from src.services.database import get_db_session
from src.services.schema_self_healing_service import execute_self_healing

logger = logging.getLogger(__name__)

_cron_task: asyncio.Task[Any] | None = None
_RUN_HOUR = 2
_RUN_MINUTE = 0


def _seconds_until_next_run(target_hour: int = _RUN_HOUR, target_minute: int = _RUN_MINUTE) -> float:
    """Calculate seconds remaining until the next 02:00 AM occurrence."""
    now = datetime.now(UTC)
    target_time = time(hour=target_hour, minute=target_minute)
    next_run = datetime.combine(now.date(), target_time, tzinfo=UTC)
    if next_run <= now:
        next_run += timedelta(days=1)
    return max(1.0, (next_run - now).total_seconds())


async def _sync_databases_with_session(session: AsyncSession, results: dict[str, Any]) -> None:
    """Scan and self-heal all live target databases using the provided session."""
    stmt = select(SemanticDatabaseModel.id).join(
        LiveTargetDbModel, LiveTargetDbModel.semantic_db_id == SemanticDatabaseModel.id
    )
    db_ids = (await session.execute(stmt)).scalars().all()
    results["total"] = len(db_ids)

    for sem_db_id in db_ids:
        try:
            log = await execute_self_healing(session, sem_db_id, trigger_type="cron")
            if log.status == "healed":
                results["healed"] += 1
            else:
                results["synced"] += 1
            results["details"].append({"db_id": sem_db_id, "status": log.status})
        except Exception as exc:
            results["errors"] += 1
            logger.error("[Schema Cron Job] Failed auto-sync for DB ID=%d: %s", sem_db_id, exc)
            results["details"].append({"db_id": sem_db_id, "status": "error", "error": str(exc)})


async def run_daily_schema_sync_job(db: AsyncSession | None = None) -> dict[str, Any]:
    """Execute schema auto-sync across all live target databases."""
    logger.info("[Schema Cron Job] Starting scheduled daily schema auto-sync...")
    results: dict[str, Any] = {"total": 0, "healed": 0, "synced": 0, "errors": 0, "details": []}

    if db is not None:
        await _sync_databases_with_session(db, results)
    else:
        async for session in get_db_session():
            await _sync_databases_with_session(session, results)
            break

    logger.info(
        "[Schema Cron Job] Finished daily auto-sync: %d total, %d healed, %d synced, %d errors",
        results["total"],
        results["healed"],
        results["synced"],
        results["errors"],
    )
    return results


async def _cron_loop() -> None:
    """Continuous background loop triggering at 02:00 AM daily."""
    logger.info("[Schema Cron Scheduler] Daily 02:00 AM auto-sync scheduler initialized.")
    while True:
        try:
            wait_seconds = _seconds_until_next_run()
            logger.info(
                "[Schema Cron Scheduler] Next auto-sync in %.1f seconds (~%.1f hours).",
                wait_seconds,
                wait_seconds / 3600,
            )
            await asyncio.sleep(wait_seconds)
            await run_daily_schema_sync_job()
        except asyncio.CancelledError:
            logger.info("[Schema Cron Scheduler] Auto-sync scheduler cancelled.")
            break
        except Exception as exc:
            logger.error("[Schema Cron Scheduler] Error in auto-sync loop: %s", exc)
            await asyncio.sleep(60.0)


def start_schema_cron_scheduler() -> asyncio.Task[Any]:
    """Launch the daily cron scheduler task."""
    global _cron_task
    if _cron_task is None or _cron_task.done():
        _cron_task = asyncio.create_task(_cron_loop())
    return _cron_task


def stop_schema_cron_scheduler() -> None:
    """Stop the background daily cron scheduler task."""
    global _cron_task
    if _cron_task and not _cron_task.done():
        _cron_task.cancel()
        _cron_task = None
