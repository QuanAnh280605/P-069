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


@pytest.mark.asyncio
async def test_missing_metric_returns_create_metric_option_for_lead(sample_catalog: dict) -> None:
    """When requested metric is missing and user is Lead/Admin, returns clean prompt and Tạo Business Metric option."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Hệ thống hiện chưa có chỉ số 'Tỷ lệ giữ chân khách hàng (Retention Rate)'. Các chỉ số liên quan hiện có gồm ID 8. Bạn có muốn tạo mới không?",
            "options": [],
        },
        "rationale": "Chưa có chỉ số trong catalog",
    }

    state = {
        "user_message": "Xem tỷ lệ giữ chân khách hàng (Retention Rate) tháng này",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": True,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    # Verify prompt is clean without unrelated metrics listing
    assert "ID 8" not in result["chat_response"]
    assert "Bạn có muốn tôi đề xuất tạo Business Metric mới này không?" in result["chat_response"]
    assert len(result["clarification"]["options"]) == 1
    assert result["clarification"]["options"][0]["id"] == "create_metric"
    assert "Tạo Business Metric" in result["clarification"]["options"][0]["label"]
    assert "Tỷ lệ giữ chân khách hàng" in result["clarification"]["options"][0]["label"]


@pytest.mark.asyncio
async def test_missing_metric_returns_submit_request_option_for_member(sample_catalog: dict) -> None:
    """When requested metric is missing and user is Member, returns prompt for Data Lead proposal."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Hệ thống hiện chưa có chỉ số 'Tỷ lệ giữ chân khách hàng'. Bạn có muốn tạo không?",
            "options": [],
        },
        "rationale": "Chưa có chỉ số trong catalog",
    }

    state = {
        "user_message": "Xem tỷ lệ giữ chân khách hàng",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    assert "Bạn có muốn gửi Data Lead đề xuất chỉ số này không?" in result["chat_response"]
    assert len(result["clarification"]["options"]) == 1
    assert result["clarification"]["options"][0]["id"] == "create_metric"
    assert "Gửi Data Lead đề xuất chỉ số" in result["clarification"]["options"][0]["label"]


@pytest.mark.asyncio
async def test_forced_mismatch_intercepted_and_converted_to_clarification(sample_catalog: dict) -> None:
    """If LLM hallucinates resolved for a different metric (e.g. retention mapped to order count), safety net converts to clarification."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [2],  # order_count / Số lượng đơn hàng
        "dimensions": [],
        "filters": [],
        "time_ranges": [],
    }

    state = {
        "user_message": "Xem tỷ lệ giữ chân khách hàng",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": True,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    assert "tỷ lệ giữ chân khách hàng" in result["chat_response"].lower()
    assert len(result["clarification"]["options"]) == 1
    assert result["clarification"]["options"][0]["id"] == "create_metric"
    assert "tỷ lệ giữ chân khách hàng" in result["clarification"]["options"][0]["label"].lower()


@pytest.mark.asyncio
async def test_invalid_option_spec_is_skipped(sample_catalog: dict) -> None:
    """An option whose spec fails Pydantic validation is dropped, not executed as semantic query."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Bạn muốn xem doanh thu theo tiêu chí nào?",
            "options": [
                {
                    "id": "opt_bad",
                    "label": "Spec không hợp lệ",
                    "spec": {"metric_ids": "not-a-list"},
                }
            ],
        },
        "rationale": "Cần làm rõ",
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
    assert result["clarification"]["options"] == []


@pytest.mark.asyncio
async def test_explicit_grouping_without_matching_dimension_forces_clarification(sample_catalog: dict) -> None:
    """A request that explicitly asks to group 'theo/by/per <dimension>' but resolves with no
    dimension must be forced into clarification, never executed with an empty spec."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [1],
        "dimensions": [],  # LLM silently dropped the requested grouping
        "filters": [],
        "time_ranges": [],
    }

    state = {
        "user_message": "Tổng doanh thu theo vùng miền",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None


@pytest.mark.asyncio
async def test_aggregate_only_request_remains_resolvable_without_dimension(sample_catalog: dict) -> None:
    """Legitimate aggregate-only questions (e.g. total revenue) must still resolve without a dimension."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [1],
        "dimensions": [],
        "filters": [],
        "time_ranges": [],
    }

    state = {
        "user_message": "Tổng doanh thu",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "resolved"
    assert interp["spec"]["metric_ids"] == [1]


@pytest.mark.asyncio
async def test_semantic_mismatch_outside_hardcoded_pairs_forces_clarification(sample_catalog: dict) -> None:
    """If the LLM resolves a concept that shares no distinctive token with the requested metric
    (and is not one of the four hardcoded pairs), conservatively force clarification."""
    llm_payload = {
        "status": "resolved",
        "metric_ids": [2],  # Số lượng đơn hàng
        "dimensions": [],
        "filters": [],
        "time_ranges": [],
    }

    state = {
        "user_message": "Xem tỷ lệ hoàn tiền",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None


@pytest.mark.asyncio
async def test_missing_metric_data_lead_gets_create_option(sample_catalog: dict) -> None:
    """Data Lead (role) gets a create/save Business Metric option for a missing metric."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Hệ thống hiện chưa có chỉ số 'Tỷ lệ hủy đơn'. Bạn có muốn tạo không?",
            "options": [],
        },
        "rationale": "Chưa có chỉ số trong catalog",
    }

    state = {
        "user_message": "Xem tỷ lệ hủy đơn",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    assert "Tạo Business Metric" in result["clarification"]["options"][0]["label"]
    assert result["clarification"]["options"][0]["action"] == "create_metric"


@pytest.mark.asyncio
async def test_missing_metric_member_gets_submit_option(sample_catalog: dict) -> None:
    """Member (role) gets a submit-to-Data-Lead option for a missing metric."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Hệ thống hiện chưa có chỉ số 'Tỷ lệ hủy đơn'. Bạn có muốn tạo không?",
            "options": [],
        },
        "rationale": "Chưa có chỉ số trong catalog",
    }

    state = {
        "user_message": "Xem tỷ lệ hủy đơn",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
        "role": "member",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    assert "Gửi Data Lead đề xuất chỉ số" in result["clarification"]["options"][0]["label"]
    assert result["clarification"]["options"][0]["action"] == "create_metric"


@pytest.mark.asyncio
async def test_missing_metric_admin_gets_guidance_only(sample_catalog: dict) -> None:
    """Admin (role) gets explanatory guidance directing to a Data Lead, with no create/submit action."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Hệ thống hiện chưa có chỉ số 'Tỷ lệ hủy đơn'. Bạn có muốn tạo không?",
            "options": [],
        },
        "rationale": "Chưa có chỉ số trong catalog",
    }

    state = {
        "user_message": "Xem tỷ lệ hủy đơn",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": False,
        "role": "admin",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    # Admin must NOT receive any create/submit action option.
    assert result["clarification"]["options"] == []
    assert "Data Lead" in result["chat_response"]


@pytest.mark.asyncio
async def test_stale_catalog_metric_id_dropped_from_options(sample_catalog: dict) -> None:
    """Clarification options referencing metric IDs absent from the approved catalog are dropped."""
    llm_payload = {
        "status": "needs_clarification",
        "clarification": {
            "prompt": "Bạn muốn xem chỉ số nào?",
            "options": [
                {
                    "id": "opt_stale",
                    "label": "Chỉ số không tồn tại",
                    "spec": {"metric_ids": [9999], "dimensions": [], "filters": [], "limit": 100},
                },
                {
                    "id": "opt_ok",
                    "label": "Doanh thu theo khách hàng",
                    "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
                },
            ],
        },
        "rationale": "Cần làm rõ",
    }

    state = {
        "user_message": "Cho tôi xem số liệu",
        "parser_catalog": sample_catalog,
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = llm_payload
        result = await semantic_parse_node(state)

    interp = result["interpretation"]
    assert interp["status"] == "needs_clarification"
    assert result["clarification"] is not None
    kept = result["clarification"]["options"]
    assert [o["id"] for o in kept] == ["opt_ok"]


@pytest.mark.asyncio
async def test_proactive_clarification_for_repeat_customer_concept(sample_catalog: dict) -> None:
    """When user requests repeat customer rate, node proactively explains schema limits in clarification."""
    state = {
        "user_message": "Tính tỷ lệ khách quay lại",
        "parser_catalog": sample_catalog,
        "can_generate_metrics": True,
        "role": "data_lead",
    }
    result = await semantic_parse_node(state)
    assert result["intent"] == "metric_query"
    assert result["clarification"] is not None
    assert "chưa có dữ liệu lịch sử mua hàng lặp lại" in result["chat_response"].lower()
    options = result["clarification"]["options"]
    assert len(options) >= 2
    assert "Tổng số khách hàng từng đặt đơn" in options[0]["label"]
