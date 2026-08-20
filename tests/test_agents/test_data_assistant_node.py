"""Unit tests for the read-only data assistant node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.data_assistant_node import _format_context, data_assistant_node


@pytest.mark.asyncio
async def test_data_assistant_returns_data_question_response() -> None:
    """The node answers from semantic context without producing metric suggestions."""
    response = MagicMock(content="Bảng customers chứa thông tin khách hàng.")
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = response
        mock_get_llm.return_value = llm

        result = await data_assistant_node(
            {
                "user_message": "Bảng nào chứa thông tin khách hàng?",
                "enriched_schema": {"customers": {"columns": ["id", "name"]}},
                "approved_metrics": [],
            }
        )

    assert result["intent"] == "data_question"
    assert result["chat_response"].startswith("Bảng customers")


@pytest.mark.asyncio
async def test_metric_catalog_question_lists_approved_metrics_without_llm() -> None:
    """Listing approved metrics must not depend on a generative response."""
    state = {
        "user_message": "Có những metric gì trong semantic layer?",
        "approved_metrics": [{"name": "Doanh thu thuần"}, {"name": "Số đơn hoàn thành"}],
    }
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        result = await data_assistant_node(state)

    mock_get_llm.assert_not_called()
    assert "2 metric" in result["chat_response"]
    assert "Doanh thu thuần" in result["chat_response"]


@pytest.mark.asyncio
async def test_unsupported_metric_returns_missing_schema_inputs_without_llm() -> None:
    """Unsupported KPI requests must not be turned into a metric card."""
    state = {
        "user_message": "Đếm khách hàng phát sinh giao dịch",
        "metric_decision": {
            "kind": "missing_metric_unsupported",
            "reason": "Chưa có nguồn giao dịch.",
            "missing_input_codes": ["transaction_table", "customer_link_column"],
        },
    }
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        result = await data_assistant_node(state)

    mock_get_llm.assert_not_called()
    assert "Bảng giao dịch" in result["chat_response"]


@pytest.mark.asyncio
async def test_unsupported_metric_never_renders_foreign_llm_text() -> None:
    """Unsupported-metric guidance must stay Vietnamese when the decision payload is English."""
    state = {
        "user_message": "Đếm khách hàng phát sinh giao dịch",
        "metric_decision": {
            "kind": "missing_metric_unsupported",
            "reason": "The transaction table is absent.",
            "missing_input_codes": ["transaction_table", "customer_link_column"],
        },
    }

    result = await data_assistant_node(state)

    assert "Bảng giao dịch" in result["chat_response"]
    assert "transaction table" not in result["chat_response"]


def test_context_keeps_columns_after_the_legacy_character_limit() -> None:
    """Data guidance must not silently drop late schema columns."""
    columns = [{"column_name": f"field_{index}", "description": "x" * 100} for index in range(160)]
    columns.extend([{"column_name": "is_completed"}, {"column_name": "completed_time"}])

    state = {"enriched_schema": {"tables": [{"table_name": "order_header", "columns": columns}]}}
    context = _format_context(state)

    assert len(context) > 14000
    assert "is_completed" in context
    assert "completed_time" in context
