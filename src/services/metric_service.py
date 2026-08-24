"""Metric lifecycle: create, copy-on-write edit, approval, and rejection.

A published (``approved``) metric is never overwritten in place. Editing one
appends a new ``metric_versions`` row awaiting approval while the live row keeps
serving Flow 2; approval promotes that draft, rejection discards it without
touching the published definition.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import MetricVersionModel, SemanticMetricModel
from src.models.metric_definition import MetricDefinition
from src.services.metric_definition_resolver import MetricDefinitionResolver
from src.services.metric_definitions import validate_metric_definition, with_metric_status
from src.services.metric_versioning import (
    VERSION_STATUS_NEEDS_REVIEW,
    VERSION_STATUS_PENDING,
    latest_open_version,
    load_version,
    mark_version_approved,
    next_version_number,
    record_version,
    reject_version,
    supersede_open_versions,
    version_status_for,
)
from src.services.query_compiler import SemanticQueryCompiler

logger = logging.getLogger(__name__)

METRIC_STATUS_APPROVED = "approved"
METRIC_STATUS_NEEDS_REVIEW = "needs_review"
METRIC_STATUS_PENDING = "pending_approval"
APPROVABLE_METRIC_STATUSES = (METRIC_STATUS_PENDING, METRIC_STATUS_NEEDS_REVIEW, "unverified")


class MetricRequiresReviewError(ValueError):
    """Raised when a metric cannot be approved until its definition diagnostics are resolved."""


class DuplicateMetricError(ValueError):
    """Raised when a metric name already exists within one semantic database."""


async def _ensure_unique_metric_name(db: AsyncSession, db_id: int, name: str) -> None:
    """Reject a duplicate metric name before creating a second catalog record."""
    stmt = select(SemanticMetricModel.name).where(SemanticMetricModel.db_id == db_id)
    existing_names = (await db.execute(stmt)).scalars().all()
    normalized = name.strip().casefold()
    if any(existing.strip().casefold() == normalized for existing in existing_names):
        raise DuplicateMetricError(f'Metric "{name}" already exists in this Semantic Layer')


def _legacy_formula_parts(metric_data: dict[str, Any]) -> tuple[str, str]:
    """Derive (function, expression) from a legacy flat metric payload."""
    agg_type = metric_data.get("aggregation_type", "COUNT")
    formula_raw = metric_data.get("formula")
    if isinstance(formula_raw, dict):
        return formula_raw.get("function", agg_type), formula_raw.get("expression", "*")
    if not isinstance(formula_raw, str):
        return agg_type, "*"
    expr = formula_raw
    if "(" in expr and ")" in expr:
        expr = expr[expr.find("(") + 1 : expr.rfind(")")]
    if "." in expr and expr != "*":
        expr = expr.split(".")[-1]
    return agg_type, expr or "*"


def coerce_metric_definition(metric_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy flat metric payloads into a canonical definition dict."""
    if "definition" in metric_data and isinstance(metric_data["definition"], dict):
        return metric_data["definition"]
    if "metric" in metric_data and isinstance(metric_data["metric"], dict):
        return metric_data

    function, expression = _legacy_formula_parts(metric_data)
    return {
        "metric": {
            "name": metric_data.get("name", "Metric"),
            "formula": {"function": function, "expression": expression},
            "base_entity": metric_data.get("base_entity", "orders"),
            "filters": metric_data.get("filters", []),
            "status": metric_data.get("status", METRIC_STATUS_PENDING),
            "confidence": metric_data.get("confidence", "high"),
            "excluded_notes": metric_data.get("description", ""),
        }
    }


async def require_metric(
    db: AsyncSession,
    metric_id: int,
    user_id: int | None = None,
    require_ownership: bool = False,
) -> SemanticMetricModel:
    """Load a metric by id, optionally enforcing creator ownership."""
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    metric = (await db.execute(stmt)).scalar_one_or_none()
    if metric is None:
        raise ValueError(f"Metric {metric_id} not found")
    if require_ownership and metric.created_by != user_id:
        raise ValueError(f"User {user_id} does not have ownership of metric {metric_id}")
    return metric


async def _resolve_definition(db: AsyncSession, db_id: int, raw: Any) -> tuple[MetricDefinition, str]:
    """Resolve a raw definition payload and derive its lifecycle status."""
    draft = MetricDefinition.model_validate(raw)
    definition = await MetricDefinitionResolver(db).resolve(db_id, draft)
    status = METRIC_STATUS_NEEDS_REVIEW if definition.diagnostics else METRIC_STATUS_PENDING
    return with_metric_status(definition, status), status


async def create_metric(
    db: AsyncSession,
    connection_id: int,
    metric_data: dict[str, Any],
    user_id: int,
    status_override: str | None = None,
) -> SemanticMetricModel:
    """Create a metric and its initial version with a server-controlled status."""
    definition, status = await _resolve_definition(db, connection_id, metric_data["definition"])
    await _ensure_unique_metric_name(db, connection_id, definition.metric.name)
    if status_override:
        status = status_override
        definition = with_metric_status(definition, status)
    table = await validate_metric_definition(db, connection_id, definition)
    payload = definition.model_dump(mode="json")
    metric = SemanticMetricModel(
        db_id=connection_id,
        created_by=user_id,
        name=definition.metric.name,
        description=definition.metric.excluded_notes,
        sql_template="",
        source=metric_data.get("source", "manual"),
        formula="",
        aggregation_type=definition.metric.formula.function,
        definition=payload,
        base_entity_id=table.id,
        version=1,
        status=status,
    )
    db.add(metric)
    await db.flush()
    await record_version(db, metric.id, payload, definition.metric.name, version_status_for(status), user_id, version=1)
    return metric


async def update_metric(
    db: AsyncSession,
    metric_id: int,
    metric_data: dict[str, Any],
    user_id: int,
    require_ownership: bool = True,
) -> SemanticMetricModel:
    """Edit a metric, appending history instead of overwriting it.

    An approved metric is edited copy-on-write: the live row is left untouched and
    the edit waits as a pending version. Unpublished metrics are updated in place,
    still recording every snapshot.
    """
    metric = await require_metric(db, metric_id, user_id, require_ownership)
    definition, status = await _resolve_definition(db, metric.db_id, metric_data["definition"])
    table = await validate_metric_definition(db, metric.db_id, definition)
    payload = definition.model_dump(mode="json")
    reason = (metric_data.get("change_reason") or "").strip()

    if metric.status == METRIC_STATUS_APPROVED:
        await _draft_published_edit(db, metric, payload, definition, status, user_id, reason)
        return metric
    await _edit_in_place(db, metric, payload, definition, table.id, status, user_id, reason)
    return metric


async def _draft_published_edit(
    db: AsyncSession,
    metric: SemanticMetricModel,
    payload: dict[str, Any],
    definition: MetricDefinition,
    status: str,
    user_id: int,
    reason: str,
) -> MetricVersionModel:
    """Park an edit to a published metric as a pending version (copy-on-write)."""
    if not reason:
        raise ValueError("change_reason is required when editing an approved metric")
    await supersede_open_versions(db, metric.id)
    version = await next_version_number(db, metric.id)
    record = await record_version(
        db,
        metric.id,
        payload,
        definition.metric.name,
        status,
        user_id,
        change_reason=reason,
        parent_version=metric.version,
        version=version,
    )
    logger.info(
        "Metric edit parked as draft metric_id=%s live_version=%s draft_version=%s actor=%s",
        metric.id,
        metric.version,
        version,
        user_id,
    )
    return record


async def _edit_in_place(
    db: AsyncSession,
    metric: SemanticMetricModel,
    payload: dict[str, Any],
    definition: MetricDefinition,
    base_entity_id: int,
    status: str,
    user_id: int,
    reason: str,
) -> None:
    """Advance an unpublished metric to a new version, keeping the old snapshot."""
    parent_version = metric.version
    await supersede_open_versions(db, metric.id)
    metric.name = definition.metric.name
    metric.description = definition.metric.excluded_notes
    metric.definition = payload
    metric.base_entity_id = base_entity_id
    metric.aggregation_type = definition.metric.formula.function
    metric.status = status
    metric.approved_by = None
    metric.version = await next_version_number(db, metric.id)
    await record_version(
        db,
        metric.id,
        payload,
        definition.metric.name,
        status,
        user_id,
        change_reason=reason,
        parent_version=parent_version,
        version=metric.version,
    )


async def _ensure_open_draft(
    db: AsyncSession,
    metric: SemanticMetricModel,
    actor_id: int,
) -> MetricVersionModel | None:
    """Return the version awaiting approval, normalizing legacy rows when needed."""
    draft = await latest_open_version(db, metric.id)
    if draft is not None:
        return draft
    if metric.status not in APPROVABLE_METRIC_STATUSES:
        return None
    existing = await load_version(db, metric.id, metric.version)
    if existing is not None:
        existing.status = VERSION_STATUS_PENDING
        existing.definition = existing.definition or metric.definition
        await db.flush()
        return existing
    return await record_version(
        db,
        metric.id,
        metric.definition or {},
        metric.name,
        VERSION_STATUS_PENDING,
        actor_id,
        version=metric.version,
    )


async def _flag_draft_for_review(
    db: AsyncSession,
    metric: SemanticMetricModel,
    draft: MetricVersionModel,
    definition: MetricDefinition,
) -> None:
    """Send a draft back for review; the published definition stays live."""
    payload = definition.model_dump(mode="json")
    draft.status = VERSION_STATUS_NEEDS_REVIEW
    draft.definition = payload
    if metric.version == draft.version:
        metric.status = METRIC_STATUS_NEEDS_REVIEW
        metric.approved_by = None
        metric.definition = payload
    await db.flush()


def _publish_draft(
    metric: SemanticMetricModel,
    draft: MetricVersionModel,
    definition: MetricDefinition,
    base_entity_id: int,
    actor_id: int,
) -> None:
    """Promote an approved draft to be the metric's live published definition."""
    payload = definition.model_dump(mode="json")
    metric.name = definition.metric.name
    metric.description = definition.metric.excluded_notes
    metric.definition = payload
    metric.base_entity_id = base_entity_id
    metric.aggregation_type = definition.metric.formula.function
    metric.version = draft.version
    metric.status = METRIC_STATUS_APPROVED
    metric.approved_by = actor_id
    draft.definition = payload
    draft.name = definition.metric.name
    mark_version_approved(draft, actor_id)


async def approve_metric(
    db: AsyncSession,
    metric_id: int,
    user_id: int,
) -> SemanticMetricModel:
    """Approve the version awaiting review and publish it as the live definition."""
    metric = await require_metric(db, metric_id)
    draft = await _ensure_open_draft(db, metric, user_id)
    if draft is None:
        raise ValueError("Metric is not eligible for approval")
    if not draft.definition:
        raise MetricRequiresReviewError("Legacy metric definition requires review before approval")

    resolved = await MetricDefinitionResolver(db).resolve(
        metric.db_id, MetricDefinition.model_validate(draft.definition)
    )
    if resolved.diagnostics:
        await _flag_draft_for_review(db, metric, draft, resolved)
        raise MetricRequiresReviewError("Metric requires review before approval")

    definition = with_metric_status(resolved, METRIC_STATUS_APPROVED)
    table = await validate_metric_definition(db, metric.db_id, definition)
    _publish_draft(metric, draft, definition, table.id, user_id)
    await supersede_open_versions(db, metric.id, exclude_version=draft.version)
    await db.flush()
    await SemanticQueryCompiler(db).compile(metric.db_id, metric_ids=[metric.id], dimension_ids=[])
    logger.info("Metric published metric_id=%s version=%s actor=%s", metric.id, metric.version, user_id)
    return metric


async def reject_metric_update(
    db: AsyncSession,
    metric_id: int,
    user_id: int,
    reason: str = "",
    version: int | None = None,
) -> MetricVersionModel:
    """Reject a pending edit, leaving the published definition untouched."""
    metric = await require_metric(db, metric_id)
    draft = await load_version(db, metric.id, version) if version is not None else None
    if draft is None:
        draft = await latest_open_version(db, metric.id)
    if draft is None:
        raise ValueError("Metric has no version awaiting approval")
    record = await reject_version(db, metric.id, draft.version, user_id, reason)
    if metric.version == record.version and metric.status != METRIC_STATUS_APPROVED:
        metric.status = METRIC_STATUS_NEEDS_REVIEW
        metric.approved_by = None
        await db.flush()
    return record


async def get_metric_with_history(
    db: AsyncSession,
    metric_id: int,
) -> SemanticMetricModel | None:
    """Retrieve a metric with its version history and actors eagerly loaded."""
    stmt = (
        select(SemanticMetricModel)
        .where(SemanticMetricModel.id == metric_id)
        .options(
            selectinload(SemanticMetricModel.versions).selectinload(MetricVersionModel.changer),
            selectinload(SemanticMetricModel.versions).selectinload(MetricVersionModel.approver),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()
