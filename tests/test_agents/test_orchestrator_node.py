"""Unit tests for orchestrator_node — intent classification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.orchestrator_node import orchestrator_node


def _mock_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response with the given content."""
    resp = MagicMock()
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifies_greeting_as_chitchat() -> None:
    """'Xin chào' should be classified as chitchat."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("chitchat")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "xin chào"})

    assert result["intent"] == "chitchat"


@pytest.mark.asyncio
async def test_classifies_general_question_as_chitchat() -> None:
    """General system question should be classified as chitchat."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("chitchat")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "hệ thống này làm gì?"})

    assert result["intent"] == "chitchat"


@pytest.mark.asyncio
async def test_classifies_revenue_query_as_metric() -> None:
    """Revenue question should be classified as metric_query."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("metric_query")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "tổng doanh thu tháng này bao nhiêu?"})

    assert result["intent"] == "metric_query"


@pytest.mark.asyncio
async def test_classifies_suggest_metric_as_metric() -> None:
    """'Đề xuất metric' should be classified as metric_query."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("metric_query")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "đề xuất metric cho bảng orders"})

    assert result["intent"] == "metric_query"


@pytest.mark.asyncio
async def test_classifies_schema_question_as_data_question() -> None:
    """Schema and approved-metric questions use the read-only assistant."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("data_question")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Bảng nào chứa thông tin khách hàng?"})

    assert result["intent"] == "data_question"


@pytest.mark.asyncio
async def test_classifies_kpi_question_as_metric() -> None:
    """KPI / chỉ số câu hỏi should be classified as metric_query."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("metric_query")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "chỉ số nào quan trọng nhất?"})

    assert result["intent"] == "metric_query"


@pytest.mark.asyncio
async def test_classifies_weather_question_as_out_of_scope() -> None:
    """Unrelated weather question should be classified as out_of_scope with rejection message."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("out_of_scope")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "thời tiết Hà Nội hôm nay thế nào?"})

    assert result["intent"] == "out_of_scope"
    assert "chat_response" in result
    assert "Semantic Layer" in result["chat_response"]


@pytest.mark.asyncio
async def test_classifies_recipe_question_as_out_of_scope() -> None:
    """Unrelated recipe/cooking question should return out_of_scope."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _mock_llm_response("out_of_scope")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "hướng dẫn nấu phở bò"})

    assert result["intent"] == "out_of_scope"
    assert "chat_response" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_message_returns_chitchat_without_llm() -> None:
    """Empty user_message should return chitchat without calling LLM."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        result = await orchestrator_node({"user_message": ""})
        mock_get_llm.assert_not_called()

    assert result["intent"] == "chitchat"
    assert "chat_response" in result


@pytest.mark.asyncio
async def test_llm_exception_falls_back_to_chitchat() -> None:
    """LLM exception should silently fall back to chitchat intent."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("LLM timeout")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "test message"})

    assert result["intent"] == "chitchat"


@pytest.mark.asyncio
async def test_missing_user_message_key_returns_chitchat() -> None:
    """State without user_message key should return chitchat."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        result = await orchestrator_node({})
        mock_get_llm.assert_not_called()

    assert result["intent"] == "chitchat"
