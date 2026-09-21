"""Tests verifying the 2-turn clarify-then-create workflow for 5 hard golden dataset metrics.

Covers:
1. gross_margin (Biên lợi nhuận gộp)
2. average_order_value (Giá trị đơn hàng trung bình - AOV)
3. order_cancellation_rate (Tỷ lệ hủy đơn hàng)
4. loyalty_order_penetration (Tỷ lệ thâm nhập đơn hàng thành viên thân thiết)
5. returned_order_rate (Tỷ lệ đơn hàng bị hoàn trả)

For each metric:
- Turn 1: AI must NOT create the metric immediately; must return clarification with proposed dimensions.
- Turn 2: Upon clarification, AI produces valid MetricDefinition with dimensions auto-attached.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.chat_graph import _route_after_parse
from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.agents.nodes.semantic_parse_node import semantic_parse_node
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions


@pytest.fixture
def ecommerce_schema() -> dict[str, Any]:
    """Rich ecommerce schema matching golden dataset conventions."""
    return {
        "tables": [
            {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER", "business_name": "Mã đơn hàng"},
                    {"column_name": "order_date", "data_type": "DATE", "business_name": "Ngày đặt hàng"},
                    {"column_name": "channel", "data_type": "VARCHAR", "business_name": "Kênh bán hàng"},
                    {"column_name": "status", "data_type": "VARCHAR", "business_name": "Trạng thái đơn"},
                    {"column_name": "store_id", "data_type": "INTEGER", "business_name": "Mã cửa hàng"},
                    {"column_name": "customer_id", "data_type": "INTEGER", "business_name": "Mã khách hàng"},
                    {"column_name": "total_amount", "data_type": "DECIMAL", "business_name": "Tổng tiền"},
                    {"column_name": "discount_amount", "data_type": "DECIMAL", "business_name": "Tiền chiết khấu"},
                    {"column_name": "net_revenue", "data_type": "DECIMAL", "business_name": "Doanh thu thuần"},
                    {"column_name": "is_test_order", "data_type": "BOOLEAN", "business_name": "Đơn thử nghiệm"},
                    {"column_name": "is_canceled", "data_type": "BOOLEAN", "business_name": "Đơn bị hủy"},
                    {"column_name": "is_returned", "data_type": "BOOLEAN", "business_name": "Đơn hoàn trả"},
                ],
            },
            {
                "table_name": "order_items",
                "business_name": "Chi tiết đơn hàng",
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER", "business_name": "Mã chi tiết"},
                    {"column_name": "order_id", "data_type": "INTEGER", "business_name": "Mã đơn hàng"},
                    {"column_name": "product_id", "data_type": "INTEGER", "business_name": "Mã sản phẩm"},
                    {"column_name": "quantity", "data_type": "INTEGER", "business_name": "Số lượng"},
                    {"column_name": "unit_price", "data_type": "DECIMAL", "business_name": "Đơn giá"},
                    {"column_name": "cost_price", "data_type": "DECIMAL", "business_name": "Giá vốn"},
                    {"column_name": "net_revenue", "data_type": "DECIMAL", "business_name": "Doanh thu thuần dòng"},
                ],
            },
            {
                "table_name": "customers",
                "business_name": "Khách hàng",
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER", "business_name": "Mã khách hàng"},
                    {"column_name": "customer_tier", "data_type": "VARCHAR", "business_name": "Hạng thành viên"},
                    {"column_name": "city_name", "data_type": "VARCHAR", "business_name": "Tỉnh / Thành phố"},
                    {"column_name": "region_name", "data_type": "VARCHAR", "business_name": "Khu vực / Miền"},
                ],
            },
            {
                "table_name": "order_returns",
                "business_name": "Đơn hoàn trả",
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER", "business_name": "Mã hoàn trả"},
                    {"column_name": "order_id", "data_type": "INTEGER", "business_name": "Mã đơn hàng"},
                    {"column_name": "return_reason", "data_type": "VARCHAR", "business_name": "Lý do hoàn trả"},
                    {"column_name": "return_amount", "data_type": "DECIMAL", "business_name": "Số tiền hoàn"},
                ],
            },
        ]
    }


@pytest.fixture
def candidate_dimensions() -> list[dict[str, Any]]:
    """Grounded candidate dimensions for ecommerce."""
    return [
        {"column_id": 101, "column_name": "channel", "business_name": "Kênh bán hàng", "table_name": "orders"},
        {"column_id": 102, "column_name": "city_name", "business_name": "Tỉnh / Thành phố", "table_name": "customers"},
        {"column_id": 103, "column_name": "region_name", "business_name": "Khu vực", "table_name": "customers"},
        {"column_id": 104, "column_name": "order_date", "business_name": "Ngày đặt hàng", "table_name": "orders"},
        {
            "column_id": 105,
            "column_name": "customer_tier",
            "business_name": "Hạng thành viên",
            "table_name": "customers",
        },
        {
            "column_id": 106,
            "column_name": "return_reason",
            "business_name": "Lý do hoàn trả",
            "table_name": "order_returns",
        },
    ]


HARD_METRICS_TEST_CASES = [
    (
        "gross_margin",
        "Tôi muốn tính biên lợi nhuận gộp",
        ["channel", "city_name"],
        "Biên lợi nhuận gộp",
        "orders",
    ),
    (
        "average_order_value",
        "Tạo metric tính giá trị đơn hàng trung bình AOV",
        ["channel", "city_name"],
        "Giá trị đơn hàng trung bình",
        "orders",
    ),
    (
        "order_cancellation_rate",
        "Tôi muốn tính tỷ lệ hủy đơn hàng",
        ["channel", "order_date"],
        "Tỷ lệ hủy đơn hàng",
        "orders",
    ),
    (
        "loyalty_order_penetration",
        "Tính tỷ lệ đơn hàng thành viên thân thiết",
        ["customer_tier", "city_name"],
        "Tỷ lệ thành viên thân thiết",
        "orders",
    ),
    (
        "returned_order_rate",
        "Tính tỷ lệ đơn hàng bị hoàn trả",
        ["return_reason", "channel"],
        "Tỷ lệ hoàn trả",
        "orders",
    ),
]


@pytest.mark.parametrize(
    ("metric_slug", "user_prompt", "target_dimensions", "metric_name", "base_table"),
    HARD_METRICS_TEST_CASES,
)
@pytest.mark.asyncio
async def test_hard_metric_clarify_and_creation_flow(
    metric_slug: str,
    user_prompt: str,
    target_dimensions: list[str],
    metric_name: str,
    base_table: str,
    ecommerce_schema: dict[str, Any],
    candidate_dimensions: list[dict[str, Any]],
):
    """Test full 2-turn flow for 5 hard golden dataset metrics."""
    # =========================================================================
    # TURN 1: User requests metric creation -> AI MUST CLARIFY (no instant creation)
    # =========================================================================
    turn1_state = {
        "user_message": user_prompt,
        "chat_history": [],
        "enriched_schema": ecommerce_schema,
        "parser_catalog": {"metrics": [], "dimensions": []},
        "grounded_candidate_dimensions": candidate_dimensions,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    mock_clarify_response = {
        "prompt": f"Để tạo chỉ số '{metric_name}' chuẩn xác cho doanh nghiệp, bạn vui lòng làm rõ cách tính và chiều phân tích:",
        "options": [
            {
                "id": "opt_1",
                "label": f"Chỉ tính đơn hợp lệ · Gắn chiều {target_dimensions[0]} & {target_dimensions[1]}",
                "description": f"Loại trừ đơn hủy/test, tự động gắn các chiều: {', '.join(target_dimensions)}",
                "dimensions": target_dimensions,
            },
            {
                "id": "opt_2",
                "label": "Tính trên toàn bộ đơn hàng · Gắn chiều Kênh bán & Thời gian",
                "description": "Tính trên toàn bộ bản ghi",
                "dimensions": ["channel", "order_date"],
            },
        ],
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_clarify_response
        turn1_output = await semantic_parse_node(turn1_state)

    # 1. Must recognize metric_query intent
    assert turn1_output["intent"] == "metric_query"
    # 2. Must return clarification payload
    assert "clarification" in turn1_output
    clarification = turn1_output["clarification"]
    assert "prompt" in clarification
    assert len(clarification["options"]) >= 2
    assert clarification["options"][0]["dimensions"] == target_dimensions
    # 3. Interpretation status must be needs_clarification
    assert turn1_output["interpretation"]["status"] == "needs_clarification"
    # 4. Graph router must return "done", stopping at END without creating metric immediately!
    next_node = _route_after_parse(turn1_output)
    assert next_node == "done"

    # =========================================================================
    # TURN 2: User confirms clarification option -> AI GENERATES METRIC WITH DIMENSIONS
    # =========================================================================
    turn2_state = {
        "user_message": f"Tạo metric dựa trên lựa chọn đã làm rõ: Chỉ tính đơn hợp lệ với các chiều phân tích: {', '.join(target_dimensions)}",
        "chat_history": [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": clarification["prompt"]},
        ],
        "enriched_schema": ecommerce_schema,
        "parser_catalog": {"metrics": [], "dimensions": []},
        "grounded_candidate_dimensions": candidate_dimensions,
        "clarified_dimensions": target_dimensions,
        "is_clarified": True,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    # Verify semantic parse recognizes confirmed clarification and routes to metric_suggest
    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_p2:
        mock_p2.return_value = {"intent": "metric_query"}
        turn2_parse_out = await semantic_parse_node(turn2_state)
    assert turn2_parse_out["intent"] == "metric_query"
    assert turn2_parse_out.get("clarification") is None
    assert _route_after_parse(turn2_parse_out) == "metric_suggest"

    # Mock LLM generation of MetricDefinition
    mock_metric_json = {
        "metrics": [
            {
                "schema_version": 2,
                "metric": {
                    "name": metric_slug,
                    "base_entity": base_table,
                    "formula": {"function": "SUM", "expression": "net_revenue"},
                    "filters": [{"field": "is_test_order", "operator": "eq", "value": False}],
                    "dimensions": target_dimensions,
                    "status": "pending_approval",
                    "confidence": "high",
                    "excluded_notes": "Đã làm rõ nghiệp vụ theo phản hồi người dùng.",
                },
            }
        ]
    }

    with patch(
        "src.agents.nodes.on_demand_metric_suggest_node.invoke_metric_structured", new_callable=AsyncMock
    ) as mock_gen_llm:
        mock_gen_llm.return_value = MetricSuggestions.model_validate(mock_metric_json)
        suggest_out = await on_demand_metric_suggest_node(turn2_state)

    # 1. Output intent must be metric_query
    assert suggest_out["intent"] == "metric_query"
    # 2. Suggested metrics must contain 1 item
    suggested = suggest_out.get("suggested_metrics")
    assert suggested is not None and len(suggested) == 1

    item = suggested[0]
    definition_dict = item["definition"]
    definition = MetricDefinition.model_validate(definition_dict)

    # 3. Verify MetricDefinition has correct base entity
    assert definition.metric.base_entity == base_table
    # 4. CRITICAL: Verify dimensions field is automatically attached and equals clarified dimensions!
    assert definition.metric.dimensions == target_dimensions
    # 5. Verify YAML preview contains dimensions
    yaml_preview = item["yaml_preview"]
    assert "dimensions:" in yaml_preview
    for d in target_dimensions:
        assert d in yaml_preview
