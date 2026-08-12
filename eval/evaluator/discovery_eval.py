"""Schema-extraction fidelity evaluator for the discovery stage (live mode)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from eval.dataset.loader import DomainDataset
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result
from eval.evaluator.schemas import (
    CaseEvaluationResult,
    EvaluationConfig,
    EvaluationIssue,
    FieldScore,
    MatchCounts,
    SuiteEvaluationResult,
)
from eval.evaluator.scoring import match_sets, precision_recall_f1

__all__ = ["CandidateDiscoveryOutput", "evaluate_discovery_suite"]


class CandidateDiscoveryOutput(BaseModel):
    """Candidate schema-extraction output: a RawSchema or an error code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_schema: dict[str, Any] | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> CandidateDiscoveryOutput:
        """Require exactly one of raw_schema or error_code."""
        if (self.raw_schema is None) == (self.error_code is None):
            raise ValueError("Provide exactly one of raw_schema or error_code.")
        return self


async def evaluate_discovery_suite(
    dataset: DomainDataset,
    candidates: Mapping[str, CandidateDiscoveryOutput],
    config: EvaluationConfig,
) -> SuiteEvaluationResult:
    """Score schema-extraction fidelity per discovery case vs golden fixtures."""
    results = tuple(_evaluate_case(case, dataset.raw_schemas, candidates) for case in dataset.discovery_cases)
    return build_suite_result(SuiteBuildInput(dataset=dataset, results=results, config=config))


def _evaluate_case(
    case: Any,
    raw_schemas: Mapping[str, dict[str, Any]],
    candidates: Mapping[str, CandidateDiscoveryOutput],
) -> CaseEvaluationResult:
    """Score one discovery case against its golden raw-schema fixture."""
    candidate = candidates.get(case.case_id)
    if candidate is None:
        return _issue_result(case, "not_available", "NO_CANDIDATE", "No candidate provided for discovery case.")
    if candidate.error_code is not None:
        return _issue_result(case, "error", candidate.error_code, "Introspection reported an error.")
    components = _score_components(raw_schemas[case.raw_schema_ref], candidate.raw_schema or {})
    status = "passed" if all(item.matched for item in components) else "failed"
    return _result(case, status, components=components)


def _result(
    case: Any,
    status: str,
    components: tuple[FieldScore, ...] = (),
    issues: tuple[EvaluationIssue, ...] = (),
) -> CaseEvaluationResult:
    """Assemble a CaseEvaluationResult for one discovery case."""
    return CaseEvaluationResult(
        case_id=case.case_id,
        status=status,
        component_scores=components,
        issues=issues,
        tags=tuple(case.tags),
    )


def _issue_result(
    case: Any,
    status: str,
    code: str,
    message: str,
) -> CaseEvaluationResult:
    """Build a case result carrying a single structured issue."""
    return _result(case, status, issues=(EvaluationIssue(code=code, message=message),))


def _score_components(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[FieldScore, ...]:
    """Compare tables, columns, primary keys and relationships."""
    exp_tables = _table_map(expected)
    act_tables = _table_map(actual)
    return (
        _set_score("tables", set(exp_tables), set(act_tables)),
        _micro_score("columns", exp_tables, act_tables, _column_names),
        _micro_score("primary_keys", exp_tables, act_tables, _primary_keys),
        _set_score("relationships", _rel_tuples(expected), _rel_tuples(actual)),
    )


def _table_map(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map table name to table dict from a RawSchema."""
    return {table["table_name"]: table for table in raw.get("tables", [])}


def _column_names(table: dict[str, Any]) -> set[str]:
    """Extract the set of column names from a table dict."""
    return {column["column_name"] for column in table.get("columns", [])}


def _primary_keys(table: dict[str, Any]) -> set[str]:
    """Extract the set of primary-key column names from a table dict."""
    return set(table.get("primary_keys", []))


def _rel_tuples(raw: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """Flatten relationship rows to hashable endpoint tuples."""
    return {
        (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])
        for rel in raw.get("relationships", [])
    }


def _set_score(component: str, expected: set, actual: set) -> FieldScore:
    """Build a FieldScore from a single set match."""
    result = match_sets(expected, actual)
    matched = result.metrics.f1 == 1.0 and not result.duplicates
    return FieldScore(
        component=component,
        status="passed" if matched else "failed",
        score=result.metrics.f1,
        matched=matched,
        counts=result.counts,
        metrics=result.metrics,
        diagnostics=(f"duplicates={list(result.duplicates)}",) if result.duplicates else (),
    )


def _micro_score(
    component: str,
    exp_tables: dict[str, dict[str, Any]],
    act_tables: dict[str, dict[str, Any]],
    selector: Any,
) -> FieldScore:
    """Aggregate a set match across matched tables into one FieldScore."""
    tp = fp = fn = 0
    for name, exp_table in exp_tables.items():
        act_table = act_tables.get(name)
        result = match_sets(
            selector(exp_table),
            selector(act_table) if act_table else set(),
        )
        tp += result.counts.true_positive
        fp += result.counts.false_positive
        fn += result.counts.false_negative
    counts = MatchCounts(true_positive=tp, false_positive=fp, false_negative=fn)
    metrics = precision_recall_f1(counts)
    matched = metrics.f1 == 1.0
    return FieldScore(
        component=component,
        status="passed" if matched else "failed",
        score=metrics.f1,
        matched=matched,
        counts=counts,
        metrics=metrics,
    )
