"""Tests for quality gates and run-status resolution."""

from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.run_result import CRITICAL_GATES, evaluate_gates, resolve_run_status


def _result(metric: str, status: str, score: float | None = None, reason: str = "") -> MetricResult:
    return MetricResult(
        sample_id="s1",
        metric=metric,
        metric_type="deterministic",
        status=status,
        score=score,
        reason=reason,
        threshold=0.95,  # type: ignore[arg-type]
    )


def test_critical_gate_failure_forces_fail() -> None:
    gates = evaluate_gates(
        (_result("unsafe_sql_rejection", "failed", 0.0),),
        run_type="benchmark",
        candidate_source="agent_live",
        profile="pipeline",
        dataset_review_status="approved",
    )
    security = next(g for g in gates if g.name == "security_negative_guardrails")
    assert security.name in CRITICAL_GATES and not security.passed
    assert resolve_run_status(gates, coverage_value=1.0, score_valid=True, overall=95.0) == "FAIL"


def test_low_compiler_execution_fails_gate() -> None:
    gates = evaluate_gates(
        (_result("sql_execution_accuracy", "failed", 0.5),),
        "benchmark",
        "agent_live",
        "pipeline",
        "approved",
    )
    assert not next(g for g in gates if g.name == "compiler_execution_accuracy").passed


def test_passed_negative_guardrails_pass_security_gate() -> None:
    gates = evaluate_gates(
        (_result("unsafe_sql_rejection", "passed", 1.0), _result("error_code_accuracy", "passed", 1.0)),
        "benchmark",
        "agent_live",
        "pipeline",
        "approved",
    )
    assert next(g for g in gates if g.name == "security_negative_guardrails").passed


def test_unapproved_dataset_blocks_non_smoke() -> None:
    gates = evaluate_gates((), "benchmark", "agent_live", "pipeline", "pending")
    assert not next(g for g in gates if g.name == "dataset_approved").passed


def test_smoke_tolerates_unapproved_dataset() -> None:
    gates = evaluate_gates((), "smoke", "golden_derived", "pipeline", "pending")
    assert next(g for g in gates if g.name == "dataset_approved").passed


def test_release_requires_agent_live_pipeline() -> None:
    recorded = evaluate_gates((), "release", "agent_recorded", "pipeline", "approved")
    assert not next(g for g in recorded if g.name == "release_evidence").passed
    component = evaluate_gates((), "release", "agent_live", "component", "approved")
    assert not next(g for g in component if g.name == "release_evidence").passed


def test_missing_candidate_fails_required_negatives_gate() -> None:
    deterministic = evaluate_gates(
        (_result("sql_execution_accuracy", "failed", 0.0, reason="CANDIDATE_ERROR:no candidate response"),),
        "benchmark",
        "agent_live",
        "pipeline",
        "approved",
    )
    gate = next(g for g in deterministic if g.name == "required_negatives_evaluated")
    assert not gate.passed and "missing candidates=1" in gate.detail
    judge_lane = evaluate_gates(
        (
            _result(
                "business_semantic_correctness",
                "not_applicable",
                reason="candidate not judgeable: no candidate response",
            ),
        ),
        "benchmark",
        "agent_live",
        "pipeline",
        "approved",
    )
    judge_gate = next(g for g in judge_lane if g.name == "required_negatives_evaluated")
    assert not judge_gate.passed
    ordinary = evaluate_gates((_result("table_f1", "passed", 1.0),), "benchmark", "agent_live", "pipeline", "approved")
    assert next(g for g in ordinary if g.name == "required_negatives_evaluated").passed


def test_benchmark_rejects_golden_derived_candidates() -> None:
    gates = evaluate_gates((), "benchmark", "golden_derived", "pipeline", "approved")
    assert not next(g for g in gates if g.name == "release_evidence").passed


def test_benchmark_accepts_agent_candidate_sources() -> None:
    for source in ("agent_live", "agent_recorded"):
        gates = evaluate_gates((), "benchmark", source, "pipeline", "approved")
        assert next(g for g in gates if g.name == "release_evidence").passed


def test_smoke_allows_golden_derived_candidates() -> None:
    gates = evaluate_gates((), "smoke", "golden_derived", "pipeline", "pending")
    assert next(g for g in gates if g.name == "release_evidence").passed


def test_required_negatives_failure_blocks_pass() -> None:
    results = (
        _result("table_f1", "passed", 1.0),
        _result(
            "business_semantic_correctness",
            "not_applicable",
            reason="candidate not judgeable: no candidate response",
        ),
    )
    gates = evaluate_gates(results, "benchmark", "agent_live", "pipeline", "approved")
    assert "required_negatives_evaluated" in CRITICAL_GATES
    assert not next(g for g in gates if g.name == "required_negatives_evaluated").passed
    assert resolve_run_status(gates, coverage_value=1.0, score_valid=True, overall=95.0) == "FAIL"


def test_required_negatives_passing_keeps_pass_path() -> None:
    gates = evaluate_gates((), "smoke", "golden_derived", "pipeline", "approved")
    assert resolve_run_status(gates, 1.0, True, 95.0) == "PASS"


def test_status_precedence_and_score_bands() -> None:
    gates = evaluate_gates((), "smoke", "golden_derived", "pipeline", "pending")
    assert resolve_run_status(gates, 0.9, True, 95.0) == "INCOMPLETE"
    assert resolve_run_status(gates, 1.0, False, 95.0) == "INCOMPLETE"
    assert resolve_run_status(gates, 1.0, True, None) == "INCOMPLETE"
    assert resolve_run_status(gates, 1.0, True, 95.0) == "PASS"
    assert resolve_run_status(gates, 1.0, True, 85.0) == "WARN"
    assert resolve_run_status(gates, 1.0, True, 70.0) == "FAIL"
