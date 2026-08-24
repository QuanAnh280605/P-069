"""Tests for copy-on-write metric versioning: published edits never overwrite the live row."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    MetricVersionModel,
    SemanticColumnModel,
    SemanticTableModel,
)
from src.services.metric_service import (
    approve_metric,
    create_metric,
    reject_metric_update,
    update_metric,
)
from src.services.metric_versioning import latest_open_version
from src.services.semantic_service import ensure_semantic_database


async def _seed_tables(db: AsyncSession, db_id: int) -> None:
    """Seed one orders table with the columns the metric definitions reference."""
    table = SemanticTableModel(db_id=db_id, table_name="orders", business_name="Đơn hàng", primary_key_column="id")
    db.add(table)
    await db.flush()
    db.add(
        SemanticColumnModel(
            table_id=table.id, column_name="id", data_type="INTEGER", business_name="ID", is_primary_key=True
        )
    )
    db.add(SemanticColumnModel(table_id=table.id, column_name="total", data_type="NUMERIC", business_name="Tổng"))
    db.add(SemanticColumnModel(table_id=table.id, column_name="net", data_type="NUMERIC", business_name="Thuần"))
    await db.flush()


def _make_def(name: str, expression: str = "total", change_reason: str | None = None) -> dict:
    """Build an update payload, optionally carrying a change reason."""
    payload: dict = {
        "definition": {
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": expression},
                "base_entity": "orders",
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "",
            }
        }
    }
    if change_reason is not None:
        payload["change_reason"] = change_reason
    return payload


async def _versions(db: AsyncSession, metric_id: int) -> list[MetricVersionModel]:
    """Load every version row of *metric_id* ordered by version number."""
    stmt = (
        select(MetricVersionModel).where(MetricVersionModel.metric_id == metric_id).order_by(MetricVersionModel.version)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _published_metric(db: AsyncSession):
    """Create and approve a metric so later edits go through the draft path."""
    sem_db_id = await ensure_semantic_database(
        db=db, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(db, sem_db_id)
    metric = await create_metric(db=db, connection_id=sem_db_id, metric_data=_make_def("Doanh thu"), user_id=1)
    await approve_metric(db=db, metric_id=metric.id, user_id=1)
    return metric


@pytest.mark.asyncio
async def test_editing_published_metric_requires_change_reason(async_session: AsyncSession):
    """An approved metric cannot be edited anonymously — the audit trail needs a reason."""
    metric = await _published_metric(async_session)

    with pytest.raises(ValueError, match="change_reason"):
        await update_metric(
            db=async_session,
            metric_id=metric.id,
            metric_data=_make_def("Doanh thu thuần", "net"),
            user_id=1,
        )


@pytest.mark.asyncio
async def test_editing_published_metric_drafts_instead_of_overwriting(async_session: AsyncSession):
    """The live definition keeps serving Flow 2 while the edit waits as a new version."""
    metric = await _published_metric(async_session)
    live_version = metric.version

    returned = await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Doanh thu thuần", "net", change_reason="Đổi sang doanh thu thuần"),
        user_id=1,
    )

    assert returned.status == "approved"
    assert returned.version == live_version
    assert returned.name == "Doanh thu"
    assert returned.definition["metric"]["formula"]["expression"] == "total"

    draft = await latest_open_version(async_session, metric.id)
    assert draft is not None
    assert draft.version == live_version + 1
    assert draft.status in ("pending_approval", "needs_review")
    assert draft.parent_version == live_version
    assert draft.changed_by == 1
    assert draft.definition["metric"]["formula"]["expression"] == "net"
    assert "Đổi sang doanh thu thuần" in draft.change_reason


@pytest.mark.asyncio
async def test_second_edit_supersedes_the_earlier_draft(async_session: AsyncSession):
    """Only one draft stays open; the previous one is superseded, never deleted."""
    metric = await _published_metric(async_session)
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Bản 1", "net", change_reason="Lần 1"),
        user_id=1,
    )
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Bản 2", "net", change_reason="Lần 2"),
        user_id=1,
    )

    versions = await _versions(async_session, metric.id)
    open_rows = [v for v in versions if v.status in ("pending_approval", "needs_review")]
    assert len(open_rows) == 1
    assert open_rows[0].name == "Bản 2"
    assert any(v.status == "superseded" and v.name == "Bản 1" for v in versions)


@pytest.mark.asyncio
async def test_approving_draft_publishes_it_to_the_live_row(async_session: AsyncSession):
    """Approval promotes the draft: the live row adopts the new definition and version."""
    metric = await _published_metric(async_session)
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Doanh thu thuần", "net", change_reason="Đổi công thức"),
        user_id=1,
    )

    approved = await approve_metric(db=async_session, metric_id=metric.id, user_id=2)

    assert approved.status == "approved"
    assert approved.version == 2
    assert approved.definition["metric"]["formula"]["expression"] == "net"
    assert await latest_open_version(async_session, metric.id) is None
    versions = await _versions(async_session, metric.id)
    assert versions[-1].version == 2
    assert versions[-1].status == "approved"
    assert versions[-1].approved_by == 2
    assert versions[-1].approved_at is not None


@pytest.mark.asyncio
async def test_rejecting_draft_keeps_published_definition(async_session: AsyncSession):
    """A rejected draft is retained for audit while the published definition stands."""
    metric = await _published_metric(async_session)
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Doanh thu thuần", "net", change_reason="Đổi công thức"),
        user_id=1,
    )

    rejected = await reject_metric_update(async_session, metric.id, 2, reason="Chưa khớp tài chính")

    assert rejected.status == "rejected"
    assert "Chưa khớp tài chính" in rejected.change_reason
    assert metric.status == "approved"
    assert metric.version == 1
    assert metric.definition["metric"]["formula"]["expression"] == "total"
    assert await latest_open_version(async_session, metric.id) is None


@pytest.mark.asyncio
async def test_rejecting_twice_raises(async_session: AsyncSession):
    """There is nothing left to reject once the draft is closed."""
    metric = await _published_metric(async_session)
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Doanh thu thuần", "net", change_reason="Đổi công thức"),
        user_id=1,
    )
    await reject_metric_update(async_session, metric.id, 2, reason="Không đúng")

    with pytest.raises(ValueError):
        await reject_metric_update(async_session, metric.id, 2, reason="Không đúng")
