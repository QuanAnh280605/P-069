"""Tests for chitchat node with conversation context."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.chitchat_node import chitchat_node


def _response(content: str) -> MagicMock:
    """Create a minimal LLM response fixture."""
    result = MagicMock()
    result.content = content
    return result


@pytest.mark.asyncio
async def test_empty_user_message_returns_greeting() -> None:
    """An empty or whitespace message returns a quick greeting without invoking LLM."""
    with patch("src.agents.nodes.chitchat_node.get_llm") as mock_get_llm:
        result = await chitchat_node({"user_message": "   "})

    assert "Xin chào" in result["chat_response"]
    mock_get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_chitchat_with_chat_history_passes_context() -> None:
    """Chitchat node forwards prior conversation history to LLM."""
    with patch("src.agents.nodes.chitchat_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.return_value = _response("Chào bạn, câu trước bạn vừa chào 'hello'!")
        mock_get_llm.return_value = llm

        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Chào bạn! Tôi có thể giúp gì?"},
        ]
        result = await chitchat_node(
            {
                "user_message": "nhớ câu trước tôi nói gì không ?",
                "chat_history": history,
            }
        )

    assert "Chào bạn, câu trước bạn vừa chào 'hello'!" in result["chat_response"]
    llm.ainvoke.assert_called_once()
    call_args = llm.ainvoke.call_args[0][0]
    assert len(call_args) == 4  # system + 2 history + user
    assert call_args[0]["role"] == "system"
    assert call_args[1]["content"] == "hello"
    assert call_args[2]["content"] == "Chào bạn! Tôi có thể giúp gì?"
    assert call_args[3]["content"] == "nhớ câu trước tôi nói gì không ?"


@pytest.mark.asyncio
async def test_chitchat_failure_returns_fallback_response() -> None:
    """When LLM call fails, return friendly fallback response."""
    with patch("src.agents.nodes.chitchat_node.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("API error")
        mock_get_llm.return_value = llm

        result = await chitchat_node({"user_message": "hello"})

    assert "Xin lỗi" in result["chat_response"]
