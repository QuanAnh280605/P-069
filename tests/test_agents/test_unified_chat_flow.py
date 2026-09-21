"""Tests for single-pass unified conversational agent flow and grounded clarification."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.semantic_parse_node import semantic_parse_node


@pytest.fixture
def base_catalog() -> dict:
    """Fixture catalog with approved metric and dimensions."""
    return {
        "metrics": [
            {
                "id": 1,
                "name": "revenue",
                "business_name": "Tổng doanh thu",
                "formula": "SUM(amount)",
                "base_entity": "order_items",
            }
        ],
        "dimensions": [
            {
                "column_id": 101,
                "column_name": "order_date",
                "business_name": "Ngày đặt hàng",
                "table_name": "orders",
                "data_type": "DATE",
                "is_time_dimension": True,
            }
        ],
        "filter_columns": [],
    }


@pytest.mark.asyncio
async def test_single_pass_prevents_false_positive_system_error_report(base_catalog: dict):
    """User reporting system error is classified as chitchat, NOT forced into semantic_query."""
    state = {
        "user_message": "Tôi cần báo cáo lỗi hệ thống xuất file excel",
        "chat_history": [],
        "parser_catalog": base_catalog,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    mock_llm_response = {
        "intent": "chitchat",
        "chat_response": "Cảm ơn bạn đã phản hồi. Chúng tôi đã ghi nhận lỗi xuất Excel và sẽ kiểm tra ngay.",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_llm_response
        out = await semantic_parse_node(state)

    assert out["intent"] == "chitchat"
    assert "Ghi nhận lỗi" in out["chat_response"] or "Cảm ơn" in out["chat_response"]
    assert "interpretation" not in out


@pytest.mark.asyncio
async def test_single_pass_out_of_scope(base_catalog: dict):
    """User asking irrelevant question receives out_of_scope politely."""
    state = {
        "user_message": "Thời tiết hôm nay tại Hà Nội thế nào?",
        "chat_history": [],
        "parser_catalog": base_catalog,
        "can_generate_metrics": False,
        "role": "member",
    }

    mock_llm_response = {
        "intent": "out_of_scope",
        "chat_response": "Tôi chỉ hỗ trợ tra cứu số liệu và Semantic Layer của doanh nghiệp.",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_llm_response
        out = await semantic_parse_node(state)

    assert out["intent"] == "out_of_scope"
    assert "Semantic Layer" in out["chat_response"]


@pytest.mark.asyncio
async def test_single_pass_multi_hop_grounded_clarification(base_catalog: dict):
    """Ambiguous query receives clarification options pre-bound with multi-hop dimension spec."""
    grounded_dims = [
        {
            "column_id": 501,
            "column_name": "city_name",
            "business_name": "Tên thành phố",
            "table_name": "cities",
            "table_business_name": "Thành phố",
            "sample_values": ["Hà Nội", "TP. Hồ Chí Minh"],
            "hop_count": 4,
            "label": "Tên thành phố (bảng cities)",
        },
        {
            "column_id": 502,
            "column_name": "region_name",
            "business_name": "Vùng miền",
            "table_name": "cities",
            "table_business_name": "Thành phố",
            "sample_values": ["Miền Bắc", "Miền Nam"],
            "hop_count": 4,
            "label": "Vùng miền (bảng cities)",
        },
    ]

    state = {
        "user_message": "Tính doanh thu của từng khu vực",
        "chat_history": [],
        "parser_catalog": base_catalog,
        "grounded_candidate_dimensions": grounded_dims,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    mock_llm_response = {
        "intent": "semantic_query",
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Dữ liệu có thể phân tích theo các góc nhìn khu vực sau. Bạn muốn xem theo tiêu chí nào?",
            "options": [],
        },
        "rationale": "Yêu cầu cần làm rõ chiều phân tích khu vực.",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_llm_response
        out = await semantic_parse_node(state)

    assert out["intent"] == "metric_query"
    interp = out["interpretation"]
    assert interp["status"] == "needs_clarification"
    options = interp["clarification"]["options"]
    assert len(options) >= 2

    labels = [opt["label"] for opt in options]
    assert any("thành phố" in lbl.lower() or "khu vực" in lbl.lower() for lbl in labels)


@pytest.mark.asyncio
async def test_single_pass_resolved_query(base_catalog: dict):
    """Direct query in chat is routed to guidance pointing to Metric Explorer."""
    state = {
        "user_message": "Xem tổng doanh thu theo ngày",
        "chat_history": [],
        "parser_catalog": base_catalog,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    mock_llm_response = {
        "intent": "semantic_query",
        "status": "resolved",
        "metric_ids": [1],
        "dimensions": [{"column_id": 101, "time_grain": None}],
        "filters": [],
        "time_ranges": [],
        "limit": 100,
        "rationale": "Xem doanh thu theo ngày",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_llm_response
        out = await semantic_parse_node(state)

    assert out["intent"] == "data_question"
    assert "Metric Explorer" in out["chat_response"]
