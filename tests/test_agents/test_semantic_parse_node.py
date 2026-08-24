"""Unit tests for semantic_parse_node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.semantic_parse_node import semantic_parse_node


@pytest.fixture
def sample_catalog() -> dict:
    return {
        "metrics": [
            {
                "id": 1,
                "name": "total_revenue",
                "business_name": "Tổng doanh thu",
                "formula": "SUM(amount)",
                "base_entity": "orders",
            },
            {
                "id": 2,
                "name": "order_count",
                "business_name": "Số lượng đơn hàng",
                "formula": "COUNT(id)",
                "base_entity": "orders",
            },
        ],
        "dimensions": [
            {
                "column_id": 10,
                "column_name": "customer_id",
                "business_name": "Mã khách hàng",
                "table_name": "orders",
                "data_type": "INTEGER",
                "is_time_dimension": False,
            },
            {
                "column_id": 11,
                "column_name": "created_at",
                "business_name": "Ngày tạo đơn",
                "table_name": "orders",
                "data_type": "TIMESTAMP",
                "is_time_dimension": True,
            },
        ],
        "filter_columns": [
            {
                "column_id": 12,
                "column_name": "status",
                "business_name": "Trạng thái đơn",
                "table_name": "orders",
                "data_type": "VARCHAR",
            }
        ],
    }


@pytest.mark.asyncio
async def test_empty_catalog_returns_needs_clarification() -> None:
    """When catalog has no metrics, node immediately returns clarification without calling LLM."""
    state = {
        "user_message": "Tổng doanh thu 2024",
        "parser_catalog": {"metrics": []},
    }
    with patch("src.agents.nodes.semantic_parse_node.get_llm") as mock_get_llm:
        result = await semantic_parse_node(state)
        mock_get_llm.assert_not_called()

    assert result["intent"] == "semantic_query"
    assert result["interpretation"]["status"] == "needs_clarification"
    assert "chưa có business metric" in result["chat_response"].lower()


@pytest.mark.asyncio
async def test_resolved_query_mapping(sample_catalog: dict) -> None:
    """Valid LLM JSON is mapped to resolved SemanticQueryInterpretation with spec and time range."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [1],
        "dimensions": [{"column_id": 10, "time_grain": None}],
        "filters": [{"column_id": 12, "operator": "eq", "value": "completed"}],
        "time_ranges": [
            {
                "column_id": 11,
                "start_date": "2024-01-01",
                "end_date": "2025-01-01",
                "label": "Năm 2024",
            }
        ],
        "limit": 100,
        "rationale": "Tính doanh thu theo khách hàng cho đơn hàng hoàn tất trong năm 2024.",
    }

    state = {
        "user_message": "Tổng doanh thu theo khách hàng năm 2024",
        "parser_catalog": sample_catalog,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "resolved"
    assert interp["spec"]["metric_ids"] == [1]
    assert interp["spec"]["dimensions"][0]["column_id"] == 10
    assert interp["spec"]["filters"][0]["column_id"] == 12
    assert len(interp["time_ranges"]) == 1
    assert interp["time_ranges"][0]["start_date"] == "2024-01-01"


@pytest.mark.asyncio
async def test_unknown_metric_id_falls_back_to_clarification(sample_catalog: dict) -> None:
    """If LLM hallucinates an unknown metric_id not in catalog, node falls back to clarification."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [9999],  # unknown ID
        "dimensions": [],
        "filters": [],
        "time_ranges": [],
    }

    state = {
        "user_message": "Tổng chi phí",
        "parser_catalog": sample_catalog,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"


@pytest.mark.asyncio
async def test_needs_clarification_with_options(sample_catalog: dict) -> None:
    """When LLM returns ambiguous clarification, options with specs are preserved."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Bạn muốn xem doanh thu theo tiêu chí nào?",
            "options": [
                {
                    "id": "opt_cust",
                    "label": "Doanh thu theo khách hàng",
                    "description": "Nhóm theo mã khách hàng",
                    "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
                },
                {
                    "id": "opt_date",
                    "label": "Doanh thu theo ngày",
                    "description": "Nhóm theo ngày tạo",
                    "spec": {
                        "metric_ids": [1],
                        "dimensions": [{"column_id": 11, "time_grain": "day"}],
                        "filters": [],
                        "limit": 100,
                    },
                },
            ],
        },
        "rationale": "Câu hỏi chưa rõ chiều phân tích",
    }

    state = {
        "user_message": "Cho tôi xem doanh thu",
        "parser_catalog": sample_catalog,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    assert len(result["clarification"]["options"]) == 2
    assert result["clarification"]["options"][0]["id"] == "opt_cust"


@pytest.mark.asyncio
async def test_llm_exception_falls_back_gracefully(sample_catalog: dict) -> None:
    """When ainvoke_json raises an exception, node gracefully returns needs_clarification."""
    state = {
        "user_message": "Doanh thu",
        "parser_catalog": sample_catalog,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.side_effect = RuntimeError("LLM connection timeout")
        result = await semantic_parse_node(state)

    assert result["interpretation"]["status"] == "needs_clarification"
    assert "chưa hiểu rõ" in result["chat_response"]
