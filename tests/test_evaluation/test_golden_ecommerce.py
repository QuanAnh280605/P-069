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
    assert len(successes) == len(dataset.expected_query_results) == 30
    assert len(errors) == 2
    assert len(successes) + len(errors) == len(dataset.query_cases)


def _execute_case(connection: sqlite3.Connection, sql: str) -> list[dict[str, object]]:
    cursor = connection.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _normalize_rows(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
