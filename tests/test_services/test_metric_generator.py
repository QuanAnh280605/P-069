"""Unit tests for Business Metric generation service and sqlglot SQL validation.

Validates read-only safety, identifier checks, LLM structured output parsing,
and retry behavior without executing queries against Target DB.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.schemas import GeneratedMetric, MetricSuggestions
from src.services.metrics import (
    extract_schema_summary,
    generate_metrics_from_prompt,
    normalize_prompt,
    validate_sql_template,
)


def test_normalize_prompt_valid():
    """Valid prompt must be stripped properly."""
    assert normalize_prompt("  Tỷ lệ khách hàng quay lại  ") == "Tỷ lệ khách hàng quay lại"


def test_normalize_prompt_empty():
    """Empty or whitespace-only prompt must raise ValueError."""
    with pytest.raises(ValueError, match="empty"):
        normalize_prompt("   ")


def test_normalize_prompt_too_long():
    """Prompt exceeding 2000 characters must raise ValueError."""
    long_prompt = "a" * 2001
    with pytest.raises(ValueError, match="2000"):
        normalize_prompt(long_prompt)


def test_extract_schema_summary():
    """Schema summary must correctly extract valid tables, columns, and relationships."""
    schema_dict = {
        "orders": {
            "business_name": "Đơn hàng",
            "description": "Lịch sử đơn hàng",
            "columns": [
                {"column_name": "order_id", "data_type": "INTEGER", "is_primary_key": True, "business_name": "Mã đơn"},
                {"column_name": "total_amount", "data_type": "NUMERIC", "business_name": "Tổng tiền"},
            ],
        }
    }
    valid_tables, summary_text = extract_schema_summary(schema_dict)
    assert "orders" in valid_tables
    assert "order_id" in valid_tables["orders"]
    assert "total_amount" in valid_tables["orders"]
    assert "Table `orders`" in summary_text
    assert "[PK]" in summary_text


def test_sql_validator_valid_select():
    """Standard read-only SELECT statement must pass validation."""
    valid_tables = {"orders": {"order_id", "total_amount", "customer_id"}}
    sql = "SELECT customer_id, SUM(total_amount) AS total_spent FROM orders GROUP BY customer_id"
    is_valid, reason = validate_sql_template(sql, "postgres", valid_tables)
    assert is_valid is True
    assert "Valid SELECT" in reason


def test_sql_validator_cte_query():
    """CTE query starting with WITH must pass validation and recognize CTE table name."""
    valid_tables = {"orders": {"order_id", "customer_id", "order_status"}}
    sql = (
        "WITH sub AS (SELECT customer_id, COUNT(*) AS cnt FROM orders GROUP BY customer_id) "
        "SELECT COUNT(*) FROM sub WHERE cnt > 1"
    )
    is_valid, _ = validate_sql_template(sql, "postgres", valid_tables)
    assert is_valid is True


def test_sql_validator_rejects_dml():
    """DML statements (INSERT, UPDATE, DELETE) must be rejected."""
    is_valid, reason = validate_sql_template("DELETE FROM orders WHERE order_id = 1", "postgres")
    assert is_valid is False

    is_valid, reason = validate_sql_template("UPDATE orders SET total_amount = 0", "postgres")
    assert is_valid is False

    is_valid, reason = validate_sql_template("INSERT INTO orders (order_id) VALUES (1)", "postgres")
    assert is_valid is False


def test_sql_validator_rejects_ddl():
    """DDL statements (DROP, ALTER, CREATE, TRUNCATE) must be rejected."""
    is_valid, _ = validate_sql_template("DROP TABLE orders", "postgres")
    assert is_valid is False

    is_valid, _ = validate_sql_template("ALTER TABLE orders ADD COLUMN test INT", "postgres")
    assert is_valid is False


def test_sql_validator_rejects_multi_statement():
    """Multi-statement SQL separated by semicolons must be rejected."""
    sql = "SELECT * FROM orders; DROP TABLE customers;"
    is_valid, reason = validate_sql_template(sql, "postgres")
    assert is_valid is False
    assert "exactly one" in reason


def test_sql_validator_rejects_unknown_table():
    """SQL referencing non-existent tables in schema must be rejected."""
    valid_tables = {"orders": {"order_id"}}
    sql = "SELECT * FROM secret_passwords"
    is_valid, reason = validate_sql_template(sql, "postgres", valid_tables)
    assert is_valid is False
    assert "not present in schema" in reason


@pytest.mark.asyncio
@patch("src.services.metrics.get_llm")
async def test_generate_metrics_success(mock_get_llm):
    """Service returns 1-3 valid metric suggestion items from structured LLM."""
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(
        return_value=MetricSuggestions(
            metrics=[
                GeneratedMetric(
                    name="Tỷ lệ khách hàng quay lại",
                    description="Tỷ lệ khách hàng có từ 2 đơn trở lên",
                    sql_template="SELECT COUNT(*) FROM orders WHERE total_amount > 0",
                ),
                GeneratedMetric(
                    name="Doanh thu trung bình",
                    description="Giá trị đơn hàng trung bình",
                    sql_template="SELECT AVG(total_amount) FROM orders",
                ),
            ]
        )
    )
    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = mock_structured
    mock_get_llm.return_value = mock_llm_instance

    schema_dict = {"orders": {"columns": [{"column_name": "total_amount"}]}}
    suggestions = await generate_metrics_from_prompt("Tính doanh thu", "postgres", schema_dict)
    assert len(suggestions) == 2
    assert suggestions[0].name == "Tỷ lệ khách hàng quay lại"
    assert suggestions[0].source == "ai"


@pytest.mark.asyncio
@patch("src.services.metrics.get_llm")
async def test_generate_metrics_filters_invalid_sql(mock_get_llm):
    """Service filters out invalid suggestions and keeps only valid ones."""
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(
        return_value=MetricSuggestions(
            metrics=[
                GeneratedMetric(
                    name="Metric Xấu",
                    description="Chứa lệnh xóa dữ liệu",
                    sql_template="DELETE FROM orders",
                ),
                GeneratedMetric(
                    name="Metric Hợp lệ",
                    description="Truy vấn an toàn",
                    sql_template="SELECT COUNT(*) FROM orders",
                ),
            ]
        )
    )
    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = mock_structured
    mock_get_llm.return_value = mock_llm_instance

    schema_dict = {"orders": {"columns": []}}
    suggestions = await generate_metrics_from_prompt("Đếm đơn hàng", "postgres", schema_dict)
    assert len(suggestions) == 1
    assert suggestions[0].name == "Metric Hợp lệ"
