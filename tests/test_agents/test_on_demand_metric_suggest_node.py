"""Tests for the definition-only LangGraph metric node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions
from src.services.metrics import extract_schema_summary


def _definition() -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Doanh thu",
                "formula": {"function": "SUM", "expression": "amount"},
                "base_entity": "orders",
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "",
            }
        }
    )


@pytest.mark.asyncio
async def test_empty_state_returns_error() -> None:
    result = await on_demand_metric_suggest_node({})
    assert "error" in result


@pytest.mark.asyncio
async def test_node_returns_definition_without_sql() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    state = {
        "enriched_schema": {
            "tables": [{"table_name": "orders", "columns": [{"column_name": "amount", "data_type": "NUMERIC"}]}]
        }
    }
    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm", return_value=llm):
        result = await on_demand_metric_suggest_node(state)
    item = result["suggested_metrics"][0]
    metric = item["definition"]
    assert metric["metric"]["formula"]["expression"] == "amount"
    assert "sql_template" not in str(item)


def test_schema_prompt_contains_entity_and_column() -> None:
    schema = {"tables": [{"table_name": "orders", "columns": [{"column_name": "amount"}]}]}
    _, text = extract_schema_summary(schema)
    assert "orders" in text
    assert "amount" in text
