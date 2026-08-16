"""Tests for the hybrid metric engine: isolation, ordering, judge prerequisites."""

from dataclasses import dataclass

from eval.evaluator.hybrid.catalog import MetricSpec, metrics_for_task
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext, score_sample
from eval.evaluator.hybrid.metrics.base import DeterministicMetric
from eval.evaluator.hybrid.samples import GuardrailInput
from eval.evaluator.schemas import EvaluationConfig
from tests.test_evaluation.hybrid.conftest import _guardrail_case


@dataclass
class FakeDeterministic(DeterministicMetric):
    outcome: str = "passed"

    async def _score(self, sample, context) -> MetricResult:
        if self.outcome == "boom":
            raise RuntimeError("boom")
        from eval.evaluator.hybrid.metrics.base import boolean_result

        return boolean_result(self.spec, sample.sample_id, self.outcome == "passed")


@dataclass
class FakeJudge:
    name: str = "business_semantic_correctness"
    metric_type: str = "ai_judge"

    async def score(self, sample, context) -> MetricResult:
        return MetricResult(
            sample_id=sample.sample_id,
            metric=self.name,
            metric_type="ai_judge",
            status="passed",
            score=0.9,
            threshold=0.8,
        )


def _sample():
    from eval.evaluator.hybrid.samples import EvaluationSample

    case = _guardrail_case()
    return EvaluationSample(
        sample_id=case.case_id,
        task="guardrail",
        input=GuardrailInput(sql=case.sql, dialect="sqlite"),
        reference=case.expected,
        tags=("mini",),
    )


def _specs():
    return (
        MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.5),
        MetricSpec("business_semantic_correctness", "enrichment", "ai_judge", 0.8, 0.5, prerequisites=("entity_f1",)),
    )


async def test_deterministic_exception_becomes_error_result() -> None:
    broken = FakeDeterministic(MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.5), "boom")
    results = await score_sample(_sample(), _specs(), {"entity_f1": broken}, EvaluationContext(EvaluationConfig()))
    assert results[0].status == "error"
    assert results[0].reason == "RuntimeError"


async def test_judge_skipped_after_failed_prerequisite() -> None:
    failed = FakeDeterministic(MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.5), "failed")
    judge = FakeJudge()
    context = EvaluationContext(EvaluationConfig())
    context.judge_runner = object()  # judge lane available
    results = await score_sample(_sample(), _specs(), {"entity_f1": failed, judge.name: judge}, context)
    assert results[1].status == "not_applicable"
    assert "entity_f1" in results[1].reason


async def test_judge_skipped_when_runner_missing() -> None:
    passed = FakeDeterministic(MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.5), "passed")
    results = await score_sample(
        _sample(),
        _specs(),
        {"entity_f1": passed, "business_semantic_correctness": FakeJudge()},
        EvaluationContext(EvaluationConfig()),
    )
    assert results[1].status == "not_applicable"
    assert "judge" in results[1].reason


async def test_judge_runs_when_prerequisite_passes() -> None:
    passed = FakeDeterministic(MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.5), "passed")
    context = EvaluationContext(EvaluationConfig())
    context.judge_runner = object()
    results = await score_sample(
        _sample(), _specs(), {"entity_f1": passed, "business_semantic_correctness": FakeJudge()}, context
    )
    assert results[1].status == "passed"


async def test_unknown_implementation_is_not_applicable() -> None:
    results = await score_sample(_sample(), metrics_for_task("guardrail"), {}, EvaluationContext(EvaluationConfig()))
    assert all(r.status == "not_applicable" for r in results)
