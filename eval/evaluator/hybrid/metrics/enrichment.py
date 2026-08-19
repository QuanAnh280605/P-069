"""Deterministic enrichment metrics (spec §7.2)."""

from __future__ import annotations

from eval.dataset.models import CanonicalEntityDefinition
from eval.evaluator.enrichment_eval import _relationship_key
from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.base import (
    CandidateFailure,
    DeterministicMetric,
    reference_as,
    response_as,
    score_result,
    set_match_result,
)
from eval.evaluator.hybrid.samples import EnrichmentReference, EvaluationSample
from eval.evaluator.schemas import CandidateEnrichmentOutput, CandidateEntity, MatchCounts
from eval.evaluator.scoring import match_sets, micro_average
from eval.evaluator.text_similarity import TextSimilarityScore, compare_business_name


def build_enrichment_metrics(specs: tuple[MetricSpec, ...]) -> dict[str, DeterministicMetric]:
    """Instantiate deterministic enrichment metrics from catalog specs."""
    factory = {
        "entity_f1": EntityF1,
        "dimension_f1": DimensionF1,
        "relationship_accuracy": RelationshipAccuracy,
        "business_name_similarity": BusinessNameSimilarity,
    }
    return {spec.name: factory[spec.name](spec) for spec in specs if spec.name in factory}


def _payload(sample: EvaluationSample) -> tuple[EnrichmentReference, tuple[CandidateEntity, ...]]:
    reference = reference_as(sample, EnrichmentReference)
    response = response_as(sample, CandidateEnrichmentOutput)
    if response.entities is None:
        raise CandidateFailure(response.error_code or "no entities")
    return reference, response.entities


class EntityF1(DeterministicMetric):
    """Match discovered entity names against golden entity references."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, entities = _payload(sample)
        match = match_sets(reference.entity_refs, tuple(entity.entity for entity in entities))
        return set_match_result(self.spec, sample.sample_id, match)


class DimensionF1(DeterministicMetric):
    """Micro-match dimensions per canonical entity."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, entities = _payload(sample)
        by_name = {entity.entity: entity for entity in entities}
        counts = tuple(_entity_counts(entity, by_name.get(entity.entity)) for entity in reference.canonical_entities)
        average = micro_average(counts) if counts else None
        return score_result(self.spec, sample.sample_id, average.f1 if average else 1.0)


def _entity_counts(expected: CanonicalEntityDefinition, actual: CandidateEntity | None) -> MatchCounts:
    expected_names = tuple(dimension.name for dimension in expected.dimensions)
    actual_names = tuple(dimension.name for dimension in actual.dimensions) if actual else ()
    return match_sets(expected_names, actual_names).counts


class RelationshipAccuracy(DeterministicMetric):
    """Match relationship tuples against golden expectations."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, entities = _payload(sample)
        expected = tuple(_relationship_key(item) for item in reference.relationship_expectations)
        actual = tuple(_relationship_key(item) for entity in entities for item in entity.relationships)
        return set_match_result(self.spec, sample.sample_id, match_sets(expected, actual))


class BusinessNameSimilarity(DeterministicMetric):
    """Average deterministic name similarity across entities and dimensions."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, entities = _payload(sample)
        by_name = {entity.entity: entity for entity in entities}
        scores: list[float] = []
        for canonical in reference.canonical_entities:
            entity = by_name.get(canonical.entity)
            labels = (canonical.business_name, *canonical.accepted_business_names, *canonical.synonyms)
            scores.append(0.0 if entity is None else await _best(entity.business_name, labels, context))
            scores.extend(await _dimension_scores(canonical, entity, context))
        similarity = sum(scores) / len(scores) if scores else 1.0
        return score_result(self.spec, sample.sample_id, similarity)


async def _dimension_scores(
    canonical: CanonicalEntityDefinition,
    entity: CandidateEntity | None,
    context: EvaluationContext,
) -> list[float]:
    if entity is None:
        return [0.0 for _ in canonical.dimensions]
    by_name = {dimension.name: dimension for dimension in entity.dimensions}
    values = []
    for dimension in canonical.dimensions:
        candidate = by_name.get(dimension.name)
        labels = (dimension.business_name, *dimension.synonyms)
        values.append(0.0 if candidate is None else await _best(candidate.business_name, labels, context))
    return values


async def _best(actual: str, labels: tuple[str, ...], context: EvaluationContext) -> float:
    result: TextSimilarityScore = await compare_business_name(actual, labels, context.config, context.text_provider)
    semantic = result.semantic_similarity or 0.0
    return max(result.exact_match, result.fuzzy_similarity, semantic)
