"""Tests for dataset validation and read-only AST guardrails."""

import pytest

from eval.dataset.validator import DatasetValidationError, validate_read_only_sql


@pytest.mark.parametrize(
    ("sql", "dialect"),
    [
        ("SELECT id FROM orders", "sqlite"),
        ("WITH recent AS (SELECT id FROM orders) SELECT * FROM recent", "postgres"),
    ],
)
def test_validate_read_only_sql_accepts_safe_select(sql: str, dialect: str) -> None:
    """Accept one side-effect-free SELECT, including read-only CTEs."""
    assert validate_read_only_sql(sql, dialect) is True


@pytest.mark.parametrize(
    ("sql", "dialect"),
    [
        ("DELETE FROM orders", "sqlite"),
        ("DROP TABLE products", "postgres"),
        ("SELECT * INTO copied_orders FROM orders", "postgres"),
        ("WITH gone AS (DELETE FROM orders RETURNING *) SELECT * FROM gone", "postgres"),
        ("SELECT 1; SELECT 2", "sqlite"),
        ("SELECT load_extension('unsafe')", "sqlite"),
    ],
)
def test_validate_read_only_sql_rejects_unsafe_ast(sql: str, dialect: str) -> None:
    """Reject root and nested write operations plus multi-statements."""
    assert validate_read_only_sql(sql, dialect) is False


def test_validate_read_only_sql_rejects_invalid_syntax() -> None:
    """Raise a sanitized validation error for invalid SQL syntax."""
    with pytest.raises(DatasetValidationError, match="Invalid SQL syntax"):
        validate_read_only_sql("SELECT FROM WHERE UNCLOSED ((", "sqlite")
