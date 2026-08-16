"""Sample-centric metric execution with error isolation and judge gating."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from eval.dataset.loader import DomainDataset
from eval.evaluator.compiler_eval import GuardrailAdapter
from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricResult, MetricType
from eval.evaluator.hybrid.samples import EvaluationSample
from eval.evaluator.schemas import EvaluationConfig, ExecutionResult
from eval.evaluator.text_similarity import TextSimilarityProvider

if TYPE_CHECKING:
    from eval.evaluator.hybrid.judge.base import JudgeRunner


class EvaluationMetric(Protocol):
    """Score one sample deterministically or with an AI judge."""

    name: str
    metric_type: MetricType

    async def score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult: ...


@dataclass
class EvaluationContext:
    """Carry configuration, providers, and caches through one evaluation run."""

    config: EvaluationConfig
    text_provider: TextSimilarityProvider | None = None
    guardrail_adapter: GuardrailAdapter | None = None
    dataset: DomainDataset | None = None
    judge_runner: JudgeRunner | None = None
    execution_cache: dict[str, ExecutionResult | None] = field(default_factory=dict)


async def score_sample(
    sample: EvaluationSample,
    specs: tuple[MetricSpec, ...],
    implementations: Mapping[str, EvaluationMetric],
    context: EvaluationContext,
) -> tuple[MetricResult, ...]:
    """Run deterministic metrics first, then eligible judge metrics."""
    results: list[MetricResult] = []
    observed: dict[str, MetricResult] = {}
    for spec in (s for s in specs if s.metric_type == "deterministic"):
        result = await _run_one(spec, sample, implementations, context)
        results.append(result)
        observed[spec.name] = result
    for spec in (s for s in specs if s.metric_type == "ai_judge"):
        results.append(await _run_judge(spec, sample, implementations, context, observed))
    return tuple(results)


async def _run_one(
    spec: MetricSpec,
    sample: EvaluationSample,
    implementations: Mapping[str, EvaluationMetric],
    context: EvaluationContext,
) -> MetricResult:
    from eval.evaluator.hybrid.metrics.base import error_result, not_applicable_result

    metric = implementations.get(spec.name)
    if metric is None:
        return not_applicable_result(spec, sample.sample_id, "no implementation registered")
    try:
        return await metric.score(sample, context)
    except Exception as exc:  # engine-level isolation mirrors metric-level isolation
        return error_result(spec, sample.sample_id, exc)


async def _run_judge(
    spec: MetricSpec,
    sample: EvaluationSample,
    implementations: Mapping[str, EvaluationMetric],
    context: EvaluationContext,
    observed: Mapping[str, MetricResult],
) -> MetricResult:
    from eval.evaluator.hybrid.metrics.base import not_applicable_result

    failed = [name for name in spec.prerequisites if observed.get(name) is None or observed[name].status != "passed"]
    if failed:
        return not_applicable_result(spec, sample.sample_id, f"prerequisite not passed: {', '.join(failed)}")
    if context.judge_runner is None:
        return not_applicable_result(spec, sample.sample_id, "judge runner unavailable")
    return await _run_one(spec, sample, implementations, context)
