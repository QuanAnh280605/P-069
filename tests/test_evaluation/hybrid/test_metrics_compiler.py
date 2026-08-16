"""Tests for hybrid compiler metrics including isolated SQLite execution."""

from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.compiler import build_compiler_metrics
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import (
    CandidateCanonicalQuery,
    CandidateCompilerOutput,
    CandidateGuardrailOutput,
    EvaluationConfig,
)
from eval.evaluator.sql_normalization import effective_limit


class FakeAdapter:
    """Deterministic guardrail stand-in that accepts safe SELECTs."""

    async def validate(self, sql: str, dialect: str) -> CandidateGuardrailOutput:
        limit = effective_limit(sql, "sqlite") or 100
        return CandidateGuardrailOutput(accepted=True, sql=sql, effective_limit=limit, effective_timeout_seconds=15)


_GOOD_SQL = "SELECT order_month, SUM(amount) AS total FROM orders GROUP BY order_month LIMIT 100"


def _compiler_sample(mini_dataset, candidate):
    samples = build_samples(mini_dataset, {}, {}, {}, {"query_001": candidate}, {})
    return next(s for s in samples if s.task == "query_compilation")


def _candidate(sql: str = _GOOD_SQL) -> CandidateCompilerOutput:
    return CandidateCompilerOutput(
        canonical_query=CandidateCanonicalQuery(
            intent="aggregate",
            domain="mini",
            primary_entity="orders",
            metrics=("total_revenue",),
            dimensions=("order_month",),
        ),
        sql=sql,
    )


async def test_ast_equivalence_ignores_formatting(mini_dataset) -> None:
    metrics = build_compiler_metrics(metrics_for_task("query_compilation"))
    reformatted = _candidate(sql=_GOOD_SQL.replace(" AS total", " as  total"))
    sample = _compiler_sample(mini_dataset, reformatted)
    result = await metrics["sql_ast_equivalence"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "passed"


async def test_execution_unavailable_without_adapter(mini_dataset) -> None:
    metrics = build_compiler_metrics(metrics_for_task("query_compilation"))
    sample = _compiler_sample(mini_dataset, _candidate())
    result = await metrics["sql_execution_accuracy"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "not_applicable"
    assert "unavailable" in result.reason


async def test_execution_accuracy_with_sources(mini_dataset, tmp_path) -> None:
    sources = tmp_path / "sources" / "sqlite"
    sources.mkdir(parents=True)
    (sources / "schema.sql").write_text(
        "CREATE TABLE orders (id INTEGER, amount REAL, order_month TEXT);", encoding="utf-8"
    )
    (sources / "seed_data.sql").write_text(
        "INSERT INTO orders VALUES (1, 10.0, '2026-01');\nINSERT INTO orders VALUES (2, 20.0, '2026-01');",
        encoding="utf-8",
    )
    dataset = mini_dataset.model_copy(
        update={
            "expected_query_results": {"query_001": [{"order_month": "2026-01", "total": 30.0}]},
            "domain_dir": tmp_path,
        }
    )
    metrics = build_compiler_metrics(metrics_for_task("query_compilation"))
    sample = _compiler_sample(dataset, _candidate())
    context = EvaluationContext(EvaluationConfig(), guardrail_adapter=FakeAdapter(), dataset=dataset)
    execution = await metrics["sql_execution_accuracy"].score(sample, context)
    schema = await metrics["result_schema_accuracy"].score(sample, context)
    assert execution.status == "passed", execution.reason
    assert schema.status == "passed"
    assert len(context.execution_cache) == 1  # executed once, shared by both metrics


async def test_negative_case_rejection(mini_dataset) -> None:
    case = mini_dataset.query_cases[0]
    negative = case.model_copy(update={"expected": None, "expected_error": "METRIC_NOT_FOUND"})
    dataset = mini_dataset.model_copy(update={"query_cases": [negative]})
    metrics = build_compiler_metrics(metrics_for_task("query_compilation"))
    sample = _compiler_sample(dataset, CandidateCompilerOutput(error_code="METRIC_NOT_FOUND"))
    result = await metrics["invalid_selection_rejection"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "passed" and result.score == 1.0


async def test_missing_candidate_carries_sentinel_reason(mini_dataset) -> None:
    metrics = build_compiler_metrics(metrics_for_task("query_compilation"))
    sample = _compiler_sample(mini_dataset, None)
    result = await metrics["request_validation_accuracy"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed"
    assert result.reason == "CANDIDATE_ERROR:no candidate response"
