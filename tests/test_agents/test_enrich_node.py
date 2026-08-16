"""Unit tests for enrich_node — Two-Pass Semantic Enrichment."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.enrich_node import _title_case, enrich_node


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
        },
        "db_type": "postgresql",
    }


@pytest.fixture
def multi_table_state() -> dict:
    return {
        "raw_schema": {
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"column_name": "id", "data_type": "INTEGER"},
                        {"column_name": "total_amount", "data_type": "NUMERIC"},
                    ],
                },
                {
                    "table_name": "customers",
                    "columns": [
                        {"column_name": "id", "data_type": "INTEGER"},
                        {"column_name": "name", "data_type": "VARCHAR"},
                    ],
                },
            ]
        },
        "db_type": "postgresql",
    }


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_node_empty_state_returns_error() -> None:
    result = await enrich_node({})
    assert "error" in result
    assert "raw_schema is empty" in result["error"]


@pytest.mark.asyncio
async def test_enrich_node_no_tables_returns_error() -> None:
    result = await enrich_node({"raw_schema": {}})
    assert "error" in result
    assert "raw_schema is empty" in result["error"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_node_success(sample_raw_schema_state: dict) -> None:
    mock_glossary = {"orders": {"business_name": "Đơn hàng", "description": "Lịch sử mua hàng"}}
    mock_clusters = [
        [
            {
                "table_name": "orders",
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER"},
                    {"column_name": "total_amount", "data_type": "NUMERIC"},
                ],
            }
        ]
    ]
    mock_enriched = {
        "orders": {
            "business_name": "Đơn hàng",
            "description": "Lịch sử mua hàng",
            "columns": [
                {"column_name": "id", "business_name": "Mã đơn hàng", "description": "ID đơn"},
                {"column_name": "total_amount", "business_name": "Tổng tiền", "description": "Giá trị đơn"},
            ],
        }
    }

    with (
        patch("src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, return_value=mock_glossary),
        patch("src.agents.nodes.enrich_node.cluster_tables", return_value=mock_clusters),
        patch(
            "src.agents.nodes.enrich_node.enrich_clusters_parallel", new_callable=AsyncMock, return_value=mock_enriched
        ),
    ):
        result = await enrich_node(sample_raw_schema_state)

    assert "error" not in result
    assert "enriched_schema" in result
    assert "global_glossary" in result
    tables = result["enriched_schema"]["tables"]
    assert len(tables) == 1
    assert tables[0]["business_name"] == "Đơn hàng"
    assert tables[0]["columns"][0]["business_name"] == "Mã đơn hàng"


@pytest.mark.asyncio
async def test_enrich_node_returns_global_glossary(sample_raw_schema_state: dict) -> None:
    mock_glossary = {"orders": {"business_name": "Đơn hàng", "description": "Mô tả"}}

    with (
        patch("src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, return_value=mock_glossary),
        patch("src.agents.nodes.enrich_node.cluster_tables", return_value=[]),
        patch("src.agents.nodes.enrich_node.enrich_clusters_parallel", new_callable=AsyncMock, return_value={}),
    ):
        result = await enrich_node(sample_raw_schema_state)

    assert result["global_glossary"] == mock_glossary


# ---------------------------------------------------------------------------
# Fallback when pass2 misses a table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_node_fallback_to_glossary(sample_raw_schema_state: dict) -> None:
    """When pass2 doesn't return a table, enrich_node falls back to global glossary."""
    mock_glossary = {"orders": {"business_name": "Đơn hàng từ glossary", "description": "Mô tả từ glossary"}}

    with (
        patch("src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, return_value=mock_glossary),
        patch("src.agents.nodes.enrich_node.cluster_tables", return_value=[]),
        patch("src.agents.nodes.enrich_node.enrich_clusters_parallel", new_callable=AsyncMock, return_value={}),
    ):
        result = await enrich_node(sample_raw_schema_state)

    tables = result["enriched_schema"]["tables"]
    assert tables[0]["business_name"] == "Đơn hàng từ glossary"
    assert tables[0]["description"] == "Mô tả từ glossary"
    assert len(tables[0]["columns"]) == 2
    assert tables[0]["columns"][0]["column_name"] == "id"


@pytest.mark.asyncio
async def test_enrich_node_fallback_to_title_case() -> None:
    """When both pass2 and glossary miss, enrich_node uses title case fallback."""
    state = {
        "raw_schema": {
            "tables": [
                {
                    "table_name": "user_sessions",
                    "columns": [
                        {"column_name": "session_id", "data_type": "UUID"},
                    ],
                }
            ]
        },
    }

    with (
        patch("src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, return_value={}),
        patch("src.agents.nodes.enrich_node.cluster_tables", return_value=[]),
        patch("src.agents.nodes.enrich_node.enrich_clusters_parallel", new_callable=AsyncMock, return_value={}),
    ):
        result = await enrich_node(state)

    tables = result["enriched_schema"]["tables"]
    assert tables[0]["business_name"] == "User Sessions"
    assert tables[0]["description"] == "Bảng user_sessions"
    assert tables[0]["columns"][0]["business_name"] == "Session Id"


# ---------------------------------------------------------------------------
# Multi-table with partial pass2 coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_node_partial_pass2_coverage(multi_table_state: dict) -> None:
    """Tables not returned by pass2 should fall back to glossary."""
    mock_glossary = {
        "orders": {"business_name": "Đơn hàng", "description": "Đơn mua"},
        "customers": {"business_name": "Khách hàng", "description": "Bảng KH"},
    }
    # Pass 2 only enriches 'orders', not 'customers'
    mock_enriched = {
        "orders": {
            "business_name": "Đơn hàng chi tiết",
            "description": "Đơn hàng đầy đủ",
            "columns": [
                {"column_name": "id", "business_name": "Mã ĐH", "description": ""},
                {"column_name": "total_amount", "business_name": "Tổng tiền", "description": ""},
            ],
        }
    }

    with (
        patch("src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, return_value=mock_glossary),
        patch("src.agents.nodes.enrich_node.cluster_tables", return_value=[]),
        patch(
            "src.agents.nodes.enrich_node.enrich_clusters_parallel", new_callable=AsyncMock, return_value=mock_enriched
        ),
    ):
        result = await enrich_node(multi_table_state)

    tables = result["enriched_schema"]["tables"]
    assert len(tables) == 2
    # orders → from pass2
    assert tables[0]["business_name"] == "Đơn hàng chi tiết"
    # customers → from glossary fallback
    assert tables[1]["business_name"] == "Khách hàng"


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_node_exception_returns_error(sample_raw_schema_state: dict) -> None:
    with patch(
        "src.agents.nodes.enrich_node.execute_pass1", new_callable=AsyncMock, side_effect=RuntimeError("LLM down")
    ):
        result = await enrich_node(sample_raw_schema_state)

    assert "error" in result
    assert "LLM down" in result["error"]


# ---------------------------------------------------------------------------
# _title_case helper
# ---------------------------------------------------------------------------


def test_title_case_basic() -> None:
    assert _title_case("orders") == "Orders"
    assert _title_case("user_sessions") == "User Sessions"
    assert _title_case("orderItems") == "Orderitems"


def test_title_case_with_spaces() -> None:
    assert _title_case(" some_table ") == "Some Table"
