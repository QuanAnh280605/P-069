# tests/test_evaluation/hybrid/test_catalog.py
"""Tests for the frozen hybrid metric catalog."""

import pytest

from eval.evaluator.hybrid.catalog import (
    JUDGE_WEIGHT_CAPS,
    SUITE_MINIMUMS,  # noqa: F401  # brief-verbatim import; not referenced by these tests
    SUITE_WEIGHTS,
    MetricSpec,
    catalog_spec,
    metrics_for_task,
    task_names,
)


def test_suite_weights_sum_to_one() -> None:
    assert sum(SUITE_WEIGHTS.values()) == pytest.approx(1.0)


def test_weights_within_each_task_sum_to_one() -> None:
    for task in task_names():
        weights = sum(spec.weight for spec in metrics_for_task(task))
        assert weights == pytest.approx(1.0), task


def test_judge_contribution_respects_caps() -> None:
    for task, cap in JUDGE_WEIGHT_CAPS.items():
        judge_weight = sum(s.weight for s in metrics_for_task(task) if s.metric_type == "ai_judge")
        assert judge_weight <= cap + 1e-9, task


def test_no_judge_metrics_in_deterministic_suites() -> None:
    for task in ("discovery", "query_compilation", "guardrail"):
        assert all(s.metric_type == "deterministic" for s in metrics_for_task(task))


def test_catalog_spec_round_trip() -> None:
    spec = catalog_spec("table_f1")
    assert isinstance(spec, MetricSpec)
    assert spec.task == "discovery"
    with pytest.raises(KeyError):
        catalog_spec("nope")


def test_judge_prerequisites_are_deterministic_metrics() -> None:
    for spec in (s for t in task_names() for s in metrics_for_task(t)):
        if spec.metric_type == "ai_judge":
            for name in spec.prerequisites:
                assert catalog_spec(name).metric_type == "deterministic"
