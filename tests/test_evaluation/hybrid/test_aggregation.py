"""Tests for weighted metric, suite, and overall aggregation plus coverage."""

import pytest

from eval.evaluator.hybrid.aggregation import build_suite_scores, coverage, metric_mean_scores, overall_score
from eval.evaluator.hybrid.contracts import MetricResult


def _result(metric: str, status: str, score: float | None = None) -> MetricResult:
    return MetricResult(
        sample_id="s1",
        metric=metric,
        metric_type="deterministic",
        status=status,
        score=score,
        threshold=0.95,  # type: ignore[arg-type]
    )


def test_metric_mean_ignores_unscored_results() -> None:
    scores = metric_mean_scores((_result("table_f1", "passed", 1.0), _result("table_f1", "failed", 0.5)))
    assert scores["table_f1"] == pytest.approx(0.75)
    assert metric_mean_scores((_result("table_f1", "not_applicable"),))["table_f1"] is None


def test_suite_score_normalizes_available_metric_weights() -> None:
    # table_f1 w=0.4 and column_f1 w=0.3 available; precision/recall w=0.0 unavailable
    suites = build_suite_scores((_result("table_f1", "passed", 1.0), _result("column_f1", "passed", 0.5)))
    discovery = next(s for s in suites if s.task == "discovery")
    assert discovery.score == pytest.approx((0.4 * 1.0 + 0.3 * 0.5) / 0.7)
    assert discovery.metric_scores["table_recall"] is None


def test_overall_score_scales_to_100() -> None:
    assert overall_score(build_suite_scores((_result("table_f1", "passed", 1.0),))) == pytest.approx(100.0)
    assert overall_score(()) is None


def test_coverage_excludes_not_applicable() -> None:
    results = (
        _result("table_f1", "passed", 1.0),
        _result("table_f1", "not_applicable"),
        _result("table_f1", "error"),
    )
    assert coverage(results) == pytest.approx(1.0)
    assert coverage(()) == 1.0
