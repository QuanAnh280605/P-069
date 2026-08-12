"""Tests for the canonical metric definition contract."""

import pytest
from pydantic import ValidationError

from src.models.metric_definition import MetricDefinition


def _payload(expression: str = "quantity * unit_price") -> dict:
    return {
        "metric": {
            "name": "Doanh thu",
            "formula": {"function": "SUM", "expression": expression},
            "base_entity": "order_items",
            "filters": [{"field": "status", "operator": "eq", "value": "completed"}],
            "status": "pending_approval",
            "confidence": "high",
            "excluded_notes": "Chưa trừ hoàn tiền",
        }
    }


def test_definition_renders_yaml_preview() -> None:
    definition = MetricDefinition.model_validate(_payload())
    assert "name: Doanh thu" in definition.to_yaml()
    assert "function: SUM" in definition.to_yaml()


@pytest.mark.parametrize("expression", ["orders.total", "SUM(total)", "total; DELETE FROM orders"])
def test_definition_rejects_sql_like_expression(expression: str) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(_payload(expression))


def test_definition_rejects_star_for_sum() -> None:
    with pytest.raises(ValidationError, match="only valid with COUNT"):
        MetricDefinition.model_validate(_payload("*"))
