"""Executable integrity tests for the ecommerce Golden Dataset."""

import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset

GOLDEN_ROOT = Path("eval/golden_dataset")


@pytest.fixture(scope="module")
def sqlite_fixture() -> Iterator[sqlite3.Connection]:
    """Build the isolated ecommerce database with foreign keys enabled."""
    domain_dir = GOLDEN_ROOT / "ecommerce"
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    schema = (domain_dir / "sources/sqlite/schema.sql").read_text(encoding="utf-8")
    seed = (domain_dir / "sources/sqlite/seed_data.sql").read_text(encoding="utf-8")
    connection.executescript(schema)
    connection.executescript(seed)
    yield connection
    connection.close()


@pytest.mark.asyncio
async def test_all_sqlite_results_are_reproducible(sqlite_fixture: sqlite3.Connection) -> None:
    """Execute every success query and compare normalized rows to ground truth."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    for case in dataset.query_cases:
        if case.expected:
            actual = _execute_case(sqlite_fixture, case.expected.sql_by_dialect["sqlite"])
            expected = dataset.expected_query_results[case.expected.result_ref]
            assert _normalize_rows(actual) == _normalize_rows(expected), case.case_id


@pytest.mark.asyncio
async def test_success_and_error_query_partition_is_complete() -> None:
    """Require every query to have a result or a declared expected error."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    successes = [case for case in dataset.query_cases if case.expected]
    errors = [case for case in dataset.query_cases if case.expected_error]
    assert len(successes) == len(dataset.expected_query_results) == 34
    assert len(errors) == 5
    assert len(successes) + len(errors) == len(dataset.query_cases)


@pytest.mark.asyncio
async def test_query_level_coverage_and_distribution() -> None:
    """Every ecommerce query case declares a level; distribution follows v3 plan."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    leveled = [case for case in dataset.query_cases if case.level is not None]
    assert len(leveled) == len(dataset.query_cases) - 2  # two negatives stay null
    distribution: dict[str, int] = {}
    for case in dataset.query_cases:
        if case.level is not None:
            distribution[case.level] = distribution.get(case.level, 0) + 1
            assert f"level_{case.level[-1]}" in case.tags, case.case_id
    assert distribution == {"L1": 16, "L2": 12, "L3": 6, "L4": 3}


@pytest.mark.asyncio
async def test_l4_and_negative_cases_expect_errors_only() -> None:
    """L4 ambiguous and negative queries must never compile to SQL."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    for case in dataset.query_cases:
        if case.level == "L4":
            assert case.expected is None, case.case_id
            assert case.expected_error == "NEEDS_CLARIFICATION", case.case_id
            assert case.difficulty == "hard", case.case_id
        if case.level is None:
            assert case.expected_error in {"UNKNOWN_METRIC", "UNSAFE_INTENT"}, case.case_id


def _execute_case(connection: sqlite3.Connection, sql: str) -> list[dict[str, object]]:
    cursor = connection.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _normalize_rows(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
