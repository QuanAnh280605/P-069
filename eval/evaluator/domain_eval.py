"""Orchestrate all evaluator suites for one validated domain dataset."""

from __future__ import annotations

from dataclasses import dataclass

from eval.dataset.loader import DomainDataset
from eval.evaluator.aggregation import SuiteBuildInput, build_suite_result
from eval.evaluator.compiler_eval import GuardrailAdapter, evaluate_compiler_suite, evaluate_guardrail_suite
from eval.evaluator.enrichment_eval import evaluate_enrichment_suite
from eval.evaluator.metric_eval import evaluate_metric_suite
from eval.evaluator.schemas import (
    CaseEvaluationResult,
    DomainCandidateOutputs,
    DomainEvaluationResult,
    EvaluationConfig,
    SuiteEvaluationResult,
)
from eval.evaluator.text_similarity import TextSimilarityProvider


@dataclass(frozen=True)
class EvaluationDependencies:
    """Provide configured optional evaluator integrations."""

    config: EvaluationConfig
    text_provider: TextSimilarityProvider | None = None
    guardrail_adapter: GuardrailAdapter | None = None


@dataclass(frozen=True)
class DomainSuites:
    """Bundle component suite results before provenance assembly."""

    enrichment: SuiteEvaluationResult
    metrics: SuiteEvaluationResult
    compiler: SuiteEvaluationResult
    guardrails: SuiteEvaluationResult


async def evaluate_domain_suite(
    dataset: DomainDataset,
    candidates: DomainCandidateOutputs,
    dependencies: EvaluationDependencies,
) -> DomainEvaluationResult:
    """Run every evaluator suite and preserve complete replay provenance."""
    enrichment = await evaluate_enrichment_suite(
        dataset, candidates.enrichment, dependencies.config, dependencies.text_provider
    )
    metrics = await evaluate_metric_suite(dataset, candidates.metrics, dependencies.config, dependencies.text_provider)
    compiler = await evaluate_compiler_suite(
        dataset, candidates.compiler, dependencies.config, dependencies.guardrail_adapter
    )
    suites = DomainSuites(
        enrichment=enrichment,
        metrics=metrics,
        compiler=compiler,
        guardrails=await _guardrail_suite(dataset, dependencies),
    )
    return _domain_result(dataset, dependencies.config, suites)


async def _guardrail_suite(
    dataset: DomainDataset,
    dependencies: EvaluationDependencies,
) -> SuiteEvaluationResult:
    adapter = dependencies.guardrail_adapter
    if adapter is not None:
        return await evaluate_guardrail_suite(dataset, adapter, dependencies.config)
    results = tuple(
        CaseEvaluationResult(case_id=case.case_id, status="not_available", tags=tuple(case.tags))
        for case in dataset.guardrail_cases
    )
    return build_suite_result(SuiteBuildInput(dataset=dataset, results=results, config=dependencies.config))


def _domain_result(
    dataset: DomainDataset,
    config: EvaluationConfig,
    suites: DomainSuites,
) -> DomainEvaluationResult:
    manifest = dataset.manifest
    return DomainEvaluationResult(
        domain=manifest.domain,
        dataset_version=manifest.dataset_version,
        dataset_contract_version=manifest.contract_version,
        dataset_review_status=manifest.review_status,
        frozen_evaluation_date=manifest.frozen_evaluation_date,
        evaluation_config=config,
        enrichment=suites.enrichment,
        metrics=suites.metrics,
        compiler=suites.compiler,
        guardrails=suites.guardrails,
    )
