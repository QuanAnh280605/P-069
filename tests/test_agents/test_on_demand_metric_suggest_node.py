"""Tests for the dedupe-aware LangGraph metric node."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions, MetricSuggestionsV2
from src.services.metrics import extract_schema_summary


def _definition(
    name: str = "Doanh thu",
    expression: str = "amount",
    base_entity: str = "orders",
) -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": expression},
                "base_entity": base_entity,
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "",
            }
        }
    )


def _mock_llm(structured_return: Any) -> MagicMock:
    structured = AsyncMock()
    structured.ainvoke.return_value = structured_return
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _schema_with_order_items() -> dict[str, Any]:
    return {
        "tables": [
            {"table_name": "orders", "columns": [{"column_name": "amount", "data_type": "NUMERIC"}]},
            {
                "table_name": "order_items",
                "columns": [
                    {"column_name": "quantity", "data_type": "INT"},
                    {"column_name": "unit_price", "data_type": "NUMERIC"},
                ],
            },
        ]
    }


async def test_empty_state_returns_error() -> None:
    result = await on_demand_metric_suggest_node({})
    assert "error" in result


async def test_node_returns_definition_without_sql() -> None:
    llm = _mock_llm(MetricSuggestions(metrics=[_definition()]))
    state = {
        "enriched_schema": {
            "tables": [{"table_name": "orders", "columns": [{"column_name": "amount", "data_type": "NUMERIC"}]}]
        }
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)
    item = result["suggested_metrics"][0]
    metric = item["definition"]
    assert metric["metric"]["formula"]["expression"] == "amount"
    assert "sql_template" not in str(item)
    assert result["duplicate_notices"] == []
    assert result["dedupe_performed"] is True


async def test_node_emits_notices_when_existing_duplicate() -> None:
    existing = [
        {
            "id": 12,
            "name": "Doanh thu",
            "status": "approved",
            "function": "SUM",
            "expression": "quantity * unit_price",
            "base_entity": "order_items",
            "filters": [],
        }
    ]
    duplicate = _definition(
        name="DOANH  THU",
        expression="quantity * unit_price",
        base_entity="order_items",
    )
    llm = _mock_llm(MetricSuggestionsV2(metrics=[duplicate]))
    state = {"enriched_schema": _schema_with_order_items(), "existing_metrics": existing}
    with patch("src.services.metrics.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)
    llm.with_structured_output.assert_called_once_with(MetricSuggestionsV2)
    assert result["suggested_metrics"] == []
    notices = result["duplicate_notices"]
    assert len(notices) == 1
    assert notices[0]["existing_metric_id"] == 12
    assert result["dedupe_performed"] is True


async def test_node_without_existing_uses_v1() -> None:
    llm = _mock_llm(MetricSuggestions(metrics=[_definition()]))
    state = {"enriched_schema": _schema_with_order_items()}
    with patch("src.services.metrics.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)
    llm.with_structured_output.assert_called_once_with(MetricSuggestions)
    assert result["suggested_metrics"]
    assert result["duplicate_notices"] == []


@pytest.mark.asyncio
async def test_ambiguous_metric_marks_assumptions_low_confidence() -> None:
    """Unspecified business conditions must be visible in the proposal."""
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    state = {
        "enriched_schema": {"tables": [{"table_name": "orders", "columns": [{"column_name": "amount"}]}]},
        "metric_decision": {"kind": "missing_metric_supported", "assumptions": ["Chưa nêu cách xử lý hoàn tiền"]},
    }
    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)

    metric = result["suggested_metrics"][0]["definition"]["metric"]
    assert metric["confidence"] == "low"
    assert "Giả định cần xác nhận" in metric["excluded_notes"]


def test_schema_prompt_contains_entity_and_column() -> None:
    schema = {
        "tables": [
            {
                "table_name": "orders",
                "columns": [
                    {
                        "column_name": "amount",
                        "business_name": "Số tiền",
                        "description": "Tổng tiền đơn hàng",
                    }
                ],
            }
        ]
    }
    _, text = extract_schema_summary(schema)
    assert "orders" in text
    assert "amount" in text
    assert "Số tiền" in text
    assert "Tổng tiền đơn hàng" in text
