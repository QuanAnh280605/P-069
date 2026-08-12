"""Evaluate schema business names and inferred or declared relationships."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eval.dataset.loader import DomainDataset
from eval.dataset.models import CanonicalEntityDefinition, DiscoveryCase, RelationshipExpectation
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result
from eval.evaluator.schemas import (
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateRelationship,
    CaseEvaluationResult,
    CaseStatus,
    EvaluationConfig,
    EvaluationIssue,
    FieldScore,
    SuiteEvaluationResult,
    TextSimilarityScore,
)
from eval.evaluator.scoring import SetMatchResult, match_sets, micro_average
from eval.evaluator.text_similarity import TextSimilarityProvider, compare_business_name


async def evaluate_enrichment_case(
    case: DiscoveryCase,
    canonical_entities: Mapping[str, CanonicalEntityDefinition],
    candidate: CandidateEnrichmentOutput,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None = None,
) -> CaseEvaluationResult:
    """Evaluate one discovery candidate without mutating dataset artifacts."""
    if candidate.error_code is not None:
        return _candidate_error(case, candidate.error_code)
    try:
        entity_score, entity_issues = _score_entities(case, candidate)
        name_scores, name_issues = await _score_names(canonical_entities, candidate, config, provider)
        relationship_score, relationship_issues = _score_relationships(case, candidate)
    except Exception as exc:  # provider boundary must isolate case failures
        issue = EvaluationIssue(code="EVALUATOR_ERROR", message=type(exc).__name__)
        return CaseEvaluationResult(case_id=case.case_id, status="error", issues=(issue,), tags=tuple(case.tags))
    components = (entity_score, *name_scores, relationship_score)
    issues = (*entity_issues, *name_issues, *relationship_issues)
    status: CaseStatus = "passed" if all(item.matched for item in components) else "failed"
    return CaseEvaluationResult(
        case_id=case.case_id,
        status=status,
        component_scores=components,
        issues=issues,
        tags=tuple(case.tags),
    )


async def evaluate_enrichment_suite(
    dataset: DomainDataset,
    candidates: Mapping[str, CandidateEnrichmentOutput],
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None = None,
) -> SuiteEvaluationResult:
    """Evaluate all supplied discovery cases and aggregate available scores."""
    results: list[CaseEvaluationResult] = []
    for case in dataset.discovery_cases:
        candidate = candidates.get(case.case_id)
        results.append(await _evaluate_or_skip(case, dataset, candidate, config, provider))
    relationship = [_relationship_component(result) for result in results]
    counts = [item.counts for item in relationship if item and item.counts]
    return build_suite_result(
        SuiteBuildInput(
            dataset=dataset,
            results=tuple(results),
            config=config,
            micro=micro_average(counts) if counts else None,
        )
    )


async def _score_names(
    canonical: Mapping[str, CanonicalEntityDefinition],
    candidate: CandidateEnrichmentOutput,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> tuple[tuple[FieldScore, ...], tuple[EvaluationIssue, ...]]:
    actual = {entity.entity: entity for entity in candidate.entities or ()}
    scores: list[FieldScore] = []
    issues: list[EvaluationIssue] = []
    for name, expected in sorted(canonical.items()):
        entity = actual.get(name)
        if entity is None:
            scores.append(FieldScore(component=f"entity.{name}.business_name", score=0.0, matched=False))
            issues.append(_issue("MISSING_ENTITY", "entity", name, None))
            continue
        labels = (expected.business_name, *expected.accepted_business_names, *expected.synonyms)
        result = await compare_business_name(entity.business_name, labels, config, provider)
        scores.append(_name_field_score(f"entity.{name}.business_name", result))
        if not result.accepted:
            issues.append(
                _issue("BUSINESS_NAME_MISMATCH", f"entity.{name}.business_name", labels[0], entity.business_name)
            )
        await _score_dimensions(expected, entity, config, provider, scores, issues)
    return tuple(scores), tuple(issues)


async def _score_dimensions(
    expected: CanonicalEntityDefinition,
    entity: CandidateEntity,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
    scores: list[FieldScore],
    issues: list[EvaluationIssue],
) -> None:
    dimension_names = tuple(dimension.name for dimension in entity.dimensions)
    actual = {dimension.name: dimension for dimension in entity.dimensions}
    expected_names = tuple(dimension.name for dimension in expected.dimensions)
    dimension_match = match_sets(expected_names, dimension_names)
    scores.append(_dimension_set_score(expected.entity, dimension_match))
    for name in sorted(set(dimension_names) - set(expected_names)):
        issues.append(_issue("UNEXPECTED_DIMENSION", "dimensions", None, name))
    for name in _duplicates(dimension_names):
        issues.append(_issue("DUPLICATE_DIMENSION", "dimensions", None, name))
    for dimension in expected.dimensions:
        candidate = actual.get(dimension.name)
        component = f"dimension.{expected.entity}.{dimension.name}.business_name"
        if candidate is None:
            scores.append(FieldScore(component=component, score=0.0, matched=False))
            issues.append(_issue("MISSING_DIMENSION", component, dimension.name, None))
            continue
        labels = (dimension.business_name, *dimension.synonyms)
        result = await compare_business_name(candidate.business_name, labels, config, provider)
        scores.append(_name_field_score(component, result))
        if not result.accepted:
            issues.append(_issue("BUSINESS_NAME_MISMATCH", component, dimension.business_name, candidate.business_name))


def _dimension_set_score(entity: str, matched: SetMatchResult) -> FieldScore:
    diagnostics = tuple(f"duplicate dimension: {item}" for item in matched.duplicates)
    return FieldScore(
        component=f"entity.{entity}.dimensions",
        score=matched.metrics.f1,
        matched=matched.metrics.f1 == 1.0 and not matched.duplicates,
        counts=matched.counts,
        metrics=matched.metrics,
        diagnostics=diagnostics,
    )


def _score_entities(
    case: DiscoveryCase,
    candidate: CandidateEnrichmentOutput,
) -> tuple[FieldScore, tuple[EvaluationIssue, ...]]:
    expected = tuple(Path(reference).stem for reference in case.expected.entity_refs)
    actual = tuple(entity.entity for entity in candidate.entities or ())
    matched = match_sets(expected, actual)
    diagnostics = tuple(f"duplicate entity: {item}" for item in matched.duplicates)
    score = FieldScore(
        component="entities",
        score=matched.metrics.f1,
        matched=matched.metrics.f1 == 1.0 and not matched.duplicates,
        counts=matched.counts,
        metrics=matched.metrics,
        diagnostics=diagnostics,
    )
    issues = [_issue("MISSING_ENTITY", "entities", item, None) for item in set(expected) - set(actual)]
    issues.extend(_issue("UNEXPECTED_ENTITY", "entities", None, item) for item in set(actual) - set(expected))
    issues.extend(_issue("DUPLICATE_ENTITY", "entities", None, item) for item in matched.duplicates)
    return score, tuple(issues)


def _score_relationships(
    case: DiscoveryCase,
    candidate: CandidateEnrichmentOutput,
) -> tuple[FieldScore, tuple[EvaluationIssue, ...]]:
    expected = tuple(_relationship_key(item) for item in case.expected.relationship_expectations)
    relationships = tuple(item for entity in candidate.entities or () for item in entity.relationships)
    actual = tuple(_relationship_key(item) for item in relationships)
    matched = match_sets(expected, actual)
    diagnostics = tuple(f"duplicate relationship: {item!r}" for item in matched.duplicates)
    score = FieldScore(
        component="relationships",
        score=matched.metrics.f1,
        matched=matched.metrics.f1 == 1.0 and not matched.duplicates,
        counts=matched.counts,
        metrics=matched.metrics,
        diagnostics=diagnostics,
    )
    issues = _relationship_issues(set(expected), set(actual), matched.duplicates)
    return score, issues


def _relationship_issues(expected: set[tuple], actual: set[tuple], duplicates: tuple) -> tuple[EvaluationIssue, ...]:
    missing = expected - actual
    unexpected = actual - expected
    issues = [_issue("MISSING_RELATIONSHIP", "relationships", list(item), None) for item in sorted(missing)]
    issues.extend(_issue("UNEXPECTED_RELATIONSHIP", "relationships", None, list(item)) for item in sorted(unexpected))
    issues.extend(_relationship_mismatch_issues(missing, unexpected))
    issues.extend(_issue("DUPLICATE_RELATIONSHIP", "relationships", None, list(item)) for item in duplicates)
    return tuple(issues)


def _relationship_mismatch_issues(expected: set[tuple], actual: set[tuple]) -> tuple[EvaluationIssue, ...]:
    issues: list[EvaluationIssue] = []
    for wanted in sorted(expected):
        for received in sorted(actual):
            code = _relationship_mismatch_code(wanted, received)
            if code is not None:
                issues.append(_issue(code, "relationships", list(wanted), list(received)))
    return tuple(issues)


def _relationship_mismatch_code(expected: tuple, actual: tuple) -> str | None:
    if expected[:4] == actual[:4] and expected[4] != actual[4]:
        return "RELATIONSHIP_TYPE_MISMATCH"
    if expected[:5] == actual[:5] and expected[5] != actual[5]:
        return "RELATIONSHIP_INFERRED_MISMATCH"
    same_entities = expected[0] == actual[0] and expected[2] == actual[2]
    if same_entities and expected[1:4:2] != actual[1:4:2]:
        return "RELATIONSHIP_FIELD_MISMATCH"
    return None


def _relationship_key(
    item: RelationshipExpectation | CandidateRelationship,
) -> tuple[str, str, str, str, str, bool]:
    return (
        item.source_entity,
        item.source_field,
        item.target_entity,
        item.target_field,
        item.relation_type,
        item.inferred,
    )


def _name_field_score(component: str, result: TextSimilarityScore) -> FieldScore:
    return FieldScore(
        component=component,
        score=float(result.accepted),
        matched=result.accepted,
        text_similarity=result,
    )


def _candidate_error(case: DiscoveryCase, error_code: str) -> CaseEvaluationResult:
    issue = EvaluationIssue(code="CANDIDATE_ERROR", message="Candidate returned an error", actual=error_code)
    return CaseEvaluationResult(case_id=case.case_id, status="failed", issues=(issue,), tags=tuple(case.tags))


def _issue(code: str, field: str, expected: Any, actual: Any) -> EvaluationIssue:
    return EvaluationIssue(
        code=code, message=code.replace("_", " ").title(), field=field, expected=expected, actual=actual
    )


async def _evaluate_or_skip(
    case: DiscoveryCase,
    dataset: DomainDataset,
    candidate: CandidateEnrichmentOutput | None,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> CaseEvaluationResult:
    if candidate is None:
        return CaseEvaluationResult(case_id=case.case_id, status="skipped", tags=tuple(case.tags))
    return await evaluate_enrichment_case(case, dataset.canonical_entities, candidate, config, provider)


def _relationship_component(result: CaseEvaluationResult) -> FieldScore | None:
    return next((item for item in result.component_scores if item.component == "relationships"), None)


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))
