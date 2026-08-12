"""Evaluate Canonical Query Models, SQL, execution and guardrail behavior."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import JsonValue

from eval.dataset.loader import DomainDataset
from eval.dataset.models import Dialect, GuardrailCase, QueryCase
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result
from eval.evaluator.execution import EvaluationExecutionError, compare_query_result, execute_guarded_sql
from eval.evaluator.schemas import (
    CandidateCanonicalQuery,
    CandidateCompilerOutput,
    CandidateGuardrailOutput,
    CaseEvaluationResult,
    CaseStatus,
    EvaluationConfig,
    EvaluationIssue,
    FieldScore,
    SuiteEvaluationResult,
)
from eval.evaluator.sql_normalization import SqlValidationError, structurally_equal

_CQM_FIELDS = (
    "intent",
    "domain",
    "primary_entity",
    "metrics",
    "dimensions",
    "time_filters",
    "where_conditions",
    "entities_in_path",
)


class GuardrailAdapter(Protocol):
    """Validate candidate SQL through the real system-under-test guardrail."""

    async def validate(self, sql: str, dialect: Dialect) -> CandidateGuardrailOutput:
        """Return a typed guardrail decision and transformed SQL."""
        ...


async def evaluate_compiler_case(
    case: QueryCase,
    candidate: CandidateCompilerOutput,
    dataset: DomainDataset,
    config: EvaluationConfig,
    guardrail_adapter: GuardrailAdapter | None = None,
) -> CaseEvaluationResult:
    """Evaluate one compiler output with optional guarded SQLite execution."""
    outcome = _compiler_outcome(case, candidate)
    if outcome is not None:
        return outcome
    assert case.expected and candidate.canonical_query and candidate.sql
    cqm_scores, issues = _score_cqm(case, candidate.canonical_query)
    ast_score, ast_issue = _score_ast(case.expected.sql_by_dialect[config.execution_dialect], candidate.sql)
    if ast_issue:
        issues.append(ast_issue)
    execution_score, execution_issue = await _score_execution(case, candidate.sql, dataset, config, guardrail_adapter)
    if execution_issue:
        issues.append(execution_issue)
    components = (*cqm_scores, ast_score, execution_score)
    available = [item for item in components if item.status != "not_available"]
    status: CaseStatus = "passed" if all(item.matched for item in available) else "failed"
    return CaseEvaluationResult(
        case_id=case.case_id, status=status, component_scores=components, issues=tuple(issues), tags=tuple(case.tags)
    )


async def evaluate_compiler_suite(
    dataset: DomainDataset,
    candidates: Mapping[str, CandidateCompilerOutput],
    config: EvaluationConfig,
    guardrail_adapter: GuardrailAdapter | None = None,
) -> SuiteEvaluationResult:
    """Evaluate all query cases while isolating individual candidate failures."""
    results: list[CaseEvaluationResult] = []
    for case in dataset.query_cases:
        candidate = candidates.get(case.case_id)
        if candidate is None:
            results.append(CaseEvaluationResult(case_id=case.case_id, status="skipped", tags=tuple(case.tags)))
            continue
        try:
            results.append(await evaluate_compiler_case(case, candidate, dataset, config, guardrail_adapter))
        except Exception as exc:
            issue = EvaluationIssue(code="EVALUATOR_ERROR", message=type(exc).__name__)
            results.append(
                CaseEvaluationResult(case_id=case.case_id, status="error", issues=(issue,), tags=tuple(case.tags))
            )
    return _suite_result(dataset, results, config)


async def evaluate_guardrail_case(case: GuardrailCase, adapter: GuardrailAdapter) -> CaseEvaluationResult:
    """Score one guardrail decision without executing its SQL."""
    try:
        actual = await adapter.validate(case.sql, case.dialect)
    except Exception as exc:
        issue = EvaluationIssue(code="ADAPTER_ERROR", message=type(exc).__name__)
        return CaseEvaluationResult(case_id=case.case_id, status="error", issues=(issue,), tags=tuple(case.tags))
    expected = case.expected
    comparisons = {
        "accepted": expected.accepted == actual.accepted,
        "error_code": expected.error_code == actual.error_code,
        "effective_limit": expected.expected_limit == actual.effective_limit,
        "effective_timeout": expected.expected_timeout_seconds == actual.effective_timeout_seconds,
    }
    components = tuple(
        FieldScore(component=name, score=float(value), matched=value) for name, value in comparisons.items()
    )
    issues = tuple(_mismatch(name) for name, matched in comparisons.items() if not matched)
    status: CaseStatus = "passed" if all(comparisons.values()) else "failed"
    return CaseEvaluationResult(
        case_id=case.case_id, status=status, component_scores=components, issues=issues, tags=tuple(case.tags)
    )


async def evaluate_guardrail_suite(
    dataset: DomainDataset,
    adapter: GuardrailAdapter,
    config: EvaluationConfig | None = None,
) -> SuiteEvaluationResult:
    """Evaluate every dataset guardrail case via the injected runtime adapter."""
    results = [await evaluate_guardrail_case(case, adapter) for case in dataset.guardrail_cases]
    return _suite_result(dataset, results, config or EvaluationConfig())


def _compiler_outcome(case: QueryCase, candidate: CandidateCompilerOutput) -> CaseEvaluationResult | None:
    if case.expected_error is None and candidate.error_code is None:
        return None
    matched = case.expected_error is not None and case.expected_error == candidate.error_code
    component = FieldScore(component="outcome", score=float(matched), matched=matched)
    issues = () if matched else (_mismatch("outcome", case.expected_error, candidate.error_code),)
    return CaseEvaluationResult(
        case_id=case.case_id,
        status="passed" if matched else "failed",
        component_scores=(component,),
        issues=issues,
        tags=tuple(case.tags),
    )


def _score_cqm(
    case: QueryCase, actual: CandidateCanonicalQuery
) -> tuple[tuple[FieldScore, ...], list[EvaluationIssue]]:
    assert case.expected is not None
    expected = case.expected.canonical_query
    scores: list[FieldScore] = []
    issues: list[EvaluationIssue] = []
    for field in _CQM_FIELDS:
        expected_value = _normalize_cqm_field(field, getattr(expected, field))
        actual_value = _normalize_cqm_field(field, getattr(actual, field))
        matched = expected_value == actual_value
        duplicates = _cqm_duplicates(field, getattr(actual, field))
        diagnostics = tuple(f"duplicate value: {value!r}" for value in duplicates)
        scores.append(
            FieldScore(component=f"cqm.{field}", score=float(matched), matched=matched, diagnostics=diagnostics)
        )
        if not matched:
            issues.append(_mismatch(f"cqm.{field}", expected_value, actual_value))
        issues.extend(
            EvaluationIssue(code="DUPLICATE_VALUE", message="CQM collection contains duplicates", field=field)
            for _ in duplicates
        )
    exact = all(item.matched for item in scores)
    scores.append(FieldScore(component="cqm.exact", score=float(exact), matched=exact))
    return tuple(scores), issues


def _normalize_cqm_field(field: str, value: Any) -> Any:
    if field in {"metrics", "dimensions"}:
        return tuple(sorted(set(value)))
    if field in {"time_filters", "where_conditions"}:
        dumped = (item.model_dump(mode="json") for item in value)
        return tuple(sorted((_freeze(item) for item in dumped), key=repr))
    if field == "entities_in_path":
        return tuple(value)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _cqm_duplicates(field: str, value: Any) -> tuple[Any, ...]:
    if field not in {"metrics", "dimensions", "time_filters", "where_conditions"}:
        return ()
    normalized = tuple(_freeze(item.model_dump(mode="json")) if hasattr(item, "model_dump") else item for item in value)
    return tuple(sorted({item for item in normalized if normalized.count(item) > 1}, key=repr))


def _score_ast(expected: str, actual: str) -> tuple[FieldScore, EvaluationIssue | None]:
    try:
        matched = structurally_equal(expected, actual, "sqlite")
    except SqlValidationError as exc:
        score = FieldScore(component="sql_ast", status="failed", score=0.0, matched=False)
        return score, EvaluationIssue(code="UNSAFE_OR_INVALID_SQL", message=str(exc), field="sql")
    score = FieldScore(component="sql_ast", score=float(matched), matched=matched)
    return score, None if matched else _mismatch("sql_ast")


async def _score_execution(
    case: QueryCase,
    sql: str,
    dataset: DomainDataset,
    config: EvaluationConfig,
    adapter: GuardrailAdapter | None,
) -> tuple[FieldScore, EvaluationIssue | None]:
    if adapter is None:
        return FieldScore(component="execution", status="not_available"), None
    assert case.expected is not None
    try:
        guarded = await adapter.validate(sql, "sqlite")
        source = dataset.domain_dir / "sources" / "sqlite"
        result = await execute_guarded_sql(sql, source / "schema.sql", source / "seed_data.sql", guarded, config)
        expected = dataset.expected_query_results[case.expected.result_ref]
        matched = compare_query_result(result, expected, config)
    except (EvaluationExecutionError, KeyError, SqlValidationError) as exc:
        score = FieldScore(component="execution", status="failed", score=0.0, matched=False)
        return score, EvaluationIssue(code="EXECUTION_FAILED", message=str(exc), field="execution")
    score = FieldScore(component="execution", score=float(matched), matched=matched)
    return score, None if matched else _mismatch("execution")


def _suite_result(
    dataset: DomainDataset,
    results: list[CaseEvaluationResult],
    config: EvaluationConfig,
) -> SuiteEvaluationResult:
    return build_suite_result(SuiteBuildInput(dataset=dataset, results=tuple(results), config=config))


def _mismatch(field: str, expected: Any = None, actual: Any = None) -> EvaluationIssue:
    return EvaluationIssue(
        code="FIELD_MISMATCH",
        message="Evaluated field differs",
        field=field,
        expected=_safe(expected),
        actual=_safe(actual),
    )


def _safe(value: Any) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
