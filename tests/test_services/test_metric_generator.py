"""Tests for definition-only metric generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions
from src.services.metrics import generate_metrics_from_prompt, normalize_prompt


def _definition() -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Doanh thu",
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "order_items",
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "Chưa trừ hoàn tiền",
            }
        }
    )


def test_normalize_prompt_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_prompt("   ")


@pytest.mark.asyncio
async def test_generate_definition_and_yaml_without_sql() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {
        "order_items": {
            "columns": [
                {"column_name": "quantity", "data_type": "INTEGER"},
                {"column_name": "unit_price", "data_type": "NUMERIC"},
            ]
        }
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions = await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)
    suggestion = suggestions[0]
    assert suggestion.definition.metric.name == "Doanh thu"
    assert "sql_template" not in suggestion.model_dump_json()
    preview = yaml.safe_load(suggestion.yaml_preview)
    assert preview["metric"]["formula"]["expression"] == "quantity * unit_price"
    assert "filters" not in preview["metric"]


@pytest.mark.asyncio
async def test_generation_rejects_unknown_expression_column() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {"order_items": {"columns": [{"column_name": "quantity"}]}}
    with patch("src.services.metrics.get_llm", return_value=llm):
        with pytest.raises(ValueError, match="valid metric definitions"):
            await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)
