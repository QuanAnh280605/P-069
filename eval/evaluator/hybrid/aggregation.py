"""Weighted metric, suite, and overall aggregation with coverage (spec §9, §11)."""

from __future__ import annotations

from eval.evaluator.hybrid.catalog import SUITE_MINIMUMS, SUITE_WEIGHTS, metrics_for_task, task_names
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.run_result import SuiteScore


def metric_mean_scores(results: tuple[MetricResult, ...]) -> dict[str, float | None]:
    """Mean scored value per metric; None when a metric produced no score."""
    buckets: dict[str, list[float]] = {}
    for result in results:
        if result.scored and result.score is not None:
            buckets.setdefault(result.metric, []).append(result.score)
    names = {result.metric for result in results}
    return {name: sum(values) / len(values) if (values := buckets.get(name)) else None for name in names}


def build_suite_scores(results: tuple[MetricResult, ...]) -> tuple[SuiteScore, ...]:
    """Build one weight-normalized suite score per task."""
    metric_scores = metric_mean_scores(results)
    suites: list[SuiteScore] = []
    for task in task_names():
        specs = metrics_for_task(task)
        task_results = tuple(r for r in results if any(s.name == r.metric for s in specs))
        suites.append(_suite_score(task, specs, task_results, metric_scores))
    return tuple(suites)


def _suite_score(
    task: str,
    specs: tuple,
    task_results: tuple[MetricResult, ...],
    metric_scores: dict[str, float | None],
) -> SuiteScore:
    """Score one suite, normalizing weights over available metrics."""
    available = {s.name: metric_scores[s.name] for s in specs if metric_scores.get(s.name) is not None}
    weight_sum = sum(s.weight for s in specs if s.name in available)
    score = None
    if weight_sum:
        score = sum(s.weight * available[s.name] for s in specs if s.name in available) / weight_sum
    return SuiteScore(
        task=task,
        weight=SUITE_WEIGHTS[task],
        minimum=SUITE_MINIMUMS[task],
        score=score,
        metric_scores={s.name: metric_scores.get(s.name) for s in specs},
        sample_count=len({r.sample_id for r in task_results}),
        scored_results=sum(r.scored for r in task_results),
        error_count=sum(r.status == "error" for r in task_results),
    )


def overall_score(suites: tuple[SuiteScore, ...]) -> float | None:
    """Weight-normalized suite mean on the 0–100 scale."""
    available = [(suite.weight, suite.score) for suite in suites if suite.score is not None]
    if not available:
        return None
    weight_sum = sum(weight for weight, _ in available)
    return 100.0 * sum(weight * score for weight, score in available) / weight_sum


def coverage(results: tuple[MetricResult, ...]) -> float:
    """Evaluated share of applicable results; not_applicable is excluded."""
    applicable = sum(result.status != "not_applicable" for result in results)
    if applicable == 0:
        return 1.0
    evaluated = sum(result.status in {"passed", "failed", "error"} for result in results)
    return evaluated / applicable
