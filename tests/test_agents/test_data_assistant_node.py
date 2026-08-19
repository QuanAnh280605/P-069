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
