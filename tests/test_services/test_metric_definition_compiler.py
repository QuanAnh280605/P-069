"""Compiler tests using canonical JSON definitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.services.query_compiler import SemanticQueryCompiler


async def _seed(db: AsyncSession) -> tuple[int, int, int]:
    semantic_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Retail",
        db_type="sqlite",
        conn_url_enc="encrypted",
        status="draft",
    )
    db.add(semantic_db)
    await db.flush()
    table = SemanticTableModel(
        db_id=semantic_db.id,
        table_name="order_items",
        business_name="Chi tiết đơn hàng",
        description="",
    )
    db.add(table)
    await db.flush()
    columns = [
        SemanticColumnModel(table_id=table.id, column_name=name, data_type=data_type, business_name=name)
        for name, data_type in [("quantity", "INTEGER"), ("unit_price", "NUMERIC"), ("status", "TEXT")]
    ]
    db.add_all(columns)
    await db.flush()
    definition = {
        "metric": {
            "name": "Doanh thu",
            "formula": {"function": "SUM", "expression": "quantity * unit_price"},
            "base_entity": "order_items",
            "filters": [{"field": "status", "operator": "eq", "value": "completed"}],
            "status": "approved",
            "confidence": "high",
            "excluded_notes": "",
        }
    }
    metric = SemanticMetricModel(
        db_id=semantic_db.id,
        created_by=1,
        name="Doanh thu",
        description="",
        sql_template="",
        source="ai",
        status="approved",
        base_entity_id=table.id,
        formula="",
        aggregation_type="SUM",
        definition=definition,
    )
    db.add(metric)
    await db.commit()
    return semantic_db.id, metric.id, columns[2].id


@pytest.mark.asyncio
async def test_compile_definition_to_parameterized_sql(async_session: AsyncSession) -> None:
    db_id, metric_id, dimension_id = await _seed(async_session)
    result = await SemanticQueryCompiler(async_session).compile(db_id, [metric_id], [dimension_id])
    assert 'SUM("order_items"."quantity" * "order_items"."unit_price")' in result.sql
    assert 'GROUP BY "order_items"."status"' in result.sql
    assert result.parameters == {"metric_0": "completed"}
    assert "LIMIT 100" in result.sql


@pytest.mark.asyncio
async def test_compiler_rejects_legacy_metric_without_definition(async_session: AsyncSession) -> None:
    db_id, metric_id, _ = await _seed(async_session)
    metric = await async_session.get(SemanticMetricModel, metric_id)
    metric.definition = None
    await async_session.commit()
    with pytest.raises(ValueError, match="approved definition"):
        await SemanticQueryCompiler(async_session).compile(db_id, [metric_id], [])
