"""Tests for save_node — _convert_column with sample_values."""

from __future__ import annotations

from src.agents.nodes.save_node import _convert_column
from src.models.schema_metadata import SchemaDialect


def test_convert_column_with_sample_values() -> None:
    """_convert_column should pass sample_values as tuple."""
    col = {
        "column_name": "status",
        "data_type": "VARCHAR",
        "is_nullable": True,
        "is_primary_key": False,
        "default_value": None,
        "sample_values": ["active", "inactive", "pending"],
    }
    result = _convert_column(col, ordinal=1, dialect=SchemaDialect.POSTGRESQL)
    assert result.sample_values == ("active", "inactive", "pending")
    assert result.column_name.raw_name == "status"


def test_convert_column_without_sample_values() -> None:
    """_convert_column should set sample_values=None when absent."""
    col = {
        "column_name": "amount",
        "data_type": "NUMERIC",
        "is_nullable": True,
        "is_primary_key": False,
    }
    result = _convert_column(col, ordinal=2, dialect=SchemaDialect.POSTGRESQL)
    assert result.sample_values is None


def test_convert_column_with_empty_sample_values() -> None:
    """_convert_column should set sample_values=None when empty list."""
    col = {
        "column_name": "status",
        "data_type": "VARCHAR",
        "sample_values": [],
    }
    result = _convert_column(col, ordinal=3, dialect=SchemaDialect.POSTGRESQL)
    assert result.sample_values is None


def test_convert_column_with_default_value() -> None:
    """_convert_column should pass default_value as default_expression."""
    col = {
        "column_name": "created_at",
        "data_type": "TIMESTAMP",
        "default_value": "CURRENT_TIMESTAMP",
    }
    result = _convert_column(col, ordinal=4, dialect=SchemaDialect.POSTGRESQL)
    assert result.default_expression == "CURRENT_TIMESTAMP"


def test_convert_column_preserves_all_fields() -> None:
    """_convert_column should preserve all fields correctly."""
    col = {
        "column_name": "status",
        "data_type": "VARCHAR",
        "is_nullable": False,
        "is_primary_key": True,
        "default_value": "active",
        "sample_values": ["active", "inactive"],
    }
    result = _convert_column(col, ordinal=1, dialect=SchemaDialect.POSTGRESQL)
    assert result.column_name.raw_name == "status"
    assert result.data_type == "VARCHAR"
    assert result.nullable is False
    assert result.primary_key is True
    assert result.default_expression == "active"
    assert result.sample_values == ("active", "inactive")
    assert result.ordinal_position == 1
