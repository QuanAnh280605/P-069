"""Tests for entity name and relationship enrichment evaluation."""

from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.evaluator.enrichment_eval import evaluate_enrichment_case, evaluate_enrichment_suite
from eval.evaluator.schemas import (
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateRelationship,
    EvaluationConfig,
)

GOLDEN_ROOT = Path("eval/golden_dataset")


class FailingProvider:
    """Raise deterministically to verify case isolation."""

    async def similarity(self, left: str, right: str) -> float:
        raise RuntimeError("provider unavailable")


def _perfect_candidate(dataset, case) -> CandidateEnrichmentOutput:
    relationships = [
        CandidateRelationship.model_validate(item.model_dump()) for item in case.expected.relationship_expectations
    ]
    entities = []
    for name, expected in dataset.canonical_entities.items():
        dimensions = tuple(
            CandidateDimension(name=item.name, business_name=item.business_name) for item in expected.dimensions
        )
        own_relationships = tuple(item for item in relationships if item.source_entity == name)
        entities.append(
            CandidateEntity(
                entity=name,
                business_name=expected.business_name,
                dimensions=dimensions,
                relationships=own_relationships,
            )
        )
    return CandidateEnrichmentOutput(entities=tuple(entities))


@pytest.mark.asyncio
async def test_perfect_enrichment_scores_one() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = dataset.discovery_cases[0]
    result = await evaluate_enrichment_case(
        case,
        dataset.canonical_entities,
        _perfect_candidate(dataset, case),
        EvaluationConfig(),
    )
    assert result.status == "passed"
    assert all(item.score == 1.0 for item in result.component_scores)
    names = [item for item in result.component_scores if item.text_similarity]
    assert names and all(item.text_similarity.semantic_status == "not_available" for item in names)


@pytest.mark.asyncio
async def test_missing_relationship_reduces_relationship_f1() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = dataset.discovery_cases[0]
    perfect = _perfect_candidate(dataset, case)
    entities = tuple(entity.model_copy(update={"relationships": ()}) for entity in perfect.entities or ())
    result = await evaluate_enrichment_case(
        case,
        dataset.canonical_entities,
        CandidateEnrichmentOutput(entities=entities),
        EvaluationConfig(),
    )
    relationships = next(item for item in result.component_scores if item.component == "relationships")
    assert result.status == "failed"
    assert relationships.metrics and relationships.metrics.recall == 0.0


@pytest.mark.asyncio
async def test_unexpected_dimension_fails_the_dimension_component() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = dataset.discovery_cases[0]
    perfect = _perfect_candidate(dataset, case)
    first = perfect.entities[0]
    dimensions = (*first.dimensions, CandidateDimension(name="hallucinated", business_name="Ảo"))
    changed = first.model_copy(update={"dimensions": dimensions})
    candidate = perfect.model_copy(update={"entities": (changed, *perfect.entities[1:])})
    result = await evaluate_enrichment_case(case, dataset.canonical_entities, candidate, EvaluationConfig())
    component = next(item for item in result.component_scores if item.component.endswith(".dimensions"))
    assert result.status == "failed"
    assert component.matched is False and component.score < 1.0
    assert any(issue.code == "UNEXPECTED_DIMENSION" for issue in result.issues)


@pytest.mark.asyncio
async def test_duplicate_dimension_cannot_receive_a_perfect_status() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = dataset.discovery_cases[0]
    perfect = _perfect_candidate(dataset, case)
    first = perfect.entities[0]
    changed = first.model_copy(update={"dimensions": (*first.dimensions, first.dimensions[0])})
    candidate = perfect.model_copy(update={"entities": (changed, *perfect.entities[1:])})
    result = await evaluate_enrichment_case(case, dataset.canonical_entities, candidate, EvaluationConfig())
    component = next(item for item in result.component_scores if item.component.endswith(".dimensions"))
    assert result.status == "failed" and component.matched is False
    assert any(issue.code == "DUPLICATE_DIMENSION" for issue in result.issues)


@pytest.mark.asyncio
async def test_relationship_flag_mismatch_has_specific_diagnostic() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = dataset.discovery_cases[0]
    perfect = _perfect_candidate(dataset, case)
    owner = next(entity for entity in perfect.entities if entity.relationships)
    changed_relationship = owner.relationships[0].model_copy(update={"inferred": True})
    changed_owner = owner.model_copy(update={"relationships": (changed_relationship, *owner.relationships[1:])})
    entities = tuple(changed_owner if entity.entity == owner.entity else entity for entity in perfect.entities)
    result = await evaluate_enrichment_case(
        case, dataset.canonical_entities, perfect.model_copy(update={"entities": entities}), EvaluationConfig()
    )
    assert result.status == "failed"
    assert any(issue.code == "RELATIONSHIP_INFERRED_MISMATCH" for issue in result.issues)


@pytest.mark.asyncio
async def test_provider_failure_preserves_all_suite_cases() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    candidates = {case.case_id: _perfect_candidate(dataset, case) for case in dataset.discovery_cases[:2]}
    result = await evaluate_enrichment_suite(dataset, candidates, EvaluationConfig(), FailingProvider())
    assert len(result.cases) == 4
    assert [case.status for case in result.cases].count("error") == 2
    assert [case.status for case in result.cases].count("skipped") == 2
