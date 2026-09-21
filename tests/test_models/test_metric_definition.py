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


def test_preferred_join_paths_defaults_to_empty() -> None:
    spec = MetricSpec(
        name="Doanh thu",
        formula={"function": "SUM", "expression": "amount"},
        base_entity="orders",
    )
    assert spec.preferred_join_paths == {}


def test_preferred_join_paths_accepts_valid_map() -> None:
    spec = MetricSpec(
        name="Doanh thu",
        formula={"function": "SUM", "expression": "amount"},
        base_entity="orders",
        preferred_join_paths={2: [10, 11], 3: [12]},
    )
    assert spec.preferred_join_paths == {2: [10, 11], 3: [12]}


def test_preferred_join_paths_rejects_non_positive_target_key() -> None:
    with pytest.raises(ValidationError):
        MetricSpec(
            name="Doanh thu",
            formula={"function": "SUM", "expression": "amount"},
            base_entity="orders",
            preferred_join_paths={0: [1]},
        )


def test_preferred_join_paths_rejects_empty_path() -> None:
    with pytest.raises(ValidationError):
        MetricSpec(
            name="Doanh thu",
            formula={"function": "SUM", "expression": "amount"},
            base_entity="orders",
            preferred_join_paths={2: []},
        )


def test_preferred_join_paths_rejects_duplicate_relationship_id() -> None:
    with pytest.raises(ValidationError):
        MetricSpec(
            name="Doanh thu",
            formula={"function": "SUM", "expression": "amount"},
            base_entity="orders",
            preferred_join_paths={2: [10, 10]},
        )


def test_preferred_join_paths_rejects_non_positive_relationship_id() -> None:
    with pytest.raises(ValidationError):
        MetricSpec(
            name="Doanh thu",
            formula={"function": "SUM", "expression": "amount"},
            base_entity="orders",
            preferred_join_paths={2: [-1]},
        )


def test_yaml_omits_empty_preferred_join_paths() -> None:
    definition = MetricDefinition.model_validate(_payload())
    assert "preferred_join_paths" not in definition.to_yaml()


def test_yaml_includes_non_empty_preferred_join_paths() -> None:
    payload = _payload()
    payload["metric"]["preferred_join_paths"] = {2: [10, 11]}
    definition = MetricDefinition.model_validate(payload)
    assert "preferred_join_paths" in definition.to_yaml()
    assert "10" in definition.to_yaml()
