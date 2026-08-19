"""Tests for hybrid guardrail metrics."""

from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.guardrail import build_guardrail_metrics
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import CandidateGuardrailOutput, EvaluationConfig
from tests.test_evaluation.hybrid.conftest import _guardrail_case


def _guardrail_sample(mini_dataset, response):
    samples = build_samples(mini_dataset, {}, {}, {}, {}, {"guard_001": response})
    return next(s for s in samples if s.task == "guardrail")


def _accepted() -> CandidateGuardrailOutput:
    return CandidateGuardrailOutput(
        accepted=True, sql="SELECT * FROM orders LIMIT 100", effective_limit=100, effective_timeout_seconds=15
    )


def _rejected(code: str = "NON_SELECT_STATEMENT") -> CandidateGuardrailOutput:
    return CandidateGuardrailOutput(accepted=False, error_code=code)


async def test_positive_case_satisfies_positive_metrics(mini_dataset) -> None:
    metrics = build_guardrail_metrics(metrics_for_task("guardrail"))
    sample = _guardrail_sample(mini_dataset, _accepted())
    context = EvaluationContext(EvaluationConfig())
    results = {name: await metric.score(sample, context) for name, metric in metrics.items()}
    assert results["valid_select_acceptance"].status == "passed"
    assert results["limit_enforcement"].status == "passed"
    assert results["timeout_enforcement"].status == "passed"
    assert results["unsafe_sql_rejection"].status == "not_applicable"
    assert results["error_code_accuracy"].status == "not_applicable"


async def test_accepted_unsafe_sql_fails_critical_rejection(mini_dataset) -> None:
    case = _guardrail_case(sql="DELETE FROM orders", accepted=False)
    dataset = mini_dataset.model_copy(update={"guardrail_cases": [case]})
    metrics = build_guardrail_metrics(metrics_for_task("guardrail"))
    sample = _guardrail_sample(dataset, _accepted())  # guard wrongly accepted a write
    result = await metrics["unsafe_sql_rejection"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed" and result.score == 0.0


async def test_wrong_error_code_fails_accuracy(mini_dataset) -> None:
    case = _guardrail_case(sql="DROP TABLE orders", accepted=False)
    dataset = mini_dataset.model_copy(update={"guardrail_cases": [case]})
    metrics = build_guardrail_metrics(metrics_for_task("guardrail"))
    sample = _guardrail_sample(dataset, _rejected("SOME_OTHER_CODE"))
    result = await metrics["error_code_accuracy"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed"
