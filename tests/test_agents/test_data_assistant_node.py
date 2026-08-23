"""Unit tests for the read-only data assistant node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.data_assistant_node import data_assistant_node


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
async def test_data_assistant_includes_chat_history_in_llm_messages() -> None:
    """The node must include prior chat_history turns in LLM messages array."""
    response = MagicMock(content="Cột total có kiểu NUMERIC.")
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = response
        mock_get_llm.return_value = llm

        history = [
            {"role": "user", "content": "Bảng orders có những cột nào?"},
            {"role": "assistant", "content": "Bảng orders có cột id, user_id, total."},
        ]

        result = await data_assistant_node(
            {
                "user_message": "Cột total kiểu gì?",
                "chat_history": history,
                "enriched_schema": {"orders": {"columns": ["id", "user_id", "total"]}},
                "approved_metrics": [],
            }
        )

        assert result["intent"] == "data_question"
        assert result["chat_response"] == "Cột total có kiểu NUMERIC."
        llm.ainvoke.assert_awaited_once()
        invoked_messages = llm.ainvoke.call_args[0][0]
        # Verify history is passed between system messages and current user message
        roles = [m["role"] for m in invoked_messages]
        assert roles == ["system", "system", "user", "assistant", "user"]
        assert invoked_messages[2]["content"] == "Bảng orders có những cột nào?"
        assert invoked_messages[3]["content"] == "Bảng orders có cột id, user_id, total."
        assert invoked_messages[4]["content"] == "Cột total kiểu gì?"


@pytest.mark.asyncio
async def test_data_assistant_empty_message_returns_prompt() -> None:
    """Empty user_message returns quick guidance without calling LLM."""
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        result = await data_assistant_node({"user_message": ""})
        mock_get_llm.assert_not_called()

    assert result["intent"] == "data_question"
    assert "Bạn muốn tìm hiểu phần dữ liệu nào?" in result["chat_response"]


@pytest.mark.asyncio
async def test_data_assistant_handles_llm_exception() -> None:
    """LLM exception is caught safely and returns error response."""
    with patch("src.agents.nodes.data_assistant_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("LLM failure")
        mock_get_llm.return_value = llm

        result = await data_assistant_node(
            {
                "user_message": "test query",
                "enriched_schema": {},
                "approved_metrics": [],
            }
        )

    assert result["intent"] == "data_question"
    assert "Không thể đọc semantic layer" in result["chat_response"]
