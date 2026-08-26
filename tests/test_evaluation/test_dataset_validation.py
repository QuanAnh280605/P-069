"""Tests for dataset validation and read-only AST guardrails."""

import pytest

from eval.dataset.models import QueryCase
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
        ("SELECT id FROM orders WHERE store_id = 1 FOR UPDATE", "postgres"),
        ("PRAGMA table_info(orders)", "sqlite"),
        ("SELECT pg_sleep(10)", "postgres"),
    ],
)
def test_validate_read_only_sql_rejects_unsafe_ast(sql: str, dialect: str) -> None:
    """Reject root and nested write operations plus multi-statements."""
    assert validate_read_only_sql(sql, dialect) is False


def test_validate_read_only_sql_rejects_invalid_syntax() -> None:
    """Raise a sanitized validation error for invalid SQL syntax."""
    with pytest.raises(DatasetValidationError, match="Invalid SQL syntax"):
        validate_read_only_sql("SELECT FROM WHERE UNCLOSED ((", "sqlite")


def _query_case(level: str | None, difficulty: str) -> QueryCase:
    """Build one minimal error-outcome query case for level checks."""
    return QueryCase(
        case_id="q_level_probe",
        question="probe?",
        difficulty=difficulty,  # type: ignore[arg-type]
        level=level,  # type: ignore[arg-type]
        expected_error="NEEDS_CLARIFICATION",
        tags=["probe", "ground_truth"],
    )


def test_query_level_consistency_accepts_mapping() -> None:
    """Every level pairs with its declared difficulty (L3/L4 both hard)."""
    from eval.dataset.validator import validate_query_level_consistency

    validate_query_level_consistency(
        [
            _query_case(level, difficulty)
            for level, difficulty in (
                ("L1", "easy"),
                ("L2", "medium"),
                ("L3", "hard"),
                ("L4", "hard"),
                (None, "easy"),  # negatives stay level-less
            )
        ]
    )


def test_query_level_consistency_rejects_mismatch() -> None:
    """A level contradicting its difficulty tag fails validation."""
    from eval.dataset.validator import validate_query_level_consistency

    with pytest.raises(DatasetValidationError, match="Level/difficulty mismatch"):
        validate_query_level_consistency([_query_case("L1", "hard")])
