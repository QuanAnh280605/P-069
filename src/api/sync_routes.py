"""API routes for schema auto-sync, fast drift checks, self-healing, and audit logs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_current_user
from src.models.db import (
    LiveTargetDbModel,
    SchemaSyncLogModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.schemas import (
    SchemaSyncLogResponse,
    SchemaSyncStatusResponse,
    SchemaSyncTriggerResponse,
)
from src.services.database import decrypt_conn_url, get_db_session
from src.services.live_db_service import introspect_live_database
from src.services.schema_cron_service import run_daily_schema_sync_job
from src.services.schema_fingerprint import fast_introspect_schema_fingerprint
from src.services.schema_self_healing_service import detect_drift_details, execute_self_healing

logger = logging.getLogger(__name__)

sync_router = APIRouter(dependencies=[Depends(get_current_user)])


async def _resolve_semantic_db(db: AsyncSession, db_id: int, user_id: int, org_id: int | None) -> SemanticDatabaseModel:
    """Verify ownership or organization membership for a semantic database."""
    stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_id)
    if org_id is None:
        stmt = stmt.where(SemanticDatabaseModel.created_by == user_id)
    else:
        stmt = stmt.where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (SemanticDatabaseModel.created_by == user_id))
        )
    sem_db = (await db.execute(stmt)).scalar_one_or_none()
    if not sem_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semantic database not found")
    return sem_db


def _filter_log_healed_metrics(log: SchemaSyncLogModel, active_ids: set[int]) -> SchemaSyncLogResponse:
    """Filter healed_metrics in a sync log to exclude deleted or inactive metrics."""
    data = SchemaSyncLogResponse.model_validate(log).model_dump()
    if data.get("changes_summary") and isinstance(data["changes_summary"], dict):
        if "healed_metrics" in data["changes_summary"]:
            filtered = [hm for hm in data["changes_summary"]["healed_metrics"] if hm.get("metric_id") in active_ids]
            data["changes_summary"]["healed_metrics"] = filtered
    return SchemaSyncLogResponse.model_validate(data)


@sync_router.get("/semantic/{db_id}/sync-status", response_model=SchemaSyncStatusResponse)
async def get_sync_status(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SchemaSyncStatusResponse:
    """Fast hash check for schema drift status with optional preview."""
    sem_db = await _resolve_semantic_db(db, db_id, current_user.id, org_id)

    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    live_db = (await db.execute(live_stmt)).scalar_one_or_none()

    in_sync = True
    drift_preview = None
    if live_db:
        try:
            conn_url = decrypt_conn_url(live_db.conn_url_enc)
            current_fp = await asyncio.to_thread(fast_introspect_schema_fingerprint, conn_url, live_db.dialect)
            in_sync = current_fp == sem_db.schema_fingerprint
            if not in_sync:
                raw_schema = await asyncio.to_thread(introspect_live_database, conn_url, live_db.dialect)
                tbl_stmt = (
                    select(SemanticTableModel)
                    .where(SemanticTableModel.db_id == db_id)
                    .options(selectinload(SemanticTableModel.columns))
                )
                existing_tables = (await db.execute(tbl_stmt)).scalars().all()
                drift_preview = detect_drift_details(existing_tables, raw_schema)
        except Exception as exc:
            logger.warning("Fast fingerprint check failed for DB ID=%d: %s", db_id, exc)

    active_metric_ids = set(
        (
            await db.execute(
                select(SemanticMetricModel.id).where(
                    SemanticMetricModel.db_id == db_id,
                    SemanticMetricModel.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )

    log_stmt = (
        select(SchemaSyncLogModel)
        .where(SchemaSyncLogModel.semantic_db_id == db_id)
        .order_by(SchemaSyncLogModel.created_at.desc())
        .limit(1)
    )
    latest_log = (await db.execute(log_stmt)).scalar_one_or_none()
    latest_log_resp = _filter_log_healed_metrics(latest_log, active_metric_ids) if latest_log else None

    return SchemaSyncStatusResponse(
        semantic_db_id=db_id,
        in_sync=in_sync,
        fingerprint=sem_db.schema_fingerprint,
        last_synced_at=sem_db.last_synced_at,
        sync_status=sem_db.sync_status,
        latest_log=latest_log_resp,
        drift_preview=drift_preview,
    )


@sync_router.post("/semantic/{db_id}/sync", response_model=SchemaSyncTriggerResponse)
async def trigger_sync(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SchemaSyncTriggerResponse:
    """Trigger on-demand schema sync and self-healing for a database."""
    await _resolve_semantic_db(db, db_id, current_user.id, org_id)
    try:
        log = await execute_self_healing(db, db_id, trigger_type="manual")
        log_resp = SchemaSyncLogResponse.model_validate(log)
        msg = f"Đồng bộ thành công (Trạng thái: {log.status})."
        return SchemaSyncTriggerResponse(status=log.status, log=log_resp, message=msg)
    except Exception as exc:
        logger.exception("Manual schema sync failed for db_id=%d", db_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@sync_router.get("/semantic/{db_id}/sync-logs", response_model=list[SchemaSyncLogResponse])
async def list_sync_logs(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[SchemaSyncLogResponse]:
    """Retrieve audit history of schema sync runs and self-healing operations."""
    await _resolve_semantic_db(db, db_id, current_user.id, org_id)

    active_metric_ids = set(
        (
            await db.execute(
                select(SemanticMetricModel.id).where(
                    SemanticMetricModel.db_id == db_id,
                    SemanticMetricModel.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )

    stmt = (
        select(SchemaSyncLogModel)
        .where(SchemaSyncLogModel.semantic_db_id == db_id)
        .order_by(SchemaSyncLogModel.created_at.desc())
        .limit(50)
    )
    logs = (await db.execute(stmt)).scalars().all()
    return [_filter_log_healed_metrics(item, active_metric_ids) for item in logs]


@sync_router.post("/admin/sync-all")
async def trigger_admin_sync_all(
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin endpoint to run daily schema sync immediately across all databases."""
    result = await run_daily_schema_sync_job()
    return {"message": "Admin auto-sync completed", "result": result}
