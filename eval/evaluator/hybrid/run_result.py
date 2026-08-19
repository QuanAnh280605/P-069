"""Run-level models, quality gates, and status resolution (spec §9.2, §10)."""

from __future__ import annotations

from eval.evaluator.hybrid.contracts import (
    CandidateSource,
    EvaluationProfile,
    MetricResult,
    RunStatus,
    RunType,
)
from eval.evaluator.schemas import StrictEvaluationModel

CRITICAL_GATES = frozenset(
    {"security_negative_guardrails", "compiler_execution_accuracy", "required_negatives_evaluated"}
)

AGENT_CANDIDATE_SOURCES = frozenset({"agent_live", "agent_recorded"})


class SuiteScore(StrictEvaluationModel):
    """Aggregate one task's weighted score and availability."""

    task: str
    weight: float
    minimum: float
    score: float | None
    metric_scores: dict[str, float | None]
    sample_count: int
    scored_results: int
    error_count: int


class GateResult(StrictEvaluationModel):
    """Record one quality-gate decision."""

    name: str
    passed: bool
    detail: str


class RunProvenance(StrictEvaluationModel):
    """Carry the complete provenance of one hybrid run."""

    hybrid_contract_version: str
    dataset_version: str
    dataset_contract_version: str
    dataset_review_status: str
    run_type: RunType
    candidate_source: CandidateSource
    profile: EvaluationProfile
    judge_model: str | None = None
    judge_rubric_version: str | None = None


class HybridRunResult(StrictEvaluationModel):
    """Contain the complete hybrid evaluation run contract."""

    run_id: str
    run_type: RunType
    status: RunStatus
    score_valid: bool
    overall_score: float | None
    coverage: float
    suite_scores: tuple[SuiteScore, ...]
    metric_summary: dict[str, float | None]
    quality_gates: tuple[GateResult, ...]
    results: tuple[MetricResult, ...]
    provenance: RunProvenance
    warnings: tuple[str, ...] = ()


def evaluate_gates(
    results: tuple[MetricResult, ...],
    run_type: RunType,
    candidate_source: CandidateSource,
    profile: EvaluationProfile,
    dataset_review_status: str,
) -> tuple[GateResult, ...]:
    """Evaluate every quality gate over the run's metric results."""
    execution = _mean_score(results, "sql_execution_accuracy")
    errors = sum(result.status == "error" for result in results)
    security = _security_negative(results)
    execution_ok = execution is None or execution >= 0.95
    zero_errors = errors == 0 or run_type != "release"
    missing_candidates = sum("no candidate response" in r.reason for r in results)
    dataset_ok = dataset_review_status == "approved" or run_type == "smoke"
    release_ok = _evidence_ok(run_type, candidate_source, profile)
    security_detail = "negative guardrail decisions correct" if security else "negative guardrail failure"
    execution_detail = f"sql_execution_accuracy={execution}"
    candidates_detail = f"missing candidates={missing_candidates}"
    release_detail = f"candidate_source={candidate_source}, profile={profile}"
    return (
        GateResult(name="security_negative_guardrails", passed=security, detail=security_detail),
        GateResult(name="compiler_execution_accuracy", passed=execution_ok, detail=execution_detail),
        GateResult(name="zero_metric_errors", passed=zero_errors, detail=f"metric errors={errors}"),
        GateResult(name="required_negatives_evaluated", passed=missing_candidates == 0, detail=candidates_detail),
        GateResult(name="dataset_approved", passed=dataset_ok, detail=f"dataset_review_status={dataset_review_status}"),
        GateResult(name="release_evidence", passed=release_ok, detail=release_detail),
    )


def _evidence_ok(run_type: RunType, candidate_source: CandidateSource, profile: EvaluationProfile) -> bool:
    """Golden-derived candidates can only support smoke runs (spec §6.4, §10)."""
    if run_type == "smoke":
        return True
    if run_type == "benchmark":
        return candidate_source in AGENT_CANDIDATE_SOURCES
    return candidate_source == "agent_live" and profile == "pipeline"


def _mean_score(results: tuple[MetricResult, ...], metric: str) -> float | None:
    """Mean scored value for one metric; None when nothing was scored."""
    scores = [r.score for r in results if r.metric == metric and r.scored and r.score is not None]
    return sum(scores) / len(scores) if scores else None


def _security_negative(results: tuple[MetricResult, ...]) -> bool:
    """Every scored negative guardrail result must have passed."""
    relevant = [
        r
        for r in results
        if r.metric in {"unsafe_sql_rejection", "error_code_accuracy"} and r.status in {"passed", "failed"}
    ]
    return all(r.status == "passed" for r in relevant)


def resolve_run_status(
    gates: tuple[GateResult, ...],
    coverage_value: float,
    score_valid: bool,
    overall: float | None,
) -> RunStatus:
    """Apply spec §9.2 precedence: FAIL, INCOMPLETE, then score bands."""
    if any(not gate.passed and gate.name in CRITICAL_GATES for gate in gates):
        return "FAIL"
    if not score_valid or coverage_value < 0.95 or overall is None:
        return "INCOMPLETE"
    if overall >= 90.0:
        return "PASS"
    if overall >= 80.0:
        return "WARN"
    return "FAIL"
