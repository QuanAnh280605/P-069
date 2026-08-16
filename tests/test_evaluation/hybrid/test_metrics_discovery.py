"""Tests for hybrid discovery metrics against the mini fixture."""

from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.discovery import build_discovery_metrics
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import EvaluationConfig
from tests.test_evaluation.hybrid.conftest import _raw_schema


def _discovery_sample(mini_dataset, raw_schema: dict):
    samples = build_samples(mini_dataset, {"disc_001": CandidateDiscoveryOutput(raw_schema=raw_schema)}, {}, {}, {}, {})
    return next(s for s in samples if s.task == "discovery")


async def test_perfect_candidate_scores_one(mini_dataset) -> None:
    metrics = build_discovery_metrics(metrics_for_task("discovery"))
    sample = _discovery_sample(mini_dataset, _raw_schema())
    results = [await metric.score(sample, EvaluationContext(EvaluationConfig())) for metric in metrics.values()]
    assert all(r.status == "passed" and r.score == 1.0 for r in results)


async def test_missing_table_lowers_recall_not_precision(mini_dataset) -> None:
    partial = _raw_schema()
    partial["tables"] = [t for t in partial["tables"] if t["table_name"] != "customers"]
    partial["relationships"] = []
    metrics = build_discovery_metrics(metrics_for_task("discovery"))
    sample = _discovery_sample(mini_dataset, partial)
    context = EvaluationContext(EvaluationConfig())
    precision = await metrics["table_precision"].score(sample, context)
    recall = await metrics["table_recall"].score(sample, context)
    assert precision.score == 1.0
    assert recall.score == 0.5
    assert recall.status == "failed"


async def test_extra_column_lowers_column_f1(mini_dataset) -> None:
    extra = _raw_schema()
    extra["tables"][0]["columns"].append({"column_name": "note", "is_primary_key": False})
    metrics = build_discovery_metrics(metrics_for_task("discovery"))
    sample = _discovery_sample(mini_dataset, extra)
    result = await metrics["column_f1"].score(sample, EvaluationContext(EvaluationConfig()))
    assert round(result.score, 4) == round(10 / 11, 4)  # precision 5/6, recall 1.0
    assert result.details["false_positive"] == 1


async def test_candidate_error_fails_all_metrics(mini_dataset) -> None:
    metrics = build_discovery_metrics(metrics_for_task("discovery"))
    sample = _discovery_sample(mini_dataset, {"tables": []})
    sample = sample.model_copy(update={"response": CandidateDiscoveryOutput(error_code="INTROSPECTION_FAILED")})
    results = [await metric.score(sample, EvaluationContext(EvaluationConfig())) for metric in metrics.values()]
    assert all(r.status == "failed" and r.score == 0.0 and "INTROSPECTION_FAILED" in r.reason for r in results)
