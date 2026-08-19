"""Compatibility check: hybrid metrics agree with the legacy suites."""

from dataclasses import asdict

from eval.evaluator.compiler_eval import evaluate_compiler_suite
from eval.evaluator.discovery_eval import evaluate_discovery_suite
from eval.evaluator.enrichment_eval import evaluate_enrichment_suite
from eval.evaluator.hybrid.runner import HybridRunRequest, run_hybrid_evaluation
from eval.evaluator.hybrid.smoke import smoke_candidates
from eval.evaluator.metric_eval import evaluate_metric_suite
from eval.evaluator.schemas import EvaluationConfig


def _component(case, name: str) -> float:
    return next(item.score for item in case.component_scores if item.component == name)


def _hybrid(result, metric: str) -> float:
    return next(r.score for r in result.results if r.metric == metric)


async def _pair(mini_dataset):
    config = EvaluationConfig()
    candidates = await smoke_candidates(mini_dataset, config)
    hybrid = await run_hybrid_evaluation(HybridRunRequest(dataset=mini_dataset, config=config, **asdict(candidates)))
    return config, candidates, hybrid


async def test_hybrid_matches_legacy_discovery_tables(mini_dataset) -> None:
    config, candidates, hybrid = await _pair(mini_dataset)
    legacy = await evaluate_discovery_suite(mini_dataset, candidates.discovery, config)
    assert _component(legacy.cases[0], "tables") == _hybrid(hybrid, "table_f1") == 1.0


async def test_hybrid_matches_legacy_enrichment_entities(mini_dataset) -> None:
    config, candidates, hybrid = await _pair(mini_dataset)
    legacy = await evaluate_enrichment_suite(mini_dataset, candidates.enrichment, config)
    assert _component(legacy.cases[0], "entities") == _hybrid(hybrid, "entity_f1") == 1.0


async def test_hybrid_matches_legacy_metric_core_identity(mini_dataset) -> None:
    config, candidates, hybrid = await _pair(mini_dataset)
    legacy = await evaluate_metric_suite(mini_dataset, candidates.metrics, config)
    positive = next(c for c in legacy.cases if any(s.component == "core_identity" for s in c.component_scores))
    assert _component(positive, "core_identity") == _hybrid(hybrid, "metric_identity_accuracy")


async def test_hybrid_matches_legacy_compiler_sql_ast(mini_dataset) -> None:
    config, candidates, hybrid = await _pair(mini_dataset)
    legacy = await evaluate_compiler_suite(mini_dataset, candidates.compiler, config)
    positive = next(c for c in legacy.cases if any(s.component == "sql_ast" for s in c.component_scores))
    assert _component(positive, "sql_ast") == _hybrid(hybrid, "sql_ast_equivalence") == 1.0
