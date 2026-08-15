"""API router for Guided Wizard AI Query Assistant endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.db import LiveTargetDbModel, SemanticDatabaseModel, UserModel
from src.models.schemas import SemanticQuerySpec
from src.services.database import get_db_session
from src.services.query_clarifier_service import (
    advance_wizard_session,
    start_wizard_session,
)


class WizardStartResponse(BaseModel):
    """Response payload for wizard start request."""

    session_id: str
    step: int
    title: str
    question: str
    options: list[dict[str, Any]]
    is_completed: bool


class WizardStepRequest(BaseModel):
    """Request payload for wizard step selection."""

    session_id: str = Field(..., min_length=1)
    option_id: str = Field(..., min_length=1)


class WizardStepResponse(BaseModel):
    """Response payload for advancing a wizard step."""

    step: int
    title: str
    question: str
    options: list[dict[str, Any]]
    is_completed: bool
    resolved_spec: SemanticQuerySpec | None = None
    sql_preview: str | None = None


query_clarify_router = APIRouter(tags=["AI Query Assistant Wizard"])


async def _verify_live_db(db: AsyncSession, db_id: int, user_id: int) -> SemanticDatabaseModel:
    """Verify that semantic database exists and is backed by a Live Target DB."""
    stmt = select(SemanticDatabaseModel).where(
        SemanticDatabaseModel.id == db_id,
        SemanticDatabaseModel.created_by == user_id,
    )
    semantic_db = (await db.execute(stmt)).scalar_one_or_none()
    if not semantic_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database không tồn tại hoặc không thuộc quyền sở hữu.",
        )

    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    live_db = (await db.execute(live_stmt)).scalar_one_or_none()
    if not live_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI Assistant chỉ hỗ trợ kết nối Live DB. SQL Dump không hỗ trợ truy vấn.",
        )

    return semantic_db


@query_clarify_router.post(
    "/semantic/{db_id}/query/wizard/start",
    response_model=WizardStartResponse,
)
@query_clarify_router.post(
    "/semantic/{db_id}/query/clarify",
    response_model=WizardStartResponse,
)
async def start_wizard(
    db_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WizardStartResponse:
    """Start the Guided Wizard flow for a Live DB connection."""
    await _verify_live_db(db, db_id, current_user.id)
    session_id, wizard_step, error = await start_wizard_session(db, db_id, current_user.id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return WizardStartResponse(
        session_id=session_id,
        step=wizard_step.step,
        title=wizard_step.title,
        question=wizard_step.question,
        options=[opt.model_dump() for opt in wizard_step.options],
        is_completed=wizard_step.is_completed,
    )


@query_clarify_router.post(
    "/semantic/{db_id}/query/wizard/step",
    response_model=WizardStepResponse,
)
async def advance_wizard(
    db_id: int,
    body: WizardStepRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WizardStepResponse:
    """Submit selected radio option and advance wizard to next step or preview."""
    await _verify_live_db(db, db_id, current_user.id)
    wizard_step, compiled, spec, error = await advance_wizard_session(db, body.session_id, body.option_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    sql_preview = compiled.sql if compiled else None
    return WizardStepResponse(
        step=wizard_step.step,
        title=wizard_step.title,
        question=wizard_step.question,
        options=[opt.model_dump() for opt in wizard_step.options],
        is_completed=wizard_step.is_completed,
        resolved_spec=spec,
        sql_preview=sql_preview,
    )
