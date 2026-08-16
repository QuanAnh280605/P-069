"""Unit tests for Guided Wizard Agent nodes."""

from __future__ import annotations

import pytest

from src.agents.query_clarifier.nodes.resolve_node import resolve_node
from src.agents.query_clarifier.nodes.wizard_init_node import wizard_init_node
from src.agents.query_clarifier.nodes.wizard_step_node import wizard_step_node
from src.agents.query_clarifier.state import QueryClarifierState


@pytest.mark.asyncio
async def test_wizard_init_node_empty_metrics():
    """Test wizard_init_node when no approved metrics exist."""
    state: QueryClarifierState = {
        "db_id": 1,
        "user_id": 1,
        "catalog_context": {},
        "approved_metrics": [],
    }
    result = await wizard_init_node(state)
    assert result["error_message"] is not None
    assert result["current_step"] == 1


@pytest.mark.asyncio
async def test_wizard_init_node_with_metrics():
    """Test wizard_init_node generating metric radio options."""
    state: QueryClarifierState = {
        "db_id": 1,
        "user_id": 1,
        "catalog_context": {},
        "approved_metrics": [
            {"metric_id": 10, "name": "Doanh Thu Thuần", "description": "Net Revenue"},
            {"metric_id": 20, "name": "Tổng Đơn Hàng", "description": "Total Orders"},
        ],
    }
    result = await wizard_init_node(state)
    assert result["error_message"] is None
    step = result["wizard_step"]
    assert step.step == 1
    assert len(step.options) == 2
    assert step.options[0].id == "metric:10"
    assert step.options[0].label == "Doanh Thu Thuần"


@pytest.mark.asyncio
async def test_wizard_step_node_dimension_chips():
    """Test wizard_step_node generating smart dimension options."""
    state: QueryClarifierState = {
        "db_id": 1,
        "user_id": 1,
        "selected_option_id": "metric:10",
        "selected_metric_ids": [],
        "catalog_context": {
            "tables": [
                {
                    "table_id": 1,
                    "table_name": "orders",
                    "business_name": "Đơn hàng",
                    "columns": [
                        {
                            "column_id": 101,
                            "column_name": "order_date",
                            "business_name": "Ngày đặt",
                            "data_type": "TIMESTAMP",
                            "is_time_dimension": True,
                        },
                        {
                            "column_id": 102,
                            "column_name": "region",
                            "business_name": "Vùng miền",
                            "data_type": "VARCHAR",
                            "is_time_dimension": False,
                        },
                    ],
                }
            ]
        },
        "approved_metrics": [{"metric_id": 10, "name": "Doanh Thu Thuần"}],
    }
    result = await wizard_step_node(state)
    assert result["error_message"] is None
    assert result["selected_metric_ids"] == [10]
    step = result["wizard_step"]
    assert step.step == 2
    assert len(step.options) >= 2
    assert step.options[0].id == "dim:none"


@pytest.mark.asyncio
async def test_resolve_node_canonical_spec():
    """Test resolve_node producing a valid SemanticQuerySpec."""
    state: QueryClarifierState = {
        "db_id": 1,
        "selected_metric_ids": [10],
        "selected_option_id": "dim:101:month",
    }
    result = await resolve_node(state)
    assert result["error_message"] is None
    spec = result["resolved_spec"]
    assert spec is not None
    assert spec.metric_ids == [10]
    assert len(spec.dimensions) == 1
    assert spec.dimensions[0].column_id == 101
    assert spec.dimensions[0].time_grain == "month"
