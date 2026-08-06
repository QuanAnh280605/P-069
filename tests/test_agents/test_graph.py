"""Tests cho Flow 1 LangGraph pipeline.

LLM và DB đều được mock — không gọi OpenAI API thật,
không kết nối database thật.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.state import AgentState


@pytest.mark.asyncio
async def test_agent_state_has_required_fields():
    """AgentState TypedDict phải có đủ fields cho Flow 1."""
    state: AgentState = {
        "db_id": 1,
        "conn_url_enc": "encrypted-url",
        "db_type": "sqlite",
        "raw_schema": {
            "source": {
                "type": "live_connection",
                "db_engine": "sqlite",
                "connection_id": 1,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        },
        "introspection_warnings": [],
        "enriched_schema": {},
        "suggested_metrics": [],
        "hitl_approved": False,
        "semantic_layer_id": 0,
        "error": "",
    }
    assert "conn_url_enc" in state
    assert "raw_schema" in state
    assert "enriched_schema" in state
    assert "suggested_metrics" in state
    assert "semantic_layer_id" in state


@pytest.mark.asyncio
@patch("src.services.llm.get_llm")
async def test_enrich_node_skipped_when_raw_schema_empty(mock_get_llm):
    """Enrich node phải trả về error khi raw_schema rỗng."""
    from src.agents.nodes.enrich_node import enrich_node

    mock_get_llm.return_value = AsyncMock()
    result = await enrich_node({"raw_schema": {}})
    assert "error" in result
    assert result["error"]
