"""Isolated and fail-closed SQLite execution for evaluation fixtures."""

from __future__ import annotations

import asyncio
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import JsonValue

from eval.evaluator.schemas import CandidateGuardrailOutput, EvaluationConfig, ExecutionResult
from eval.evaluator.sql_normalization import effective_limit, normalize_sql


class EvaluationExecutionError(RuntimeError):
    """Report a safe candidate execution failure."""


async def execute_guarded_sql(
    sql: str,
    schema_path: Path,
    seed_path: Path,
    guardrail: CandidateGuardrailOutput,
    config: EvaluationConfig,
) -> ExecutionResult:
    """Execute an accepted guarded SELECT in an isolated SQLite database."""
    _validate_execution_request(sql, guardrail, config)
    schema, seed = await asyncio.gather(
        asyncio.to_thread(schema_path.read_text, encoding="utf-8"),
        asyncio.to_thread(seed_path.read_text, encoding="utf-8"),
    )
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_execute_sqlite, schema, seed, guardrail.sql or "", config),
            timeout=config.statement_timeout_seconds + 1,
        )
    except TimeoutError as exc:
        raise EvaluationExecutionError("STATEMENT_TIMEOUT") from exc
    except sqlite3.Error as exc:
        if "interrupted" in str(exc).casefold():
            raise EvaluationExecutionError("STATEMENT_TIMEOUT") from exc
        raise EvaluationExecutionError("SQL_EXECUTION_ERROR") from exc


def compare_query_result(
    actual: ExecutionResult,
    expected: Sequence[Mapping[str, JsonValue]],
    config: EvaluationConfig,
    ordered: bool = False,
) -> bool:
    """Compare columns and duplicate-preserving rows using configured float tolerances."""
    expected_columns = tuple(expected[0].keys()) if expected else actual.columns
    if actual.columns != expected_columns:
        return False
    expected_rows = tuple(tuple(row[column] for column in expected_columns) for row in expected)
    if ordered:
        return _rows_equal(actual.rows, expected_rows, config)
    return _multiset_rows_equal(actual.rows, expected_rows, config)


def _validate_execution_request(
    original_sql: str,
    guardrail: CandidateGuardrailOutput,
    config: EvaluationConfig,
) -> None:
    if not guardrail.accepted or guardrail.sql is None:
        raise EvaluationExecutionError("GUARDRAIL_REJECTED")
    normalize_sql(original_sql, "sqlite")
    normalize_sql(guardrail.sql, "sqlite")
    limit = effective_limit(guardrail.sql, "sqlite")
    if limit is None or limit > config.maximum_limit or limit != guardrail.effective_limit:
        raise EvaluationExecutionError("INVALID_EFFECTIVE_LIMIT")
    if guardrail.effective_timeout_seconds != config.statement_timeout_seconds:
        raise EvaluationExecutionError("INVALID_EFFECTIVE_TIMEOUT")


def _execute_sqlite(
    schema: str,
    seed: str,
    sql: str,
    config: EvaluationConfig,
) -> ExecutionResult:
    connection = sqlite3.connect(":memory:")
    deadline = time.monotonic() + config.statement_timeout_seconds
    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        connection.executescript(schema)
        connection.executescript(seed)
        cursor = connection.execute(sql)
        columns = tuple(item[0] for item in cursor.description or ())
        rows = tuple(tuple(_json_scalar(value) for value in row) for row in cursor.fetchall())
        return ExecutionResult(columns=columns, rows=rows)
    finally:
        connection.close()


def _json_scalar(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def _rows_equal(
    actual: Sequence[Sequence[JsonValue]],
    expected: Sequence[Sequence[JsonValue]],
    config: EvaluationConfig,
) -> bool:
    return len(actual) == len(expected) and all(
        _row_equal(left, right, config) for left, right in zip(actual, expected, strict=True)
    )


def _multiset_rows_equal(
    actual: Sequence[Sequence[JsonValue]],
    expected: Sequence[Sequence[JsonValue]],
    config: EvaluationConfig,
) -> bool:
    remaining = list(expected)
    for row in actual:
        match = next((index for index, item in enumerate(remaining) if _row_equal(row, item, config)), None)
        if match is None:
            return False
        remaining.pop(match)
    return not remaining


def _row_equal(left: Sequence[JsonValue], right: Sequence[JsonValue], config: EvaluationConfig) -> bool:
    if len(left) != len(right):
        return False
    return all(_value_equal(a, b, config) for a, b in zip(left, right, strict=True))


def _value_equal(left: JsonValue, right: JsonValue, config: EvaluationConfig) -> bool:
    if isinstance(left, int | float) and isinstance(right, int | float):
        return math.isclose(
            float(left),
            float(right),
            rel_tol=config.float_relative_tolerance,
            abs_tol=config.float_absolute_tolerance,
        )
    return left == right
