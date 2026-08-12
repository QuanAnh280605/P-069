"""Behavior tests for resolving metric drafts into canonical definitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import SemanticColumnModel, SemanticDatabaseModel, SemanticTableModel
from src.models.metric_definition import MetricDefinition
from src.services.metric_definition_resolver import MetricDefinitionResolver


def _draft() -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Doanh thu",
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "ORDER_ITEMS",
                "filters": [{"field": "status", "operator": "eq", "value": "completed"}],
                "status": "pending_approval",
            }
        }
    )


async def _seed_table(db: AsyncSession, with_primary_key: bool = True) -> tuple[int, SemanticTableModel]:
    semantic_db = SemanticDatabaseModel(
        created_by=1, display_name="Retail", db_type="sqlite", conn_url_enc="encrypted", status="draft"
    )
    db.add(semantic_db)
    await db.flush()
    table = SemanticTableModel(
        db_id=semantic_db.id,
        table_name="order_items",
        business_name="Chi tiết đơn hàng",
        description="",
        primary_key_column="id" if with_primary_key else None,
    )
    db.add(table)
    await db.flush()
    db.add_all(
        [
            SemanticColumnModel(
                table_id=table.id,
                column_name=name,
                data_type=data_type,
                business_name=name,
                is_primary_key=name == "id" and with_primary_key,
            )
            for name, data_type in [
                ("id", "INTEGER"),
                ("quantity", "INTEGER"),
                ("unit_price", "NUMERIC"),
                ("status", "TEXT"),
            ]
        ]
    )
    await db.flush()
    return semantic_db.id, table


@pytest.mark.asyncio
async def test_resolve_records_canonical_ids_expression_and_grain(async_session: AsyncSession) -> None:
    db_id, table = await _seed_table(async_session)

    resolved = await MetricDefinitionResolver(async_session).resolve(db_id, _draft())

    assert resolved.schema_version == 2
    assert resolved.metric.base_entity == "order_items"
    assert resolved.metric.base_entity_id == table.id
    assert len(resolved.metric.grain.column_ids) == 1
    assert resolved.metric.formula.expression_ast.kind == "mul"
    assert {node.column_id for node in resolved.metric.formula.expression_ast.children} == {
        resolved.metric.grain.column_ids[0] + 1,
        resolved.metric.grain.column_ids[0] + 2,
    }
    assert resolved.metric.filters[0].column_id is not None


@pytest.mark.asyncio
async def test_resolve_marks_metric_without_grain_for_review(async_session: AsyncSession) -> None:
    db_id, _ = await _seed_table(async_session, with_primary_key=False)

    resolved = await MetricDefinitionResolver(async_session).resolve(db_id, _draft())

    assert resolved.metric.status == "needs_review"
    assert resolved.metric.grain.column_ids == []
    assert resolved.diagnostics[0].code == "MISSING_GRAIN"
