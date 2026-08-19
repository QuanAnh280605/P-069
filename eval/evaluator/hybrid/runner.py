"""End-to-end hybrid evaluation runner (spec §10)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from eval.dataset.loader import DomainDataset
from eval.dataset.models import DomainManifest
from eval.evaluator.compiler_eval import GuardrailAdapter
from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.hybrid.aggregation import build_suite_scores, coverage, metric_mean_scores, overall_score
from eval.evaluator.hybrid.catalog import MetricSpec, all_metric_specs, metrics_for_task
from eval.evaluator.hybrid.contracts import (
    HYBRID_CONTRACT_VERSION,
    CandidateSource,
    EvaluationProfile,
    MetricResult,
    RunType,
)
from eval.evaluator.hybrid.engine import EvaluationContext, EvaluationMetric, score_sample
from eval.evaluator.hybrid.judge.metrics import build_judge_metrics
from eval.evaluator.hybrid.metrics.compiler import build_compiler_metrics
from eval.evaluator.hybrid.metrics.discovery import build_discovery_metrics
from eval.evaluator.hybrid.metrics.enrichment import build_enrichment_metrics
from eval.evaluator.hybrid.metrics.guardrail import build_guardrail_metrics
from eval.evaluator.hybrid.metrics.metric_generation import build_metric_generation_metrics
from eval.evaluator.hybrid.run_result import (
    GateResult,
    HybridRunResult,
    RunProvenance,
    SuiteScore,
    evaluate_gates,
    resolve_run_status,
)
from eval.evaluator.hybrid.samples import EvaluationSample, build_samples
from eval.evaluator.schemas import (
    CandidateCompilerOutput,
    CandidateEnrichmentOutput,
    CandidateGuardrailOutput,
    CandidateMetricOutput,
    EvaluationConfig,
)
from eval.evaluator.text_similarity import TextSimilarityProvider

if TYPE_CHECKING:
    from eval.evaluator.hybrid.judge.base import JudgeRunner


@dataclass
class HybridRunRequest:
    """Carry every input of one hybrid evaluation run."""

    dataset: DomainDataset
    config: EvaluationConfig
    discovery: Mapping[str, CandidateDiscoveryOutput] = field(default_factory=dict)
    enrichment: Mapping[str, CandidateEnrichmentOutput] = field(default_factory=dict)
    metrics: Mapping[str, CandidateMetricOutput] = field(default_factory=dict)
    compiler: Mapping[str, CandidateCompilerOutput] = field(default_factory=dict)
    guardrail: Mapping[str, CandidateGuardrailOutput] = field(default_factory=dict)
    text_provider: TextSimilarityProvider | None = None
    guardrail_adapter: GuardrailAdapter | None = None
    judge_runner: JudgeRunner | None = None
    run_id: str = "eval-hybrid"
    run_type: RunType = "smoke"
    candidate_source: CandidateSource = "golden_derived"
    profile: EvaluationProfile = "pipeline"


def default_implementations() -> dict[str, EvaluationMetric]:
    """Build the standard metric implementations from the frozen catalog."""
    implementations: dict[str, EvaluationMetric] = {}
    for builder in (
        build_discovery_metrics,
        build_enrichment_metrics,
        build_metric_generation_metrics,
        build_compiler_metrics,
        build_guardrail_metrics,
        build_judge_metrics,
    ):
        implementations.update(builder(all_metric_specs()))
    return implementations


async def run_hybrid_evaluation(request: HybridRunRequest) -> HybridRunResult:
    """Score every sample and assemble the complete run result."""
    samples = build_samples(
        request.dataset,
        dict(request.discovery),
        dict(request.enrichment),
        dict(request.metrics),
        dict(request.compiler),
        dict(request.guardrail),
    )
    context = _context(request)
    implementations = default_implementations()
    results: list[MetricResult] = []
    for sample in samples:
        specs = metrics_for_task(sample.task)
        results.extend(await score_sample(sample, specs, implementations, context))
    return build_run_result(
        run_id=request.run_id,
        run_type=request.run_type,
        candidate_source=request.candidate_source,
        profile=request.profile,
        dataset=request.dataset,
        results=tuple(results),
        judge_model=_judge_model(request.judge_runner),
        warnings=_warnings(samples),
    )


def build_run_result(
    run_id: str,
    run_type: RunType,
    candidate_source: CandidateSource,
    profile: EvaluationProfile,
    dataset: DomainDataset,
    results: tuple[MetricResult, ...],
    judge_model: str | None = None,
    warnings: tuple[str, ...] = (),
) -> HybridRunResult:
    """Assemble the complete run result from metric results and gates."""
    manifest = dataset.manifest
    gates = evaluate_gates(results, run_type, candidate_source, profile, manifest.review_status)
    suites, summary, overall, covered = _aggregates(results)
    valid = _score_valid(gates, summary, results, run_type)
    status = resolve_run_status(gates, covered, valid, overall)
    return HybridRunResult(
        run_id=run_id,
        run_type=run_type,
        status=status,
        score_valid=valid,
        overall_score=overall,
        coverage=covered,
        suite_scores=suites,
        metric_summary=summary,
        quality_gates=gates,
        results=results,
        warnings=warnings,
        provenance=_provenance(manifest, run_type, candidate_source, profile, judge_model),
    )


def _context(request: HybridRunRequest) -> EvaluationContext:
    """Build the shared evaluation context from one run request."""
    return EvaluationContext(
        config=request.config,
        text_provider=request.text_provider,
        guardrail_adapter=request.guardrail_adapter,
        dataset=request.dataset,
        judge_runner=request.judge_runner,
    )


def _aggregates(
    results: tuple[MetricResult, ...],
) -> tuple[tuple[SuiteScore, ...], dict[str, float | None], float | None, float]:
    """Compute suite scores, metric means, overall score, and coverage."""
    suites = build_suite_scores(results)
    return suites, metric_mean_scores(results), overall_score(suites), coverage(results)


def _provenance(
    manifest: DomainManifest,
    run_type: RunType,
    candidate_source: CandidateSource,
    profile: EvaluationProfile,
    judge_model: str | None,
) -> RunProvenance:
    """Carry dataset, run-type, and judge provenance into the result."""
    return RunProvenance(
        hybrid_contract_version=HYBRID_CONTRACT_VERSION,
        dataset_version=manifest.dataset_version,
        dataset_contract_version=manifest.contract_version,
        dataset_review_status=manifest.review_status,
        run_type=run_type,
        candidate_source=candidate_source,
        profile=profile,
        judge_model=judge_model,
    )


def _score_valid(
    gates: tuple[GateResult, ...],
    summary: dict[str, float | None],
    results: tuple[MetricResult, ...],
    run_type: RunType,
) -> bool:
    """A score is valid only when evidence gates pass and required metrics are available."""
    blocked = {gate.name for gate in gates if not gate.passed}
    if blocked & {"dataset_approved", "release_evidence"}:
        return False
    not_applicable_only = _not_applicable_metrics(results)
    return all(
        _required_satisfied(spec, not_applicable_only, summary, run_type)
        for spec in all_metric_specs()
        if spec.required
    )


def _required_satisfied(
    spec: MetricSpec,
    not_applicable_only: frozenset[str],
    summary: dict[str, float | None],
    run_type: RunType,
) -> bool:
    """Judge unavailability is designed; deterministic unavailability only in smoke runs."""
    exempt = spec.name in not_applicable_only and (spec.metric_type == "ai_judge" or run_type == "smoke")
    return exempt or summary.get(spec.name) is not None


def _not_applicable_metrics(results: tuple[MetricResult, ...]) -> frozenset[str]:
    """Names whose every recorded result is not_applicable (legitimately unavailable)."""
    names = {result.metric for result in results}
    return frozenset(
        name for name in names if all(result.status == "not_applicable" for result in results if result.metric == name)
    )


def _judge_model(judge_runner: JudgeRunner | None) -> str | None:
    """Read the judge model name when a judge runner is configured."""
    if judge_runner is None:
        return None
    return getattr(judge_runner.llm, "model_name", None)


def _warnings(samples: tuple[EvaluationSample, ...]) -> tuple[str, ...]:
    """Report every sample that ran without a captured response."""
    return tuple(
        f"sample {sample.sample_id} ({sample.task}) has no candidate response"
        for sample in samples
        if sample.response is None
    )
