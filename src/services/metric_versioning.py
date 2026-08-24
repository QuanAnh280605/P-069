"""Append-only version primitives for semantic metrics.

Every edit to a metric produces a new ``metric_versions`` row; nothing is ever
overwritten or deleted. A published (approved) metric keeps serving its approved
definition while an edit waits as an *open* version, so Flow 2 queries never
break mid-review.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import MetricVersionModel, utc_now

logger = logging.getLogger(__name__)

VERSION_STATUS_PENDING = "pending_approval"
VERSION_STATUS_NEEDS_REVIEW = "needs_review"
VERSION_STATUS_APPROVED = "approved"
VERSION_STATUS_SUPERSEDED = "superseded"
VERSION_STATUS_REJECTED = "rejected"
OPEN_VERSION_STATUSES = (VERSION_STATUS_PENDING, VERSION_STATUS_NEEDS_REVIEW)
_ALLOWED_VERSION_STATUSES = (
    *OPEN_VERSION_STATUSES,
    VERSION_STATUS_APPROVED,
    VERSION_STATUS_SUPERSEDED,
    VERSION_STATUS_REJECTED,
)


def version_status_for(metric_status: str) -> str:
    """Map a metric lifecycle status onto a valid version-row status."""
    return metric_status if metric_status in _ALLOWED_VERSION_STATUSES else VERSION_STATUS_PENDING


async def next_version_number(db: AsyncSession, metric_id: int) -> int:
    """Return the next unused version number for *metric_id*."""
    stmt = select(func.max(MetricVersionModel.version)).where(MetricVersionModel.metric_id == metric_id)
    highest = (await db.execute(stmt)).scalar_one_or_none()
    return (highest or 0) + 1


async def latest_open_version(db: AsyncSession, metric_id: int) -> MetricVersionModel | None:
    """Return the newest version still awaiting a decision, if any."""
    stmt = (
        select(MetricVersionModel)
        .where(
            MetricVersionModel.metric_id == metric_id,
            MetricVersionModel.status.in_(OPEN_VERSION_STATUSES),
        )
        .order_by(MetricVersionModel.version.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def load_versions(db: AsyncSession, metric_id: int) -> list[MetricVersionModel]:
    """Load the full version history of *metric_id* with actor relationships."""
    stmt = (
        select(MetricVersionModel)
        .where(MetricVersionModel.metric_id == metric_id)
        .options(selectinload(MetricVersionModel.changer), selectinload(MetricVersionModel.approver))
        .order_by(MetricVersionModel.version)
    )
    return list((await db.execute(stmt)).scalars().all())


async def load_version(db: AsyncSession, metric_id: int, version: int) -> MetricVersionModel | None:
    """Load one exact historical snapshot of *metric_id*."""
    stmt = select(MetricVersionModel).where(
        MetricVersionModel.metric_id == metric_id,
        MetricVersionModel.version == version,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def record_version(
    db: AsyncSession,
    metric_id: int,
    payload: dict[str, Any],
    name: str,
    status: str,
    changed_by: int | None,
    change_reason: str = "",
    parent_version: int | None = None,
    version: int | None = None,
) -> MetricVersionModel:
    """Append one immutable snapshot to a metric's history."""
    resolved_version = version if version is not None else await next_version_number(db, metric_id)
    record = MetricVersionModel(
        metric_id=metric_id,
        version=resolved_version,
        name=name,
        formula="",
        definition=payload,
        status=status,
        parent_version=parent_version,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    if status == VERSION_STATUS_APPROVED:
        record.approved_by = changed_by
        record.approved_at = utc_now()
    db.add(record)
    await db.flush()
    return record


async def supersede_open_versions(db: AsyncSession, metric_id: int, exclude_version: int | None = None) -> int:
    """Mark every open draft as superseded, keeping the rows for audit."""
    stmt = select(MetricVersionModel).where(
        MetricVersionModel.metric_id == metric_id,
        MetricVersionModel.status.in_(OPEN_VERSION_STATUSES),
    )
    superseded = 0
    for record in (await db.execute(stmt)).scalars().all():
        if exclude_version is not None and record.version == exclude_version:
            continue
        record.status = VERSION_STATUS_SUPERSEDED
        superseded += 1
    if superseded:
        await db.flush()
    return superseded


def mark_version_approved(record: MetricVersionModel, actor_id: int) -> None:
    """Stamp a version row as the approved, published definition."""
    record.status = VERSION_STATUS_APPROVED
    record.approved_by = actor_id
    record.approved_at = utc_now()


async def reject_version(
    db: AsyncSession,
    metric_id: int,
    version: int,
    actor_id: int,
    reason: str = "",
) -> MetricVersionModel:
    """Reject an open draft without touching the published definition."""
    if not reason or not reason.strip():
        raise ValueError("Lý do từ chối không được để trống")
    record = await load_version(db, metric_id, version)
    if record is None:
        raise ValueError(f"Version {version} not found for metric {metric_id}")
    if record.status not in OPEN_VERSION_STATUSES:
        raise ValueError(f"Version {version} is not awaiting approval")
    record.status = VERSION_STATUS_REJECTED
    record.approved_by = actor_id
    record.approved_at = utc_now()
    if reason:
        record.change_reason = f"{record.change_reason}\n[Từ chối] {reason}".strip()
    await db.flush()
    logger.info("Metric version rejected metric_id=%s version=%s actor=%s", metric_id, version, actor_id)
    return record
