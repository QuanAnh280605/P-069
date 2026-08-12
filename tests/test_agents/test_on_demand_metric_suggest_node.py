"""Unit tests for metric_suggest_node — Flow 1 Step 3.

Covers:
- Empty schema state → error
- Normal metric generation with mocked LLM
- enriched_schema preferred over raw_schema
- LLM exception handled gracefully
- Security guardrails: forbidden SQL, non-SELECT, invalid aggregation, missing fields
- Markdown code-fence stripping
- Schema formatting helpers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.on_demand_metric_suggest_node import (
    _format_schema_for_prompt,
    _parse_and_validate_metrics,
    _resolve_name,
    on_demand_metric_suggest_node,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def enriched_schema_state() -> dict:
    """Fixture: AgentState with a standard e-commerce enriched_schema (semantic layer)."""
    return {
        "enriched_schema": {
            "source": {
                "type": "live_connection",
                "db_engine": "postgresql",
                "connection_id": 1,
                "extracted_at": "2026-08-10T12:00:00Z",
            },
            "tables": [
                {
                    "table_name": "orders",
                    "business_name": "Đơn hàng",
                    "description": "Bảng lưu thông tin đơn hàng",
                    "schema_name": "public",
                    "table_type": "BASE TABLE",
                    "primary_keys": ["id"],
                    "foreign_keys": [],
                    "columns": [
                        {
                            "column_name": "id",
                            "business_name": "Mã đơn hàng",
                            "description": "Định danh duy nhất của đơn hàng",
                            "data_type": "INTEGER",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "is_nullable": False,
                        },
                        {
                            "column_name": "total_amount",
                            "business_name": "Tổng tiền",
                            "description": "Tổng giá trị đơn hàng",
                            "data_type": "NUMERIC",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                            "is_nullable": True,
                        },
                        {
                            "column_name": "status",
                            "business_name": "Trạng thái",
                            "description": "Trạng thái đơn hàng (PENDING, COMPLETED, CANCELLED)",
                            "data_type": "VARCHAR",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                            "is_nullable": False,
                        },
                        {
                            "column_name": "is_deleted",
                            "business_name": "Đã xóa mềm",
                            "description": "Đánh dấu đơn hàng đã bị xóa mềm",
                            "data_type": "BOOLEAN",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                            "is_nullable": False,
                        },
                        {
                            "column_name": "customer_id",
                            "business_name": "Mã khách hàng",
                            "description": "Khóa ngoại tham chiếu đến bảng users",
                            "data_type": "INTEGER",
                            "is_primary_key": False,
                            "is_foreign_key": True,
                            "is_nullable": False,
                        },
                    ],
                    "indexes": [],
                },
                {
                    "table_name": "users",
                    "business_name": "Người dùng",
                    "description": "Bảng lưu thông tin người dùng",
                    "schema_name": "public",
                    "table_type": "BASE TABLE",
                    "primary_keys": ["id"],
                    "foreign_keys": [],
                    "columns": [
                        {
                            "column_name": "id",
                            "business_name": "Mã người dùng",
                            "description": "Định danh duy nhất của người dùng",
                            "data_type": "INTEGER",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "is_nullable": False,
                        },
                    ],
                    "indexes": [],
                },
            ],
            "relationships": [
                {
                    "from_table": "orders",
                    "from_column": "customer_id",
                    "to_table": "users",
                    "to_column": "id",
                    "relationship_type": "many_to_one",
                }
            ],
        }
    }


@pytest.fixture
def valid_llm_json() -> str:
    """Fixture: valid JSON metrics array as returned by LLM."""
    return """[
        {
            "name": "total_revenue",
            "business_name": "Tổng doanh thu",
            "description": "Tổng giá trị đơn hàng thành công, loại trừ bản ghi đã xóa mềm",
            "target_table": "orders",
            "aggregation": "sum",
            "field": "total_amount",
            "sql_template": "SELECT SUM(total_amount) FROM orders WHERE status = 'COMPLETED' AND is_deleted = false"
        },
        {
            "name": "total_orders",
            "business_name": "Tổng số đơn hàng",
            "description": "Số lượng đơn hàng chưa bị xóa trong hệ thống",
            "target_table": "orders",
            "aggregation": "count",
            "field": "id",
            "sql_template": "SELECT COUNT(id) FROM orders WHERE is_deleted = false"
        }
    ]"""


# ---------------------------------------------------------------------------
# Main node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_state_returns_error() -> None:
    """Return error when enriched_schema is absent."""
    result = await on_demand_metric_suggest_node({})
    assert "error" in result
    assert "enriched_schema is empty" in result["error"]


@pytest.mark.asyncio
async def test_success_with_mocked_llm(enriched_schema_state: dict, valid_llm_json: str) -> None:
    """Propose valid metrics with mocked LLM — no hardcoded classification."""
    mock_response = MagicMock()
    mock_response.content = valid_llm_json

    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await on_demand_metric_suggest_node(enriched_schema_state)

    assert "suggested_metrics" in result
    assert "error" not in result
    metrics = result["suggested_metrics"]
    assert len(metrics) == 2
    assert metrics[0]["name"] == "total_revenue"
    assert metrics[0]["business_name"] == "Tổng doanh thu"
    assert metrics[1]["aggregation"] == "count"


@pytest.mark.asyncio
async def test_prefers_enriched_schema(enriched_schema_state: dict, valid_llm_json: str) -> None:
    """Use enriched_schema (semantic layer) — raw_schema is not used."""
    mock_response = MagicMock()
    mock_response.content = valid_llm_json

    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm
        result = await on_demand_metric_suggest_node(enriched_schema_state)

    assert "suggested_metrics" in result


@pytest.mark.asyncio
async def test_llm_exception_returns_error(enriched_schema_state: dict) -> None:
    """Return error dict gracefully when LLM raises an exception."""
    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = RuntimeError("API timeout")
        mock_get_llm.return_value = mock_llm
        result = await on_demand_metric_suggest_node(enriched_schema_state)

    assert "error" in result
    assert "on_demand_metric_suggest_node" in result["error"]


@pytest.mark.asyncio
async def test_prompt_includes_schema_structure(enriched_schema_state: dict, valid_llm_json: str) -> None:
    """Verify the prompt sent to LLM contains table names, column info, and business names."""
    mock_response = MagicMock()
    mock_response.content = valid_llm_json
    captured_prompt = None

    async def capture_ainvoke(prompt: str) -> MagicMock:
        nonlocal captured_prompt
        captured_prompt = prompt
        return mock_response

    with patch("src.agents.nodes.on_demand_metric_suggest_node.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = capture_ainvoke
        mock_get_llm.return_value = mock_llm
        await on_demand_metric_suggest_node(enriched_schema_state)

    assert captured_prompt is not None
    assert "orders" in captured_prompt
    assert "total_amount" in captured_prompt
    assert "NUMERIC" in captured_prompt
    assert "is_deleted" in captured_prompt


# ---------------------------------------------------------------------------
# Security guardrail tests (_parse_and_validate_metrics)
# ---------------------------------------------------------------------------


def test_guardrail_rejects_delete_sql() -> None:
    """Reject metric whose sql_template contains DELETE."""
    bad = [
        {
            "name": "evil",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
            "sql_template": "DELETE FROM orders WHERE 1=1",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_drop_sql() -> None:
    """Reject metric whose sql_template contains DROP TABLE."""
    bad = [
        {
            "name": "drop_it",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
            "sql_template": "SELECT 1; DROP TABLE orders;--",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_update_sql() -> None:
    """Reject metric whose sql_template contains UPDATE."""
    bad = [
        {
            "name": "hack",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
            "sql_template": "UPDATE orders SET total_amount = 0",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_non_select_start() -> None:
    """Reject metric whose sql_template does not start with SELECT."""
    bad = [
        {
            "name": "m",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
            "sql_template": "WITH cte AS (SELECT 1) INSERT INTO t VALUES (1)",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_invalid_aggregation() -> None:
    """Reject metric with aggregation not in allowed set."""
    bad = [
        {
            "name": "m",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "median",
            "field": "x",
            "sql_template": "SELECT MEDIAN(x) FROM t",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_missing_name() -> None:
    """Reject metric without 'name' field."""
    bad = [
        {
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
            "sql_template": "SELECT COUNT(id) FROM t",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_guardrail_rejects_missing_sql_template() -> None:
    """Reject metric without 'sql_template' field."""
    bad = [
        {
            "name": "m",
            "business_name": "X",
            "description": "Y",
            "target_table": "t",
            "aggregation": "count",
            "field": "id",
        }
    ]
    assert _parse_and_validate_metrics(bad) == []


def test_valid_metrics_pass_all_guardrails() -> None:
    """Accept well-formed metrics that pass all guardrails."""
    good = [
        {
            "name": "total_revenue",
            "business_name": "Tổng doanh thu",
            "description": "Tổng tiền đơn hàng",
            "target_table": "orders",
            "aggregation": "sum",
            "field": "total_amount",
            "sql_template": "SELECT SUM(total_amount) FROM orders WHERE status = 'COMPLETED'",
        },
    ]
    result = _parse_and_validate_metrics(good)
    assert len(result) == 1
    assert result[0]["aggregation"] == "sum"


def test_markdown_fences_stripped() -> None:
    """Strip ```json ... ``` from LLM response before parsing."""
    fenced = '```json\n[{"name":"m","business_name":"X","description":"D","target_table":"t","aggregation":"count","field":"id","sql_template":"SELECT COUNT(id) FROM t"}]\n```'
    result = _parse_and_validate_metrics(fenced)
    assert len(result) == 1
    assert result[0]["name"] == "m"


def test_all_valid_aggregations_accepted() -> None:
    """Every allowed aggregation type passes the guardrail."""
    for agg in ("sum", "count", "avg", "min", "max", "count_distinct"):
        metrics = _parse_and_validate_metrics(
            [
                {
                    "name": f"m_{agg}",
                    "business_name": "X",
                    "description": "D",
                    "target_table": "t",
                    "aggregation": agg,
                    "field": "x",
                    "sql_template": "SELECT COUNT(x) FROM t",
                },
            ]
        )
        assert len(metrics) == 1, f"Aggregation '{agg}' should be accepted"


# ---------------------------------------------------------------------------
# Schema formatting helper tests
# ---------------------------------------------------------------------------


def test_format_schema_includes_table_and_column_info() -> None:
    """Schema text sent to LLM contains table names, column names and types."""
    schema = {
        "tables": [
            {
                "table_name": "products",
                "primary_keys": ["id"],
                "foreign_keys": [],
                "columns": [
                    {
                        "column_name": "id",
                        "data_type": "INTEGER",
                        "is_primary_key": True,
                        "is_foreign_key": False,
                        "is_nullable": False,
                    },
                    {
                        "column_name": "price",
                        "data_type": "DECIMAL",
                        "is_primary_key": False,
                        "is_foreign_key": False,
                        "is_nullable": True,
                    },
                ],
            },
        ],
        "relationships": [],
    }
    text = _format_schema_for_prompt(schema)
    assert "products" in text
    assert "price" in text
    assert "DECIMAL" in text
    assert "[PK: id]" in text


def test_format_schema_includes_fk_info() -> None:
    """Schema text includes foreign key constraints when present."""
    schema = {
        "tables": [
            {
                "table_name": "orders",
                "primary_keys": ["id"],
                "foreign_keys": [
                    {"constrained_columns": ["customer_id"], "referred_table": "customers", "referred_columns": ["id"]},
                ],
                "columns": [
                    {
                        "column_name": "id",
                        "data_type": "INTEGER",
                        "is_primary_key": True,
                        "is_foreign_key": False,
                        "is_nullable": False,
                    },
                    {
                        "column_name": "customer_id",
                        "data_type": "INTEGER",
                        "is_primary_key": False,
                        "is_foreign_key": True,
                        "is_nullable": False,
                    },
                ],
            },
        ],
        "relationships": [],
    }
    text = _format_schema_for_prompt(schema)
    assert "customer_id" in text
    assert "customers" in text


def test_resolve_name_flat_string() -> None:
    """Resolve name from flat string field."""
    assert _resolve_name({"table_name": "orders"}, "table_name") == "orders"


def test_resolve_name_nested_dict() -> None:
    """Resolve name from nested Identifier dict (Canonical Model format)."""
    obj = {"table_name": {"raw_name": "Orders", "normalized_name": "orders"}}
    assert _resolve_name(obj, "table_name") == "Orders"


# ---------------------------------------------------------------------------
# Robust JSON extraction tests (PR Reviewer Fix #1)
# ---------------------------------------------------------------------------


def test_json_with_leading_filler_text() -> None:
    """Extract JSON even when LLM adds filler text before the array."""
    response = (
        "Dưới đây là 1 metric quan trọng:\n"
        '[{"name":"m","business_name":"X","description":"D",'
        '"target_table":"t","aggregation":"count","field":"id",'
        '"sql_template":"SELECT COUNT(id) FROM t"}]'
    )
    result = _parse_and_validate_metrics(response)
    assert len(result) == 1
    assert result[0]["name"] == "m"


def test_json_with_trailing_filler_text() -> None:
    """Extract JSON even when LLM adds notes after the array."""
    response = (
        '[{"name":"m","business_name":"X","description":"D",'
        '"target_table":"t","aggregation":"count","field":"id",'
        '"sql_template":"SELECT COUNT(id) FROM t"}]\n'
        "Lưu ý: Metric này đã loại bỏ các đơn hàng xóa mềm."
    )
    result = _parse_and_validate_metrics(response)
    assert len(result) == 1


def test_json_fenced_with_surrounding_text() -> None:
    """Extract JSON from markdown fence surrounded by filler text."""
    response = (
        "Đây là kết quả:\n"
        "```json\n"
        '[{"name":"m","business_name":"X","description":"D",'
        '"target_table":"t","aggregation":"count","field":"id",'
        '"sql_template":"SELECT COUNT(id) FROM t"}]\n'
        "```\n"
        "Hi vọng thông tin này giúp ích."
    )
    result = _parse_and_validate_metrics(response)
    assert len(result) == 1
    assert result[0]["name"] == "m"
