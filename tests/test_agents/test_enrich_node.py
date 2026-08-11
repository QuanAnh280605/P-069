"""Unit tests for enrich_node — Flow 1 Step 2."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.agents.nodes.enrich_node import (
    _build_enrich_prompt,
    _parse_enrich_response,
    enrich_node,
)


@pytest.fixture
def sample_raw_schema_state() -> dict:
    return {
        "raw_schema": {
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"column_name": "id", "data_type": "INTEGER"},
                        {"column_name": "total_amount", "data_type": "NUMERIC"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_enrich_node_empty_state_returns_error() -> None:
    result = await enrich_node({})
    assert "error" in result
    assert "raw_schema is empty" in result["error"]


@pytest.mark.asyncio
async def test_enrich_node_success_with_mocked_llm(sample_raw_schema_state: dict) -> None:
    llm_json_response = """{
        "tables": [
            {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "description": "Lịch sử mua hàng",
                "columns": [
                    {"column_name": "id", "business_name": "Mã đơn hàng", "description": "ID đơn"},
                    {"column_name": "total_amount", "business_name": "Tổng tiền", "description": "Giá trị đơn"}
                ]
            }
        ]
    }"""
    mock_response = MagicMock()
    mock_response.content = llm_json_response

    with patch("src.agents.nodes.enrich_node.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await enrich_node(sample_raw_schema_state)

    assert "enriched_schema" in result
    assert "error" not in result
    tables = result["enriched_schema"]["tables"]
    assert len(tables) == 1
    assert tables[0]["business_name"] == "Đơn hàng"


def test_build_enrich_prompt_contains_table_info(sample_raw_schema_state: dict) -> None:
    prompt = _build_enrich_prompt(sample_raw_schema_state["raw_schema"])
    assert "orders" in prompt
    assert "total_amount" in prompt


def test_parse_enrich_response_fallback(sample_raw_schema_state: dict) -> None:
    fallback = _parse_enrich_response("Invalid JSON content", sample_raw_schema_state["raw_schema"])
    assert "tables" in fallback
    assert len(fallback["tables"]) == 1
    assert fallback["tables"][0]["business_name"] == "Orders"
