"""Tests for isolated guarded SQLite execution."""

from pathlib import Path

import pytest

from eval.evaluator.execution import EvaluationExecutionError, compare_query_result, execute_guarded_sql
from eval.evaluator.schemas import CandidateGuardrailOutput, EvaluationConfig
from eval.evaluator.sql_normalization import SqlValidationError


def _write_fixture(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_executes_only_accepted_limited_select(tmp_path: Path) -> None:
    schema = _write_fixture(tmp_path / "schema.sql", "CREATE TABLE items(id INTEGER);")
    seed = _write_fixture(tmp_path / "seed.sql", "INSERT INTO items VALUES (1), (2);")
    sql = "SELECT id FROM items ORDER BY id LIMIT 100"
    guardrail = CandidateGuardrailOutput(
        accepted=True,
        sql=sql,
        effective_limit=100,
        effective_timeout_seconds=15,
    )
    result = await execute_guarded_sql(sql, schema, seed, guardrail, EvaluationConfig())
    assert compare_query_result(result, [{"id": 2}, {"id": 1}], EvaluationConfig())


@pytest.mark.asyncio
async def test_rejected_sql_never_executes(tmp_path: Path) -> None:
    rejected = CandidateGuardrailOutput(accepted=False, error_code="NON_SELECT_STATEMENT")
    with pytest.raises(EvaluationExecutionError, match="GUARDRAIL_REJECTED"):
        await execute_guarded_sql("DELETE FROM items", tmp_path / "x", tmp_path / "y", rejected, EvaluationConfig())


@pytest.mark.asyncio
async def test_unsafe_original_is_rejected_even_if_adapter_transforms_it(tmp_path: Path) -> None:
    guarded = CandidateGuardrailOutput(
        accepted=True,
        sql="SELECT 1 LIMIT 100",
        effective_limit=100,
        effective_timeout_seconds=15,
    )
    with pytest.raises(SqlValidationError, match="NON_SELECT_STATEMENT"):
        await execute_guarded_sql("DELETE FROM items", tmp_path / "x", tmp_path / "y", guarded, EvaluationConfig())


@pytest.mark.asyncio
async def test_effective_limit_must_match_guardrail_metadata(tmp_path: Path) -> None:
    guarded = CandidateGuardrailOutput(
        accepted=True,
        sql="SELECT 1 LIMIT 50",
        effective_limit=100,
        effective_timeout_seconds=15,
    )
    with pytest.raises(EvaluationExecutionError, match="INVALID_EFFECTIVE_LIMIT"):
        await execute_guarded_sql("SELECT 1", tmp_path / "x", tmp_path / "y", guarded, EvaluationConfig())


@pytest.mark.asyncio
async def test_timeout_closes_isolated_connection(tmp_path: Path) -> None:
    schema = _write_fixture(tmp_path / "schema.sql", "CREATE TABLE marker(id INTEGER);")
    seed = _write_fixture(tmp_path / "seed.sql", "INSERT INTO marker VALUES (1);")
    sql = "WITH RECURSIVE loop(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM loop) SELECT SUM(x) FROM loop LIMIT 100"
    guardrail = CandidateGuardrailOutput(
        accepted=True,
        sql=sql,
        effective_limit=100,
        effective_timeout_seconds=1,
    )
    with pytest.raises(EvaluationExecutionError, match="STATEMENT_TIMEOUT"):
        await execute_guarded_sql(sql, schema, seed, guardrail, EvaluationConfig(statement_timeout_seconds=1))
    safe_sql = "SELECT id FROM marker LIMIT 100"
    safe_guardrail = guardrail.model_copy(update={"sql": safe_sql})
    result = await execute_guarded_sql(
        safe_sql, schema, seed, safe_guardrail, EvaluationConfig(statement_timeout_seconds=1)
    )
    assert result.rows == ((1,),)
