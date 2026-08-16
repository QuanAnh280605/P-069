"""Query Clarifier Service — Manage Guided Wizard sessions with RAM TTL cleanup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.query_clarifier.nodes.resolve_node import resolve_node
from src.agents.query_clarifier.nodes.wizard_init_node import wizard_init_node
from src.agents.query_clarifier.nodes.wizard_step_node import wizard_step_node
from src.agents.query_clarifier.state import QueryClarifierState, WizardStepOutput
from src.models.db import SemanticColumnModel, SemanticMetricModel, SemanticTableModel
from src.models.schemas import SemanticQuerySpec
from src.services.query_compiler import CompiledQuery, SemanticQueryCompiler

# In-memory session cache with creation timestamp for TTL cleanup
_SESSION_TTL_SECONDS = 900  # 15 minutes
_WIZARD_SESSIONS: dict[str, dict[str, Any]] = {}


def _cleanup_expired_sessions() -> None:
    """Purge wizard sessions older than the TTL limit (15 mins)."""
    now = datetime.now(UTC).timestamp()
    expired_ids = [
        s_id for s_id, s_data in _WIZARD_SESSIONS.items() if now - s_data.get("timestamp", 0) > _SESSION_TTL_SECONDS
    ]
    for s_id in expired_ids:
        _WIZARD_SESSIONS.pop(s_id, None)


def _format_catalog_column(col: SemanticColumnModel) -> dict[str, Any]:
    """Format single semantic column for wizard catalog context."""
    return {
        "column_id": col.id,
        "column_name": col.column_name,
        "business_name": col.business_name or col.column_name,
        "description": col.description or "",
        "data_type": col.data_type,
        "allowed_values": col.allowed_values,
        "is_time_dimension": "date" in col.data_type.lower() or "time" in col.data_type.lower(),
    }


def _format_catalog_table(tbl: SemanticTableModel, columns: list[SemanticColumnModel]) -> dict[str, Any]:
    """Format single semantic table and its columns."""
    return {
        "table_id": tbl.id,
        "table_name": tbl.table_name,
        "business_name": tbl.business_name or tbl.table_name,
        "description": tbl.description or "",
        "columns": [_format_catalog_column(col) for col in columns],
    }


def _format_approved_metric(m: SemanticMetricModel) -> dict[str, Any]:
    """Format single approved metric for wizard context."""
    base_entity = m.definition.get("metric", {}).get("base_entity") if isinstance(m.definition, dict) else None
    return {
        "metric_id": m.id,
        "name": m.name,
        "description": m.description or "",
        "base_entity_id": m.base_entity_id,
        "base_entity": base_entity,
    }


async def _load_catalog_and_metrics(db: AsyncSession, db_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load tables, columns, and approved metrics from metadata store."""
    tables_stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == db_id)
    tables = list((await db.execute(tables_stmt)).scalars().all())

    table_dicts: list[dict[str, Any]] = []
    for tbl in tables:
        cols_stmt = select(SemanticColumnModel).where(SemanticColumnModel.table_id == tbl.id)
        columns = list((await db.execute(cols_stmt)).scalars().all())
        table_dicts.append(_format_catalog_table(tbl, columns))

    metrics_stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.status == "approved",
    )
    approved_metrics = list((await db.execute(metrics_stmt)).scalars().all())
    metric_dicts = [_format_approved_metric(m) for m in approved_metrics]

    return {"tables": table_dicts}, metric_dicts


async def start_wizard_session(db: AsyncSession, db_id: int, user_id: int) -> tuple[str, WizardStepOutput, str | None]:
    """Initialize a new Guided Wizard session for Step 1 (Metric selection)."""
    _cleanup_expired_sessions()
    catalog_context, approved_metrics = await _load_catalog_and_metrics(db, db_id)

    state: QueryClarifierState = {
        "db_id": db_id,
        "user_id": user_id,
        "catalog_context": catalog_context,
        "approved_metrics": approved_metrics,
        "current_step": 1,
        "selected_metric_ids": [],
        "selected_dimension_ids": [],
        "selected_time_grain": None,
        "selected_option_id": None,
        "wizard_step": None,
        "resolved_spec": None,
        "error_message": None,
    }

    result = await wizard_init_node(state)
    state.update(result)

    session_id = str(uuid.uuid4())
    _WIZARD_SESSIONS[session_id] = {
        "state": state,
        "timestamp": datetime.now(UTC).timestamp(),
    }

    return (
        session_id,
        state.get("wizard_step") or WizardStepOutput(step=1, title="", question="", options=[]),
        state.get("error_message"),
    )


async def advance_wizard_session(
    db: AsyncSession, session_id: str, selected_option_id: str
) -> tuple[WizardStepOutput, CompiledQuery | None, SemanticQuerySpec | None, str | None]:
    """Advance wizard session from Step 1 -> Step 2 or Step 2 -> Step 3 (Resolve)."""
    _cleanup_expired_sessions()
    session_data = _WIZARD_SESSIONS.get(session_id)
    if not session_data:
        err_step = WizardStepOutput(step=1, title="Phiên Hết Hạn", question="Phiên tư vấn đã hết hạn.", options=[])
        return err_step, None, None, "Phiên làm việc không tồn tại hoặc đã hết hạn (15 phút)."

    state: QueryClarifierState = session_data["state"]
    state["selected_option_id"] = selected_option_id
    current_step = state.get("current_step", 1)

    if current_step == 1:
        res = await wizard_step_node(state)
        state.update(res)
        session_data["timestamp"] = datetime.now(UTC).timestamp()
        return (
            state.get("wizard_step") or WizardStepOutput(step=2, title="", question="", options=[]),
            None,
            None,
            state.get("error_message"),
        )

    res = await resolve_node(state)
    state.update(res)
    spec = state.get("resolved_spec")
    compiled: CompiledQuery | None = None
    if spec:
        try:
            compiler = SemanticQueryCompiler(db)
            compiled = await compiler.compile(state["db_id"], spec)
        except Exception as exc:
            state["error_message"] = f"Lỗi biên dịch SQL: {exc}"

    _WIZARD_SESSIONS.pop(session_id, None)
    return (
        state.get("wizard_step") or WizardStepOutput(step=3, title="", question="", options=[]),
        compiled,
        spec,
        state.get("error_message"),
    )
