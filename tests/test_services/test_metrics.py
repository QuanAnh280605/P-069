"""Tests for metrics module — _format_columns and build_metric_system_prompt value sampling."""

from __future__ import annotations

from src.services.metrics import _format_columns, build_metric_system_prompt

# ---------------------------------------------------------------------------
# _format_columns — sample_values
# ---------------------------------------------------------------------------


def test_format_columns_with_sample_values() -> None:
    """Columns with sample_values should include values in output."""
    columns = [
        {
            "column_name": "status",
            "data_type": "VARCHAR",
            "business_name": "Trạng thái",
            "sample_values": ["active", "inactive"],
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "values: ['active', 'inactive']" in result[0]
    assert "status" in result[0]


def test_format_columns_without_sample_values() -> None:
    """Columns without sample_values should not show values."""
    columns = [
        {
            "column_name": "name",
            "data_type": "VARCHAR",
            "business_name": "Tên",
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "values:" not in result[0]


def test_format_columns_with_empty_sample_values() -> None:
    """Columns with empty sample_values list should not show values."""
    columns = [
        {
            "column_name": "status",
            "data_type": "VARCHAR",
            "business_name": "Trạng thái",
            "sample_values": [],
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "values:" not in result[0]


def test_format_columns_with_default_value() -> None:
    """Columns with default_value should include default in output."""
    columns = [
        {
            "column_name": "created_at",
            "data_type": "TIMESTAMP",
            "business_name": "Ngày tạo",
            "default_value": "CURRENT_TIMESTAMP",
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "default: CURRENT_TIMESTAMP" in result[0]


def test_format_columns_with_default_and_sample_values() -> None:
    """Columns with both default_value and sample_values should show both."""
    columns = [
        {
            "column_name": "status",
            "data_type": "VARCHAR",
            "business_name": "Trạng thái",
            "default_value": "active",
            "sample_values": ["active", "inactive", "pending"],
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "default: active" in result[0]
    assert "values: ['active', 'inactive', 'pending']" in result[0]


def test_format_columns_with_none_default_value() -> None:
    """Columns with default_value=None should not show default."""
    columns = [
        {
            "column_name": "name",
            "data_type": "VARCHAR",
            "business_name": "Tên",
            "default_value": None,
        }
    ]
    result = _format_columns(columns)
    assert len(result) == 1
    assert "default:" not in result[0]


def test_format_columns_multiple_columns_mixed() -> None:
    """Multiple columns with mixed sample_values presence."""
    columns = [
        {
            "column_name": "status",
            "data_type": "VARCHAR",
            "business_name": "Trạng thái",
            "sample_values": ["active", "inactive"],
        },
        {
            "column_name": "name",
            "data_type": "VARCHAR",
            "business_name": "Tên",
        },
        {
            "column_name": "category",
            "data_type": "VARCHAR",
            "business_name": "Danh mục",
            "sample_values": ["electronics", "clothing"],
        },
    ]
    result = _format_columns(columns)
    assert len(result) == 3
    assert "values: ['active', 'inactive']" in result[0]
    assert "values:" not in result[1]
    assert "values: ['electronics', 'clothing']" in result[2]


# ---------------------------------------------------------------------------
# build_metric_system_prompt — Rule 6
# ---------------------------------------------------------------------------


def test_metric_system_prompt_contains_rule_6() -> None:
    """System prompt must contain rule 6 about using exact values from sample."""
    prompt = build_metric_system_prompt("test schema text")
    assert "values: [...]" in prompt
    assert "PHẢI dùng đúng 1 giá trị trong danh sách values" in prompt


def test_metric_system_prompt_contains_schema_text() -> None:
    """System prompt must include the provided schema text."""
    schema = "Entity orders: ... test content ..."
    prompt = build_metric_system_prompt(schema)
    assert schema in prompt


def test_metric_system_prompt_contains_all_rules() -> None:
    """System prompt must contain rules 1 through 6."""
    prompt = build_metric_system_prompt("test")
    for rule_text in [
        "formula.function chỉ dùng",
        "formula.expression chỉ gồm",
        "base_entity và các cột phải tồn tại",
        "Ưu tiên base_entity có PK/grain",
        "Filter chỉ dùng cột của base_entity",
        "PHẢI dùng đúng 1 giá trị trong danh sách values",
    ]:
        assert rule_text in prompt
