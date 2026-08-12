"""Validation and persistence projections for canonical metric definitions."""

from __future__ import annotations

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from src.models.db import SemanticColumnModel, SemanticTableModel
from src.models.metric_definition import MetricDefinition, MetricStatus

_NUMERIC_TYPES = ("INT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "MONEY")


async def validate_metric_definition(
    db: AsyncSession,
    db_id: int,
    definition: MetricDefinition,
) -> SemanticTableModel:
    """Validate entity and fields against persisted semantic metadata."""
    table = await _load_base_entity(db, db_id, definition.metric.base_entity)
    columns = await _load_columns(db, table.id)
    column_map = {column.column_name: column for column in columns}
    _validate_expression_columns(definition, column_map)
    _validate_filter_columns(definition, column_map)
    return table


def with_metric_status(definition: MetricDefinition, status: MetricStatus) -> MetricDefinition:
    """Return a copied definition with the authoritative lifecycle status."""
    return definition.model_copy(update={"metric": definition.metric.model_copy(update={"status": status})})


async def _load_base_entity(db: AsyncSession, db_id: int, base_entity: str) -> SemanticTableModel:
    stmt = select(SemanticTableModel).where(
        SemanticTableModel.db_id == db_id,
        SemanticTableModel.table_name == base_entity,
    )
    table = (await db.execute(stmt)).scalar_one_or_none()
    if table is None:
        raise ValueError(f"Unknown base_entity: {base_entity}")
    return table


async def _load_columns(db: AsyncSession, table_id: int) -> list[SemanticColumnModel]:
    result = await db.execute(select(SemanticColumnModel).where(SemanticColumnModel.table_id == table_id))
    return list(result.scalars().all())


def _validate_expression_columns(
    definition: MetricDefinition,
    columns: dict[str, SemanticColumnModel],
) -> None:
    formula = definition.metric.formula
    if formula.expression == "*":
        return
    parsed = sqlglot.parse_one(formula.expression)
    names = {column.name for column in parsed.find_all(exp.Column)}
    missing = names - columns.keys()
    if missing:
        raise ValueError(f"Unknown expression columns: {sorted(missing)}")
    if formula.function in {"SUM", "AVG"}:
        invalid = [name for name in names if not _is_numeric(columns[name].data_type)]
        if invalid:
            raise ValueError(f"{formula.function} requires numeric columns: {invalid}")


def _validate_filter_columns(
    definition: MetricDefinition,
    columns: dict[str, SemanticColumnModel],
) -> None:
    missing = {item.field for item in definition.metric.filters} - columns.keys()
    if missing:
        raise ValueError(f"Unknown filter columns: {sorted(missing)}")


def _is_numeric(data_type: str) -> bool:
    return any(token in data_type.upper() for token in _NUMERIC_TYPES)
