"""Resolve metric drafts against canonical semantic metadata."""

from __future__ import annotations

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from src.models.db import SemanticColumnModel
from src.models.metric_definition import (
    MetricDefinition,
    MetricDiagnostic,
    MetricExpressionNode,
    MetricGrain,
)
from src.services.metric_definitions import validate_metric_definition

_BINARY_KINDS: dict[type[exp.Expression], str] = {
    exp.Add: "add",
    exp.Sub: "sub",
    exp.Mul: "mul",
    exp.Div: "div",
}


class MetricDefinitionResolver:
    """Turn an untrusted metric draft into a canonical versioned definition."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve(self, db_id: int, draft: MetricDefinition) -> MetricDefinition:
        """Resolve canonical identities, expression nodes, filters, and grain."""
        definition = draft.model_copy(deep=True)
        table = await validate_metric_definition(self._db, db_id, definition)
        columns = await _load_columns(self._db, table.id)
        by_name = {column.column_name.lower(): column for column in columns}
        formula = definition.metric.formula.model_copy(
            update={"expression_ast": _expression_tree(definition.metric.formula.expression, by_name)}
        )
        filters = [
            item.model_copy(
                update={"field": by_name[item.field.lower()].column_name, "column_id": by_name[item.field.lower()].id}
            )
            for item in definition.metric.filters
        ]
        grain = MetricGrain(column_ids=_primary_key_ids(table.primary_key_column, columns))
        diagnostics = _grain_diagnostics(grain)
        status = "needs_review" if diagnostics else definition.metric.status
        metric = definition.metric.model_copy(
            update={
                "formula": formula,
                "filters": filters,
                "base_entity": table.table_name,
                "base_entity_id": table.id,
                "grain": grain,
                "status": status,
            }
        )
        return MetricDefinition(schema_version=2, metric=metric, diagnostics=diagnostics)


async def _load_columns(db: AsyncSession, table_id: int) -> list[SemanticColumnModel]:
    result = await db.execute(select(SemanticColumnModel).where(SemanticColumnModel.table_id == table_id))
    return list(result.scalars().all())


def _primary_key_ids(primary_key: str | None, columns: list[SemanticColumnModel]) -> list[int]:
    flagged = [column.id for column in columns if column.is_primary_key]
    if flagged:
        return flagged
    target = (primary_key or "").lower()
    return [column.id for column in columns if column.column_name.lower() == target]


def _grain_diagnostics(grain: MetricGrain) -> list[MetricDiagnostic]:
    if grain.column_ids:
        return []
    return [MetricDiagnostic(code="MISSING_GRAIN", message="Base entity has no canonical primary-key grain")]


def _expression_tree(
    expression: str,
    columns: dict[str, SemanticColumnModel],
) -> MetricExpressionNode:
    if expression == "*":
        return MetricExpressionNode(kind="literal", value=1)
    return _node(sqlglot.parse_one(expression), columns)


def _node(node: exp.Expression, columns: dict[str, SemanticColumnModel]) -> MetricExpressionNode:
    if isinstance(node, exp.Column):
        return MetricExpressionNode(kind="column", column_id=columns[node.name.lower()].id)
    if isinstance(node, exp.Literal):
        return MetricExpressionNode(kind="literal", value=float(node.this))
    if isinstance(node, exp.Paren):
        return _node(node.this, columns)
    if isinstance(node, exp.Neg):
        return MetricExpressionNode(kind="neg", children=[_node(node.this, columns)])
    for node_type, kind in _BINARY_KINDS.items():
        if isinstance(node, node_type):
            children = [_node(node.this, columns), _node(node.expression, columns)]
            return MetricExpressionNode(kind=kind, children=children)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")
