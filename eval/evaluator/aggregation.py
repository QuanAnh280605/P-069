"""Build provenance-rich deterministic suite results."""

from __future__ import annotations

from dataclasses import dataclass

from eval.dataset.loader import DomainDataset
from eval.evaluator.schemas import (
    CaseEvaluationResult,
    EvaluationConfig,
    GroupScore,
    PrecisionRecallF1,
    SuiteEvaluationResult,
)
from eval.evaluator.scoring import macro_average


@dataclass(frozen=True)
class SuiteBuildInput:
    """Bundle suite aggregation inputs without widening function signatures."""

    dataset: DomainDataset
    results: tuple[CaseEvaluationResult, ...]
    config: EvaluationConfig
    micro: PrecisionRecallF1 | None = None


def build_suite_result(value: SuiteBuildInput) -> SuiteEvaluationResult:
    """Create one serializable suite result with dataset and config provenance."""
    manifest = value.dataset.manifest
    scores = _case_scores(value.results)
    return SuiteEvaluationResult(
        domain=manifest.domain,
        dataset_version=manifest.dataset_version,
        dataset_contract_version=manifest.contract_version,
        dataset_review_status=manifest.review_status,
        frozen_evaluation_date=manifest.frozen_evaluation_date,
        evaluation_config=value.config,
        total_cases=len(value.results),
        evaluated_cases=sum(item.status not in {"skipped", "not_available"} for item in value.results),
        micro=value.micro,
        macro_score=macro_average(scores),
        group_scores=_group_scores(value.results),
        cases=value.results,
    )


def _case_scores(results: tuple[CaseEvaluationResult, ...]) -> tuple[float, ...]:
    scores: list[float] = []
    for result in results:
        if result.status in {"skipped", "not_available", "error"}:
            continue
        components = _available_component_scores(result)
        case_score = macro_average(components)
        scores.append(case_score if case_score is not None else 0.0)
    return tuple(scores)


def _available_component_scores(result: CaseEvaluationResult) -> tuple[float, ...]:
    return tuple(
        item.score for item in result.component_scores if item.status != "not_available" and item.score is not None
    )


def _group_scores(results: tuple[CaseEvaluationResult, ...]) -> tuple[GroupScore, ...]:
    groups: list[GroupScore] = []
    for tag in sorted({tag for result in results for tag in result.tags}):
        tagged = tuple(result for result in results if tag in result.tags)
        score = macro_average(_case_scores(tagged))
        if score is not None:
            groups.append(
                GroupScore(
                    tag=tag, case_count=len(tagged), macro_score=score, case_ids=tuple(x.case_id for x in tagged)
                )
            )
    return tuple(groups)
