"""Evaluate generated metric definitions with identity and field diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import JsonValue

from eval.dataset.loader import DomainDataset
from eval.dataset.models import ExpectedMetricDefinition, MetricDefinitionCase
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result
from eval.evaluator.schemas import (
    CandidateMetricDefinition,
    CandidateMetricOutput,
    CaseEvaluationResult,
    CaseStatus,
    EvaluationConfig,
    EvaluationIssue,
    FieldScore,
    MatchCounts,
    SuiteEvaluationResult,
)
from eval.evaluator.scoring import micro_average, precision_recall_f1
from eval.evaluator.sql_normalization import normalize_expression
from eval.evaluator.text_similarity import TextSimilarityProvider, compare_business_name, normalize_text

_SET_FIELDS = {"synonyms", "dependencies", "allowed_dimensions"}
_TEXT_FIELDS = {"business_name", "description", "business_formula"}
_FIELDS = (
    "name",
    "business_name",
    "metric_type",
    "target_entity",
    "source_table",
    "aggregation",
    "field",
    "business_formula",
    "sql_expression",
    "dependencies",
    "default_filters",
    "allowed_dimensions",
    "default_time_grain",
    "expected_preview_facts",
)


async def evaluate_metric_case(
    case: MetricDefinitionCase,
    candidate: CandidateMetricOutput,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None = None,
) -> CaseEvaluationResult:
    """Evaluate one metric-definition success or negative case."""
    outcome = _evaluate_outcome(case, candidate)
    if outcome is not None:
        return outcome
    expected = case.expected_metric
    actual = candidate.metric
    assert expected is not None and actual is not None
    try:
        fields, issues = await _score_fields(case, expected, actual, config, provider)
    except Exception as exc:
        issue = EvaluationIssue(code="EVALUATOR_ERROR", message=type(exc).__name__)
        return CaseEvaluationResult(case_id=case.case_id, status="error", issues=(issue,), tags=tuple(case.tags))
    identity = _identity_score(expected, actual)
    components = (identity, *fields)
    status: CaseStatus = "passed" if all(item.matched for item in components) else "failed"
    return CaseEvaluationResult(
        case_id=case.case_id, status=status, component_scores=components, issues=issues, tags=tuple(case.tags)
    )


async def evaluate_metric_suite(
    dataset: DomainDataset,
    candidates: Mapping[str, CandidateMetricOutput],
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None = None,
) -> SuiteEvaluationResult:
    """Evaluate metric candidates and preserve missing cases as skipped."""
    results: list[CaseEvaluationResult] = []
    for case in dataset.metric_cases:
        candidate = candidates.get(case.case_id)
        result = await evaluate_metric_case(case, candidate, config, provider) if candidate else _skipped(case)
        results.append(result)
    identities = [item for result in results for item in result.component_scores if item.component == "core_identity"]
    counts = [item.counts for item in identities if item.counts]
    return build_suite_result(
        SuiteBuildInput(
            dataset=dataset,
            results=tuple(results),
            config=config,
            micro=micro_average(counts) if counts else None,
        )
    )


def _evaluate_outcome(case: MetricDefinitionCase, candidate: CandidateMetricOutput) -> CaseEvaluationResult | None:
    if case.expected_error is not None and candidate.error_code is not None:
        matched = case.expected_error == candidate.error_code
        component = FieldScore(component="outcome", score=float(matched), matched=matched)
        issues = () if matched else (_wrong_outcome(case.expected_error, candidate.error_code),)
        return CaseEvaluationResult(
            case_id=case.case_id,
            status="passed" if matched else "failed",
            component_scores=(component,),
            issues=issues,
            tags=tuple(case.tags),
        )
    if case.expected_error is not None or candidate.error_code is not None:
        expected = case.expected_error or "metric"
        actual = candidate.error_code or "metric"
        component = FieldScore(component="outcome", score=0.0, matched=False)
        return CaseEvaluationResult(
            case_id=case.case_id,
            status="failed",
            component_scores=(component,),
            issues=(_wrong_outcome(expected, actual),),
            tags=tuple(case.tags),
        )
    return None


async def _score_fields(
    case: MetricDefinitionCase,
    expected: ExpectedMetricDefinition,
    actual: CandidateMetricDefinition,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> tuple[tuple[FieldScore, ...], tuple[EvaluationIssue, ...]]:
    scores: list[FieldScore] = []
    issues: list[EvaluationIssue] = []
    for field in _FIELDS:
        expected_value = case.expected_preview_facts if field == "expected_preview_facts" else getattr(expected, field)
        actual_value = actual.expected_preview_facts if field == "expected_preview_facts" else getattr(actual, field)
        matched = await _field_equal(field, expected_value, actual_value, config, provider)
        duplicates = _field_duplicates(field, actual_value)
        diagnostics = tuple(f"duplicate value: {value}" for value in duplicates)
        scores.append(FieldScore(component=field, score=float(matched), matched=matched, diagnostics=diagnostics))
        if not matched:
            issues.append(_field_issue(field, expected_value, actual_value))
        issues.extend(
            EvaluationIssue(
                code="DUPLICATE_VALUE", message="Candidate field contains duplicates", field=field, actual=value
            )
            for value in duplicates
        )
    return tuple(scores), tuple(issues)


def _field_issue(field: str, expected: Any, actual: Any) -> EvaluationIssue:
    return EvaluationIssue(
        code="FIELD_MISMATCH",
        message="Metric field differs",
        field=field,
        expected=_safe(expected),
        actual=_safe(actual),
    )


async def _field_equal(
    field: str,
    expected: Any,
    actual: Any,
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> bool:
    if field in _TEXT_FIELDS:
        result = await compare_business_name(str(actual), (str(expected),), config, provider)
        return result.accepted
    if field == "expected_preview_facts":
        return await _text_sets_equal(expected, actual, config, provider)
    if field in _SET_FIELDS:
        return {_normalized_scalar(value) for value in expected} == {_normalized_scalar(value) for value in actual}
    if field == "default_filters":
        return {_filter(item.condition) for item in expected} == {_filter(item.condition) for item in actual}
    if field == "sql_expression":
        return normalize_expression(str(expected)) == normalize_expression(str(actual))
    return expected == actual


async def _text_sets_equal(
    expected: tuple[str, ...] | list[str],
    actual: tuple[str, ...] | list[str],
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> bool:
    if len(expected) != len(actual):
        return False
    remaining = list(actual)
    for expected_item in expected:
        matched = await _matching_text_index(expected_item, remaining, config, provider)
        if matched is None:
            return False
        remaining.pop(matched)
    return not remaining


async def _matching_text_index(
    expected: str,
    actual: list[str],
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None,
) -> int | None:
    matches: list[tuple[tuple[float, float], int]] = []
    for index, candidate in enumerate(actual):
        result = await compare_business_name(candidate, (expected,), config, provider)
        if result.accepted:
            semantic = result.semantic_similarity or 0.0
            matches.append(((result.exact_match, max(result.fuzzy_similarity, semantic)), index))
    return max(matches)[1] if matches else None


def _identity_score(expected: ExpectedMetricDefinition, actual: CandidateMetricDefinition) -> FieldScore:
    matched = _identity(expected) == _identity(actual)
    counts = MatchCounts(true_positive=int(matched), false_positive=int(not matched), false_negative=int(not matched))
    metrics = precision_recall_f1(counts)
    return FieldScore(component="core_identity", score=metrics.f1, matched=matched, counts=counts, metrics=metrics)


def _identity(metric: ExpectedMetricDefinition | CandidateMetricDefinition) -> tuple[Any, ...]:
    expression = normalize_expression(metric.sql_expression) if metric.field is None else None
    dependencies = tuple(sorted(set(metric.dependencies))) if metric.field is None else ()
    filters = tuple(sorted({_filter(item.condition) for item in metric.default_filters}))
    return metric.target_entity, metric.aggregation, metric.field, expression, dependencies, filters


def _filter(value: str) -> str:
    return normalize_expression(value)


def _normalized_scalar(value: object) -> str:
    return normalize_text(str(value))


def _field_duplicates(field: str, value: Any) -> tuple[str, ...]:
    if field in _SET_FIELDS or field == "expected_preview_facts":
        normalized = tuple(_normalized_scalar(item) for item in value)
    elif field == "default_filters":
        normalized = tuple(_filter(item.condition) for item in value)
    else:
        return ()
    return tuple(sorted({item for item in normalized if normalized.count(item) > 1}))


def _safe(value: Any) -> JsonValue:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, tuple | list):
        return [str(item) for item in value]
    return str(value)


def _wrong_outcome(expected: str, actual: str) -> EvaluationIssue:
    return EvaluationIssue(
        code="WRONG_OUTCOME", message="Candidate outcome differs", field="outcome", expected=expected, actual=actual
    )


def _skipped(case: MetricDefinitionCase) -> CaseEvaluationResult:
    return CaseEvaluationResult(case_id=case.case_id, status="skipped", tags=tuple(case.tags))
