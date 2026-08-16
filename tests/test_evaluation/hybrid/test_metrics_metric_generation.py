"""Tests for hybrid metric-generation metrics."""

from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.metric_generation import build_metric_generation_metrics
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import CandidateMetricOutput, EvaluationConfig
from tests.test_evaluation.hybrid.test_samples import _metric_candidate


def _metric_sample(mini_dataset, candidate):
    samples = build_samples(mini_dataset, {}, {}, {"metric_001": candidate}, {}, {})
    return next(s for s in samples if s.task == "metric_generation")


async def test_perfect_candidate(mini_dataset) -> None:
    metrics = build_metric_generation_metrics(metrics_for_task("metric_generation"))
    sample = _metric_sample(mini_dataset, _metric_candidate())
    results = [await m.score(sample, EvaluationContext(EvaluationConfig())) for m in metrics.values()]
    assert all(r.status == "passed" and r.score == 1.0 for r in results)


async def test_wrong_sql_expression_fails_equivalence(mini_dataset) -> None:
    metrics = build_metric_generation_metrics(metrics_for_task("metric_generation"))
    candidate = _metric_candidate()
    candidate = candidate.model_copy(
        update={"metric": candidate.metric.model_copy(update={"sql_expression": "SUM(other)"})}
    )
    sample = _metric_sample(mini_dataset, candidate)
    result = await metrics["sql_expression_equivalence"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed" and result.score == 0.0


async def test_negative_case_scored_by_identity_only(mini_dataset) -> None:
    case = mini_dataset.metric_cases[0]
    broken = case.model_copy(
        update={"expected_metric": None, "expected_error": "UNSUPPORTED_REQUEST", "expected_preview_facts": []}
    )
    dataset = mini_dataset.model_copy(update={"metric_cases": [broken]})
    metrics = build_metric_generation_metrics(metrics_for_task("metric_generation"))
    sample = _metric_sample(dataset, CandidateMetricOutput(error_code="UNSUPPORTED_REQUEST"))
    identity = await metrics["metric_identity_accuracy"].score(sample, EvaluationContext(EvaluationConfig()))
    formula = await metrics["formula_equivalence"].score(sample, EvaluationContext(EvaluationConfig()))
    assert identity.status == "passed" and identity.score == 1.0
    assert formula.status == "not_applicable"


async def test_missing_response_fails_positive_only_metric(mini_dataset) -> None:
    metrics = build_metric_generation_metrics(metrics_for_task("metric_generation"))
    sample = _metric_sample(mini_dataset, None)
    result = await metrics["formula_equivalence"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed" and result.score == 0.0
