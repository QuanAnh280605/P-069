"""Unit tests for natural_language_query service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import LiveTargetDbModel
from src.models.schemas import (
    DimensionSelection,
    SemanticQueryFilter,
    SemanticQueryInterpretation,
    SemanticQuerySpec,
    SemanticTimeRange,
)
from src.services.natural_language_query import (
    execute_natural_language_query,
    format_deterministic_explanation,
    normalize_interpretation,
)
from src.services.query_compiler import CompiledQuery
from src.services.query_execution import QueryResult


@pytest.fixture
def catalog_fixture() -> dict:
    return {
        "metrics": [
            {
                "id": 1,
                "name": "revenue",
                "business_name": "Doanh thu",
                "formula": "SUM(amount)",
                "base_entity": "orders",
            },
            {
                "id": 2,
                "name": "order_count",
                "business_name": "Số đơn hàng",
                "formula": "COUNT(order_id)",
                "base_entity": "orders",
            },
            {
                "id": 3,
                "name": "inventory_count",
                "business_name": "Tồn kho",
                "formula": "SUM(stock)",
                "base_entity": "warehouse_stock",
            },
        ],
        "dimensions": [
            {
                "column_id": 10,
                "column_name": "customer_id",
                "business_name": "Khách hàng",
                "table_name": "orders",
                "data_type": "INTEGER",
                "is_time_dimension": False,
            },
            {
                "column_id": 11,
                "column_name": "order_date",
                "business_name": "Ngày đặt",
                "table_name": "orders",
                "data_type": "DATE",
                "is_time_dimension": True,
            },
        ],
        "filter_columns": [
            {
                "column_id": 12,
                "column_name": "status",
                "business_name": "Trạng thái",
                "table_name": "orders",
                "data_type": "VARCHAR",
            }
        ],
    }


def test_normalize_interpretation_merges_time_range(catalog_fixture: dict) -> None:
    """Time ranges are merged into gte and lt runtime filters."""
    interp = SemanticQueryInterpretation(
        status="resolved",
        spec=SemanticQuerySpec(
            metric_ids=[1],
            dimensions=[DimensionSelection(column_id=10)],
            filters=[SemanticQueryFilter(column_id=12, operator="eq", value="completed")],
            limit=100,
        ),
        time_ranges=[
            SemanticTimeRange(
                column_id=11,
                start_date="2024-01-01",
                end_date="2025-01-01",
                label="Năm 2024",
            )
        ],
    )
    normalized = normalize_interpretation(interp, catalog_fixture)
    assert normalized.status == "resolved"
    assert normalized.spec is not None
    assert len(normalized.spec.filters) == 3
    assert normalized.spec.filters[1].operator == "gte"
    assert normalized.spec.filters[1].value == "2024-01-01"
    assert normalized.spec.filters[2].operator == "lt"
    assert normalized.spec.filters[2].value == "2025-01-01"


def test_normalize_interpretation_rejects_incompatible_base_entities(catalog_fixture: dict) -> None:
    """Multi-metrics with different base entities are converted to clarification with options."""
    interp = SemanticQueryInterpretation(
        status="resolved",
        spec=SemanticQuerySpec(
            metric_ids=[1, 3],  # orders vs warehouse_stock
            dimensions=[],
            filters=[],
            limit=100,
        ),
    )
    normalized = normalize_interpretation(interp, catalog_fixture)
    assert normalized.status == "needs_clarification"
    assert normalized.clarification is not None
    assert len(normalized.clarification.options) == 2
    assert "Doanh thu" in normalized.clarification.options[0].label
    assert "Tồn kho" in normalized.clarification.options[1].label


def test_format_deterministic_explanation(catalog_fixture: dict) -> None:
    """Deterministic explanation formats metric name, formula, dimensions, time range."""
    text = format_deterministic_explanation(
        metric_ids=[1],
        dimensions=[DimensionSelection(column_id=11, time_grain="month")],
        filters=[SemanticQueryFilter(column_id=12, operator="eq", value="completed")],
        time_ranges=[
            SemanticTimeRange(
                column_id=11,
                start_date="2024-01-01",
                end_date="2025-01-01",
                label="Năm 2024",
            )
        ],
        catalog=catalog_fixture,
    )
    assert "**Doanh thu**" in text
    assert "`SUM(amount)`" in text
    assert "gom nhóm theo **Ngày đặt** (theo tháng)" in text
    assert "lọc theo **Năm 2024**, **Trạng thái** eq `completed`" in text


@pytest.mark.asyncio
async def test_execute_natural_language_query(catalog_fixture: dict) -> None:
    """Execution calls compiler, executes on live DB, and returns structured result."""
    db_mock = AsyncMock(spec=AsyncSession)
    live_db = LiveTargetDbModel(
        id=1,
        created_by=1,
        display_name="Test DB",
        dialect="sqlite",
        conn_url_enc="enc_url",
    )
    spec = SemanticQuerySpec(metric_ids=[1], dimensions=[DimensionSelection(column_id=10)], filters=[], limit=100)

    compiled = CompiledQuery(
        sql="SELECT customer_id, SUM(amount) AS revenue FROM orders GROUP BY customer_id LIMIT 100",
        parameters={},
        metadata={"base_table": "orders"},
    )
    query_res = QueryResult(columns=["customer_id", "revenue"], rows=[[1, 500000], [2, 300000]], row_count=2)

    with (
        patch("src.services.natural_language_query.SemanticQueryCompiler") as mock_compiler_cls,
        patch("src.services.natural_language_query.decrypt_conn_url", return_value="sqlite:///test.db"),
        patch("src.services.natural_language_query.execute_compiled_query", new_callable=AsyncMock) as mock_exec,
    ):
        mock_compiler = AsyncMock()
        mock_compiler.compile.return_value = compiled
        mock_compiler_cls.return_value = mock_compiler
        mock_exec.return_value = query_res

        result = await execute_natural_language_query(
            db=db_mock,
            db_id=10,
            live_db=live_db,
            spec=spec,
            catalog=catalog_fixture,
        )

    assert result.row_count == 2
    assert result.columns == ["customer_id", "revenue"]
    assert result.rows == [[1, 500000], [2, 300000]]
    assert "**Doanh thu**" in result.explanation
    assert result.sql == compiled.sql
