"""Tests for SQL AST canonicalization and safety validation."""

import pytest

from eval.evaluator.sql_normalization import SqlValidationError, normalize_sql, structurally_equal


def test_format_and_table_alias_are_equivalent() -> None:
    left = "SELECT o.id AS order_id FROM orders AS o WHERE o.id = 1"
    right = " select id from orders where id=1 "
    assert structurally_equal(left, right)


def test_different_predicate_is_not_equivalent() -> None:
    assert not structurally_equal("SELECT id FROM orders WHERE id = 1", "SELECT id FROM orders WHERE id = 2")


def test_different_join_column_source_is_not_equivalent() -> None:
    left = "SELECT a.id FROM foo a JOIN bar b ON a.id = b.id"
    right = "SELECT b.id FROM foo a JOIN bar b ON a.id = b.id"
    assert not structurally_equal(left, right)


def test_different_join_condition_is_not_equivalent() -> None:
    left = "SELECT a.id FROM foo a JOIN bar b ON a.id = b.id"
    right = "SELECT a.id FROM foo a JOIN bar b ON a.id = a.id"
    assert not structurally_equal(left, right)


def test_postgresql_contract_dialect_maps_to_sqlglot() -> None:
    sql = "SELECT DATE_TRUNC('month', created_at) FROM orders"
    assert normalize_sql(sql, "postgresql").canonical


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT 1; SELECT 2",
        "SELECT id INTO backup FROM orders",
        "SELECT readfile('/tmp/secret')",
        "WITH removed AS (DELETE FROM orders RETURNING id) SELECT * FROM removed",
    ],
)
def test_unsafe_or_multi_statement_is_rejected(sql: str) -> None:
    with pytest.raises(SqlValidationError):
        normalize_sql(sql)
