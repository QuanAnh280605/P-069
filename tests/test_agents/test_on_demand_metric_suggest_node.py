"""Tests for the dedupe-aware LangGraph metric node."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.on_demand_metric_suggest_node import (
    _populate_dimensions,
    on_demand_metric_suggest_node,
)
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions
from src.services.metrics import MetricGenerationTimeoutError, extract_schema_summary


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
    llm.bind.return_value = llm
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


async def test_node_returns_fast_retry_message_on_metric_timeout() -> None:
    """A bounded Metric timeout becomes a persisted-friendly chat response."""
    state = {
        "user_message": "Tạo metric doanh thu",
        "enriched_schema": {"tables": [{"table_name": "orders", "columns": [{"column_name": "amount"}]}]},
    }
    with patch(
        "src.agents.nodes.on_demand_metric_suggest_node.invoke_metric_structured",
        side_effect=MetricGenerationTimeoutError("slow"),
    ):
        result = await on_demand_metric_suggest_node(state)

    assert result["suggested_metrics"] == []
    assert "45 giây" in result["chat_response"]
    assert "thử lại" in result["chat_response"].lower()


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
    llm = _mock_llm(MetricSuggestions(metrics=[duplicate]))
    state = {"enriched_schema": _schema_with_order_items(), "existing_metrics": existing}
    with patch("src.services.metrics.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)
    llm.with_structured_output.assert_called_once_with(MetricSuggestions, strict=True, include_raw=True)
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
    llm.with_structured_output.assert_called_once_with(MetricSuggestions, strict=True, include_raw=True)
    assert result["suggested_metrics"]
    assert result["duplicate_notices"] == []


@pytest.mark.asyncio
async def test_ambiguous_metric_marks_assumptions_low_confidence() -> None:
    """Unspecified business conditions must be visible in the proposal."""
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.with_structured_output.return_value = structured
    state = {
        "enriched_schema": {"tables": [{"table_name": "orders", "columns": [{"column_name": "amount"}]}]},
        "metric_decision": {"kind": "missing_metric_supported", "assumptions": ["Chưa nêu cách xử lý hoàn tiền"]},
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
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


@pytest.mark.asyncio
async def test_non_numeric_avg_metric_is_rejected_with_friendly_response() -> None:
    """Proposals with AVG over TIMESTAMP columns must be rejected and explained."""
    invalid_delivery_metric = MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Thời gian giao hàng trung bình",
                "formula": {"function": "AVG", "expression": "delivered_time - created_time"},
                "base_entity": "orders",
                "filters": [],
                "status": "pending_approval",
            }
        }
    )
    llm = _mock_llm(MetricSuggestions(metrics=[invalid_delivery_metric]))
    state = {
        "user_message": "Thời gian giao hàng trung bình",
        "enriched_schema": {
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"column_name": "created_time", "data_type": "TIMESTAMP"},
                        {"column_name": "delivered_time", "data_type": "TIMESTAMP"},
                    ],
                }
            ]
        },
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)

    assert result["suggested_metrics"] == []
    assert "không phải số" in result["chat_response"]
    assert "cột số đo thời lượng" in result["chat_response"]


def test_foreign_key_dimensions_are_mapped_to_related_display_names() -> None:
    """Technical FK dimensions become safe, human-readable related columns."""
    definition = _definition()
    definition.metric.dimensions = ["city_id", "store_code"]
    candidates = [
        {
            "column_id": 200,
            "column_name": "region_name",
            "business_name": "Tên vùng",
            "table_name": "cities",
            "table_business_name": "Thành phố",
            "hop_count": 1,
        },
        {
            "column_id": 201,
            "column_name": "city_name",
            "business_name": "Tên thành phố",
            "table_name": "cities",
            "table_business_name": "Thành phố",
            "hop_count": 1,
        },
        {
            "column_id": 202,
            "column_name": "name",
            "business_name": "Tên cửa hàng",
            "table_name": "stores",
            "table_business_name": "Cửa hàng",
            "hop_count": 1,
        },
    ]

    _populate_dimensions(definition, candidates, clarified_dims=None)

    assert definition.metric.dimensions == ["cities.city_name", "stores.name"]


def test_foreign_key_dimension_is_not_mapped_to_an_unrelated_name() -> None:
    """An unknown key stays explicit instead of being mapped by display-name rank alone."""
    definition = _definition()
    definition.metric.dimensions = ["warehouse_id"]
    candidates = [
        {
            "column_id": 203,
            "column_name": "name",
            "business_name": "Tên cửa hàng",
            "table_name": "stores",
            "hop_count": 1,
        }
    ]

    _populate_dimensions(definition, candidates, clarified_dims=None)

    assert definition.metric.dimensions == ["warehouse_id"]


def _canceled_rate_definition(function: str, expression: str, filters: list[Any] | None = None) -> MetricDefinition:
    """Helper creating test metric definition for order cancellation."""
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Tỷ lệ hủy đơn",
                "formula": {"function": function, "expression": expression},
                "base_entity": "orders",
                "filters": filters or [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "",
            }
        }
    )


async def test_node_self_corrects_invalid_formula_expression_types() -> None:
    """When LLM returns AVG on VARCHAR column, repair loop kicks in and validates fixed metric."""
    invalid_def = _canceled_rate_definition("AVG", "is_canceled")
    filter_spec = [{"column": "is_canceled", "operator": "=", "value": "1"}]
    valid_def = _canceled_rate_definition("COUNT", "order_id", filter_spec)
    state = {
        "user_message": "Tính tỷ lệ hủy đơn",
        "enriched_schema": {
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"column_name": "order_id", "data_type": "INT"},
                        {"column_name": "is_canceled", "data_type": "VARCHAR(1)"},
                    ],
                }
            ]
        },
    }
    mock_gen = AsyncMock(side_effect=[[invalid_def], [valid_def]])
    with patch("src.agents.nodes.on_demand_metric_suggest_node._generate_definitions", mock_gen):
        result = await on_demand_metric_suggest_node(state)

    assert mock_gen.call_count == 2
    assert len(result["suggested_metrics"]) == 1
    metric = result["suggested_metrics"][0]["definition"]["metric"]
    assert metric["formula"]["function"] == "COUNT"
    assert metric["formula"]["expression"] == "order_id"
