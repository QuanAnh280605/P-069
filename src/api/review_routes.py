"""HITL review endpoints: schema approval gate and metric version decisions.

Kept in its own router so the Flow 1 review gate stays readable and
``src/api/routes.py`` does not grow further.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.routes import _require_resource_permission
from src.models.db import SemanticMetricModel, UserModel
from src.models.review_schemas import (
    MetricVersionDecisionRequest,
    ReviewTableItem,
    SchemaApproveRequest,
    SchemaApproveResponse,
    SchemaReviewResponse,
)
from src.models.schemas import MetricVersionResponse
from src.services.database import get_db_session
from src.services.metric_service import reject_metric_update
from src.services.metric_versioning import latest_open_version
from src.services.schema_review_service import (
    SchemaRowNotFoundError,
    approve_schema,
    load_review_tables,
    pending_review_counts,
)

logger = logging.getLogger(__name__)

review_router = APIRouter(tags=["HITL Review"])


@review_router.get("/semantic/{db_id}/schema/review", response_model=SchemaReviewResponse)
async def get_schema_review(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SchemaReviewResponse:
    """Hàng đợi review: tên nghiệp vụ bảng/cột do AI đề xuất, chờ BA/DA duyệt."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_schema")
    tables = await load_review_tables(db, db_id)
    counts = await pending_review_counts(db, db_id)
    pending = counts["pending_tables"] or counts["pending_columns"]
    return SchemaReviewResponse(
        db_id=db_id,
        status="pending_review" if pending else "approved",
        pending_tables=counts["pending_tables"],
        pending_columns=counts["pending_columns"],
        tables=[ReviewTableItem.model_validate(table) for table in tables],
    )


@review_router.post("/semantic/{db_id}/schema/approve", response_model=SchemaApproveResponse)
async def approve_schema_review(
    db_id: int,
    body: SchemaApproveRequest | None = None,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SchemaApproveResponse:
    """Duyệt metadata đã review và lưu chính thức vào Metadata Store."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")
    table_names = body.table_names if body else None
    try:
        result = await approve_schema(db, db_id, current_user.id, table_names)
    except SchemaRowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    pending = result["pending_tables"] or result["pending_columns"]
    return SchemaApproveResponse(
        db_id=db_id,
        approved_tables=result["approved_tables"],
        approved_columns=result["approved_columns"],
        pending_tables=result["pending_tables"],
        pending_columns=result["pending_columns"],
        status="pending_review" if pending else "approved",
    )


async def _scoped_metric(db: AsyncSession, db_id: int, metric_id: int) -> SemanticMetricModel:
    """Load a metric that must belong to *db_id*."""
    metric = await db.get(SemanticMetricModel, metric_id)
    if metric is None or metric.db_id != db_id:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")
    return metric


@review_router.get("/semantic/{db_id}/metric/{metric_id}/pending-version", response_model=MetricVersionResponse)
async def get_pending_metric_version(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricVersionResponse:
    """Bản sửa đang chờ duyệt của một chỉ số đã publish (copy-on-write draft)."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_metrics")
    await _scoped_metric(db, db_id, metric_id)
    draft = await latest_open_version(db, metric_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Metric has no version awaiting approval")
    return MetricVersionResponse.model_validate(draft, from_attributes=True)


@review_router.post("/semantic/{db_id}/metric/{metric_id}/reject", response_model=MetricVersionResponse)
async def reject_metric_version(
    db_id: int,
    metric_id: int,
    body: MetricVersionDecisionRequest | None = None,
    version: int | None = Query(default=None, description="Bản cần từ chối; bỏ trống để lấy bản đang chờ duyệt"),
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricVersionResponse:
    """Từ chối bản sửa đang chờ duyệt; definition đang publish giữ nguyên."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")
    await _scoped_metric(db, db_id, metric_id)
    try:
        record = await reject_metric_update(
            db, metric_id, current_user.id, reason=body.reason if body else "", version=version
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return MetricVersionResponse.model_validate(record, from_attributes=True)
