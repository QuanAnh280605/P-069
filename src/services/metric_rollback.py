"""Non-destructive revert of a metric to an earlier approved version.

Reverting never deletes history: the target snapshot is replayed as a brand new
version on top of the current one, so the audit trail keeps every intermediate
edit and the revert itself is attributable.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import MetricVersionModel, SemanticMetricModel
from src.models.metric_definition import MetricDefinition
from src.services.metric_definition_resolver import MetricDefinitionResolver
from src.services.metric_definitions import validate_metric_definition, with_metric_status
from src.services.metric_versioning import (
    VERSION_STATUS_APPROVED,
    next_version_number,
    record_version,
    supersede_open_versions,
)
from src.services.query_compiler import SemanticQueryCompiler


async def rollback_metric(
    db: AsyncSession,
    metric_id: int,
    target_version: int,
    actor_id: int,
    require_ownership: bool = False,
) -> SemanticMetricModel:
    """Revert a metric to *target_version* by appending it as a new approved version.

    Loads the exact target snapshot, resolves and validates it against current
    semantic metadata, appends it as version N+1 owned by *actor_id*, republishes
    the metric row from that snapshot, and verifies deterministic compilation.
    Existing versions are preserved; open drafts are superseded. Flushes only —
    the route owns the commit so any failure rolls the whole operation back.

    Raises ValueError when the metric or target snapshot is missing/invalid,
    ownership is required but absent, or resolution/validation/compilation fails.
    """
    metric = await _load_metric_for_rollback(db, metric_id)
    target = await _load_target_snapshot(db, metric_id, target_version)
    _assert_rollback_access(metric, actor_id, require_ownership)
    _validate_rollback_target(metric, target, target_version)
    payload = await _resolve_target_snapshot(db, metric, target)
    await _append_revert_version(db, metric, payload, target_version, actor_id)
    await SemanticQueryCompiler(db).compile(metric.db_id, metric_ids=[metric.id], dimension_ids=[])
    return metric


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_metric_for_rollback(db: AsyncSession, metric_id: int) -> SemanticMetricModel:
    """Load the current metric row or raise when it does not exist."""
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    metric = (await db.execute(stmt)).scalar_one_or_none()
    if metric is None:
        raise ValueError(f"Metric {metric_id} not found")
    return metric


async def _load_target_snapshot(db: AsyncSession, metric_id: int, target_version: int) -> MetricVersionModel | None:
    """Load the exact historical snapshot for *target_version*, if it exists."""
    stmt = select(MetricVersionModel).where(
        MetricVersionModel.metric_id == metric_id,
        MetricVersionModel.version == target_version,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _assert_rollback_access(metric: SemanticMetricModel, actor_id: int, require_ownership: bool) -> None:
    """Enforce creator ownership when the caller requires it."""
    if require_ownership and metric.created_by != actor_id:
        raise ValueError(f"User {actor_id} does not have ownership of metric {metric.id}")


def _validate_rollback_target(
    metric: SemanticMetricModel,
    target: MetricVersionModel | None,
    target_version: int,
) -> None:
    """Validate range and existence of the rollback target before any mutation."""
    if not 1 <= target_version < metric.version:
        raise ValueError(f"Cannot roll back metric {metric.id} to version {target_version}")
    if target is None:
        raise ValueError(f"Target version {target_version} not found for metric {metric.id}")
    if target.definition is None:
        raise ValueError(f"Legacy version {target_version} has no stored definition to restore")


async def _resolve_target_snapshot(
    db: AsyncSession,
    metric: SemanticMetricModel,
    target: MetricVersionModel,
) -> dict[str, Any]:
    """Resolve and validate the historical definition against current semantic metadata."""
    draft = MetricDefinition.model_validate(target.definition)
    definition = await MetricDefinitionResolver(db).resolve(metric.db_id, draft)
    if definition.diagnostics:
        raise ValueError(f"Version {target.version} cannot be restored: grain diagnostics present")
    definition = with_metric_status(definition, "approved")
    table = await validate_metric_definition(db, metric.db_id, definition)
    payload = definition.model_dump(mode="json")
    payload["_base_entity_id"] = table.id
    return payload


async def _append_revert_version(
    db: AsyncSession,
    metric: SemanticMetricModel,
    payload: dict[str, Any],
    target_version: int,
    actor_id: int,
) -> MetricVersionModel:
    """Append the reverted snapshot as a new approved version and republish it."""
    base_entity_id = payload.pop("_base_entity_id")
    await supersede_open_versions(db, metric.id)
    new_version = await next_version_number(db, metric.id)
    record = await record_version(
        db,
        metric.id,
        payload,
        payload["metric"]["name"],
        VERSION_STATUS_APPROVED,
        actor_id,
        change_reason=f"Hoàn nguyên về version {target_version}",
        parent_version=target_version,
        version=new_version,
    )
    _republish(metric, payload, base_entity_id, new_version, actor_id)
    await db.flush()
    return record


def _republish(
    metric: SemanticMetricModel,
    payload: dict[str, Any],
    base_entity_id: int,
    version: int,
    actor_id: int,
) -> None:
    """Point the live metric row at the reverted definition."""
    metric.name = payload["metric"]["name"]
    metric.description = payload["metric"].get("excluded_notes", "")
    metric.definition = payload
    metric.base_entity_id = base_entity_id
    metric.formula = payload["metric"]["formula"]["expression"]
    metric.aggregation_type = payload["metric"]["formula"]["function"]
    metric.version = version
    metric.status = "approved"
    metric.approved_by = actor_id
