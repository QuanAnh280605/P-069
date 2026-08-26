"""Cross-module perfect replay and controlled-mutation tests."""

from pathlib import Path

import pytest
from sqlglot import parse_one

from eval.dataset.loader import DomainDataset, load_domain_dataset
from eval.dataset.models import Dialect, DiscoveryCase, MetricDefinitionCase, QueryCase
from eval.evaluator import (
    CandidateCanonicalQuery,
    CandidateCompilerOutput,
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateGuardrailOutput,
    CandidateMetricDefinition,
    CandidateMetricOutput,
    CandidateRelationship,
    CaseEvaluationResult,
    DomainCandidateOutputs,
    EvaluationConfig,
    EvaluationDependencies,
    FieldScore,
    evaluate_domain_suite,
)
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result

GOLDEN_ROOT = Path("eval/golden_dataset")


class PerfectGuardrail:
    """Replay guardrail fixtures and guard valid compiler SQL."""

    def __init__(self, dataset: DomainDataset) -> None:
        self.cases = {case.sql: case for case in dataset.guardrail_cases}

    async def validate(self, sql: str, dialect: Dialect) -> CandidateGuardrailOutput:
        case = self.cases.get(sql)
        if case is None:
            return _accepted(sql, dialect, 100, 15)
        expected = case.expected
        if not expected.accepted:
            return CandidateGuardrailOutput(accepted=False, error_code=expected.error_code)
        assert expected.expected_limit and expected.expected_timeout_seconds
        return _accepted(sql, dialect, expected.expected_limit, expected.expected_timeout_seconds)


def _accepted(sql: str, dialect: Dialect, limit: int, timeout: int) -> CandidateGuardrailOutput:
    sqlglot_dialect = "postgres" if dialect == "postgresql" else dialect
    transformed = parse_one(sql, read=sqlglot_dialect).limit(limit).sql(dialect=sqlglot_dialect)
    return CandidateGuardrailOutput(
        accepted=True,
        sql=transformed,
        effective_limit=limit,
        effective_timeout_seconds=timeout,
    )


def _enrichment_candidate(dataset: DomainDataset, case: DiscoveryCase) -> CandidateEnrichmentOutput:
    relationships = tuple(
        CandidateRelationship.model_validate(item.model_dump()) for item in case.expected.relationship_expectations
    )
    entities = tuple(_entity_candidate(dataset, name, relationships) for name in dataset.canonical_entities)
    return CandidateEnrichmentOutput(entities=entities)


def _entity_candidate(
    dataset: DomainDataset,
    name: str,
    relationships: tuple[CandidateRelationship, ...],
) -> CandidateEntity:
    expected = dataset.canonical_entities[name]
    dimensions = tuple(
        CandidateDimension(name=item.name, business_name=item.business_name) for item in expected.dimensions
    )
    own = tuple(item for item in relationships if item.source_entity == name)
    return CandidateEntity(entity=name, business_name=expected.business_name, dimensions=dimensions, relationships=own)


def _metric_candidate(case: MetricDefinitionCase) -> CandidateMetricOutput:
    if case.expected_error is not None:
        return CandidateMetricOutput(error_code=case.expected_error)
    assert case.expected_metric is not None
    payload = case.expected_metric.model_dump()
    payload["expected_preview_facts"] = case.expected_preview_facts
    return CandidateMetricOutput(metric=CandidateMetricDefinition.model_validate(payload))


def _compiler_candidate(case: QueryCase) -> CandidateCompilerOutput:
    expected = case.expected
    if expected is None:
        return CandidateCompilerOutput(error_code=case.expected_error)
    canonical = CandidateCanonicalQuery.model_validate(expected.canonical_query.model_dump())
    return CandidateCompilerOutput(canonical_query=canonical, sql=expected.sql_by_dialect["sqlite"])


def _perfect_candidates(dataset: DomainDataset) -> DomainCandidateOutputs:
    return DomainCandidateOutputs(
        enrichment={case.case_id: _enrichment_candidate(dataset, case) for case in dataset.discovery_cases},
        metrics={case.case_id: _metric_candidate(case) for case in dataset.metric_cases},
        compiler={case.case_id: _compiler_candidate(case) for case in dataset.query_cases},
    )


@pytest.mark.asyncio
async def test_complete_domain_perfect_replay_scores_one() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    result = await evaluate_domain_suite(
        dataset,
        _perfect_candidates(dataset),
        EvaluationDependencies(EvaluationConfig(), guardrail_adapter=PerfectGuardrail(dataset)),
    )
    suites = (result.enrichment, result.metrics, result.compiler, result.guardrails)
    assert [suite.total_cases for suite in suites] == [4, 21, 39, 16]
    assert all(suite.macro_score == 1.0 for suite in suites)
    assert all(all(case.status == "passed" for case in suite.cases) for suite in suites)
    assert result.frozen_evaluation_date == dataset.manifest.frozen_evaluation_date
    assert result.domain == "ecommerce" and result.dataset_contract_version == "2.1.0"
    assert any(group.tag == "easy" for group in result.compiler.group_scores)
    assert result.model_dump_json()


@pytest.mark.asyncio
async def test_cqm_mutation_only_reduces_cqm_component() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    candidates = _perfect_candidates(dataset)
    case = next(item for item in dataset.query_cases if item.expected)
    candidate = candidates.compiler[case.case_id]
    assert candidate.canonical_query is not None
    canonical = candidate.canonical_query.model_copy(update={"primary_entity": "wrong_entity"})
    mutated = candidate.model_copy(update={"canonical_query": canonical})
    compiler = {**candidates.compiler, case.case_id: mutated}
    candidates = candidates.model_copy(update={"compiler": compiler})
    result = await evaluate_domain_suite(
        dataset,
        candidates,
        EvaluationDependencies(EvaluationConfig(), guardrail_adapter=PerfectGuardrail(dataset)),
    )
    evaluated = next(item for item in result.compiler.cases if item.case_id == case.case_id)
    scores = {item.component: item.matched for item in evaluated.component_scores}
    assert not scores["cqm.primary_entity"]
    assert scores["sql_ast"] and scores["execution"]


@pytest.mark.asyncio
async def test_missing_adapter_is_explicitly_not_available() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    result = await evaluate_domain_suite(
        dataset,
        _perfect_candidates(dataset),
        EvaluationDependencies(EvaluationConfig()),
    )
    assert result.guardrails.evaluated_cases == 0
    assert result.guardrails.macro_score is None
    assert all(case.status == "not_available" for case in result.guardrails.cases)
    execution = [
        score for case in result.compiler.cases for score in case.component_scores if score.component == "execution"
    ]
    assert execution and all(score.status == "not_available" for score in execution)


@pytest.mark.asyncio
async def test_macro_score_averages_cases_instead_of_weighting_fields() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    results = (
        CaseEvaluationResult(
            case_id="many_fields",
            status="passed",
            component_scores=(FieldScore(component="a", score=1.0), FieldScore(component="b", score=1.0)),
        ),
        CaseEvaluationResult(
            case_id="one_field",
            status="failed",
            component_scores=(FieldScore(component="a", status="failed", score=0.0),),
        ),
    )
    suite = build_suite_result(SuiteBuildInput(dataset=dataset, results=results, config=EvaluationConfig()))
    assert suite.macro_score == 0.5


@pytest.mark.asyncio
async def test_candidate_failure_without_components_contributes_zero_to_macro() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    results = (
        CaseEvaluationResult(
            case_id="success", status="passed", component_scores=(FieldScore(component="a", score=1.0),)
        ),
        CaseEvaluationResult(case_id="candidate_error", status="failed"),
        CaseEvaluationResult(case_id="evaluator_error", status="error"),
    )
    suite = build_suite_result(SuiteBuildInput(dataset=dataset, results=results, config=EvaluationConfig()))
    assert suite.macro_score == 0.5
