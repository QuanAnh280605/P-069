"""Tests for positive, mutated and negative metric outcomes."""

from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.evaluator.metric_eval import evaluate_metric_case
from eval.evaluator.schemas import CandidateMetricDefinition, CandidateMetricOutput, EvaluationConfig

GOLDEN_ROOT = Path("eval/golden_dataset")


class SemanticProvider:
    """Return a deterministic semantic match for text fields."""

    async def similarity(self, left: str, right: str) -> float:
        return 0.95


def _candidate(case, **updates) -> CandidateMetricOutput:
    payload = case.expected_metric.model_dump()
    payload["expected_preview_facts"] = case.expected_preview_facts
    payload.update(updates)
    return CandidateMetricOutput(metric=CandidateMetricDefinition.model_validate(payload))


@pytest.mark.asyncio
async def test_perfect_metric_scores_one() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.metric_cases if item.expected_metric)
    result = await evaluate_metric_case(case, _candidate(case), EvaluationConfig())
    assert result.status == "passed"
    assert all(score.score == 1.0 for score in result.component_scores)


@pytest.mark.asyncio
async def test_identity_mutation_decreases_score() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.metric_cases if item.expected_metric)
    result = await evaluate_metric_case(case, _candidate(case, aggregation="count"), EvaluationConfig())
    identity = next(item for item in result.component_scores if item.component == "core_identity")
    assert identity.score == 0.0


@pytest.mark.asyncio
async def test_expected_error_matches_candidate_error() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.metric_cases if item.expected_error)
    result = await evaluate_metric_case(case, CandidateMetricOutput(error_code=case.expected_error), EvaluationConfig())
    assert result.status == "passed"


@pytest.mark.asyncio
async def test_preview_facts_use_injected_text_similarity() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.metric_cases if item.expected_preview_facts)
    alternatives = tuple(f"semantic alternative {index}" for index, _ in enumerate(case.expected_preview_facts))
    result = await evaluate_metric_case(
        case,
        _candidate(case, expected_preview_facts=alternatives),
        EvaluationConfig(),
        SemanticProvider(),
    )
    preview = next(item for item in result.component_scores if item.component == "expected_preview_facts")
    assert preview.matched
