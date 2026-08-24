"""Tests for direct orchestrator intent classification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.orchestrator_node import orchestrator_node


def _response(content: str) -> MagicMock:
    """Create a minimal LLM response fixture."""
    result = MagicMock()
    result.content = content
    return result


@pytest.mark.asyncio
async def test_classifies_metric_request_for_direct_generation() -> None:
    """Creating a KPI must not be routed through data assistance."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _response("metric_query")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Tao metric doanh thu theo ngay"})

    assert result["intent"] == "metric_query"


@pytest.mark.asyncio
async def test_classifies_semantic_query_request() -> None:
    """Asking for live metric numbers routes to semantic_query."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _response("semantic_query")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Tổng doanh thu theo khách hàng năm 2024"})

    assert result["intent"] == "semantic_query"


@pytest.mark.asyncio
async def test_classifies_schema_request_for_data_assistant() -> None:
    """Schema exploration remains on the read-only guidance flow."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _response("data_question")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Bang nao chua thong tin khach hang"})

    assert result["intent"] == "data_question"


@pytest.mark.asyncio
async def test_keeps_preclassified_data_intent_without_another_llm_call() -> None:
    """The graph must preserve the route selected before context construction."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        result = await orchestrator_node({"user_message": "Các trường thời gian?", "intent": "data_question"})

    assert result["intent"] == "data_question"
    mock_get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_classifier_response_falls_back_to_data_assistant() -> None:
    """An unknown classifier value cannot invoke a metric generator."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _response("semantic_question")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Bang orders co cot nao"})

    assert result["intent"] == "data_question"


@pytest.mark.asyncio
async def test_classifier_failure_keeps_metric_creation_available() -> None:
    """A failed classifier does not reintroduce the old safe fallback."""
    with patch("src.agents.nodes.orchestrator_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("timeout")
        mock_get_llm.return_value = llm

        result = await orchestrator_node({"user_message": "Tao metric doanh thu"})

    assert result["intent"] == "metric_query"
