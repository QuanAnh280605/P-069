"""Singleton dashboard layout API for workspace-scoped semantic databases."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.db import UserModel
from src.models.schemas import DashboardLayoutResponse, DashboardSaveRequest
from src.services.dashboard_service import (
    DashboardAuthorizationError,
    DashboardNotFoundError,
    DashboardValidationError,
    DashboardVersionConflictError,
    get_dashboard_layout,
    save_dashboard_layout,
)
from src.services.database import get_db_session

router = APIRouter(
    prefix="/semantic/{db_id}/dashboard",
    tags=["Visual Dashboard"],
    dependencies=[Depends(get_current_user)],
)


def _raise_conflict(error: DashboardVersionConflictError) -> NoReturn:
    """Translate a stale expected_version into a machine-readable 409 payload.

    Stable frontend contract: detail is ``{"code": "dashboard_version_conflict",
    "current_version": <int>}``; the lowercase code must not be renamed.
    """
    raise HTTPException(
        status_code=409,
        detail={"code": "dashboard_version_conflict", "current_version": error.current_version},
    ) from error


def _raise_service_error(error: Exception) -> NoReturn:
    """Map dashboard service errors onto deterministic HTTP failures."""
    if isinstance(error, DashboardNotFoundError):
        raise HTTPException(status_code=404, detail="Semantic database not found") from error
    if isinstance(error, DashboardAuthorizationError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, DashboardValidationError):
        raise HTTPException(
            status_code=422,
            detail={"code": "dashboard_invalid_layout", "message": str(error)},
        ) from error
    raise error


@router.get("", response_model=DashboardLayoutResponse)
async def read_dashboard_layout(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardLayoutResponse:
    """Return the singleton dashboard layout, or an empty version-0 state before first save."""
    try:
        return await get_dashboard_layout(db, current_user.id, db_id, org_id=org_id)
    except (DashboardNotFoundError, DashboardAuthorizationError) as error:
        _raise_service_error(error)


@router.put("", response_model=DashboardLayoutResponse)
async def upsert_dashboard_layout(
    db_id: int,
    request: DashboardSaveRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardLayoutResponse:
    """Create or update the singleton layout guarded by optimistic concurrency."""
    try:
        return await save_dashboard_layout(db, current_user.id, db_id, request, org_id=org_id)
    except DashboardVersionConflictError as error:
        _raise_conflict(error)
    except (DashboardNotFoundError, DashboardAuthorizationError, DashboardValidationError) as error:
        _raise_service_error(error)
