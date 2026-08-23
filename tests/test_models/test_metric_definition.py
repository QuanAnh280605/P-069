"""Tests for the canonical metric definition contract."""

import pytest
from pydantic import ValidationError

from src.models.metric_definition import MetricDefinition, MetricSpec


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


@pytest.mark.parametrize("status", ["draft", "pending_approval", "approved", "needs_review", "unverified"])
def test_definition_accepts_valid_statuses(status: str) -> None:
    """MetricSpec accepts all currently valid lifecycle statuses including unverified."""
    payload = _payload()
    payload["metric"]["status"] = status
    definition = MetricDefinition.model_validate(payload)
    assert definition.metric.status == status


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("draft", "draft"),
        ("  Approved  ", "approved"),
        ("NEEDS_REVIEW", "needs_review"),
        ("Unverified", "unverified"),
        ("WEIRD", "pending_approval"),
        ("bogus", "pending_approval"),
        (123, "pending_approval"),
        (None, "pending_approval"),
    ],
)
def test_definition_coerces_status(raw_status: object, expected: str) -> None:
    """Status values are normalized; unknown or non-string values fall back to pending_approval."""
    payload = _payload()
    payload["metric"]["status"] = raw_status
    definition = MetricDefinition.model_validate(payload)
    assert definition.metric.status == expected


def test_metric_spec_coerces_weird_status_to_pending_approval() -> None:
    """MetricSpec(status="WEIRD") validates to "pending_approval" instead of raising."""
    spec = MetricSpec(
        name="Đơn nháp",
        formula={"function": "COUNT", "expression": "*"},
        base_entity="orders",
        status="WEIRD",
    )
    assert spec.status == "pending_approval"
