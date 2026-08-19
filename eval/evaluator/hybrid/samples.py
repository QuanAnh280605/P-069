"""Typed evaluation sample envelope and dataset-to-sample builder."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue

from eval.dataset.loader import DomainDataset
from eval.dataset.models import (
    CanonicalEntityDefinition,
    Dialect,
    DiscoveryCase,
    DiscoveryCaseExpected,
    ExpectedMetricDefinition,
    GuardrailExpected,
    QueryCaseExpected,
    RelationshipExpectation,
)
from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.schemas import (
    CandidateCompilerOutput,
    CandidateEnrichmentOutput,
    CandidateGuardrailOutput,
    CandidateMetricOutput,
    StrictEvaluationModel,
)

TaskName = Literal["discovery", "enrichment", "metric_generation", "query_compilation", "guardrail"]


class DiscoveryInput(StrictEvaluationModel):
    """Describe the public discovery request for one sample."""

    source_type: Literal["live_connection", "sql_dump"]
    dialect: Dialect
    raw_schema_ref: str


class EnrichmentInput(StrictEvaluationModel):
    """List entity references visible to the enrichment stage."""

    entity_refs: tuple[str, ...]


class MetricGenerationInput(StrictEvaluationModel):
    """Describe the metric generation request and canonical context."""

    request: str
    canonical_entities: tuple[str, ...]
    canonical_dimensions: tuple[str, ...]


class QueryCompilationInput(StrictEvaluationModel):
    """Describe the query compilation request."""

    question: str
    difficulty: Literal["easy", "medium", "hard"]


class GuardrailInput(StrictEvaluationModel):
    """Describe one SQL guardrail probe."""

    sql: str
    dialect: Dialect


SampleInput = DiscoveryInput | EnrichmentInput | MetricGenerationInput | QueryCompilationInput | GuardrailInput


class DiscoveryReference(StrictEvaluationModel):
    """Contain the golden raw schema fixture for discovery scoring."""

    raw_schema: dict[str, JsonValue]


class EnrichmentReference(StrictEvaluationModel):
    """Contain golden entity names, relationships, and canonical entities."""

    entity_refs: tuple[str, ...]
    relationship_expectations: tuple[RelationshipExpectation, ...]
    canonical_entities: tuple[CanonicalEntityDefinition, ...]


class MetricReference(StrictEvaluationModel):
    """Contain the expected metric definition or expected error."""

    expected_metric: ExpectedMetricDefinition | None = None
    expected_error: str | None = None
    expected_preview_facts: tuple[str, ...] = ()


class QueryReference(StrictEvaluationModel):
    """Contain the expected compiled query and its expected result rows."""

    expected: QueryCaseExpected | None = None
    expected_error: str | None = None
    expected_rows: list[dict[str, JsonValue]] = Field(default_factory=list)


SampleReference = DiscoveryReference | EnrichmentReference | MetricReference | QueryReference | GuardrailExpected

SampleResponse = (
    CandidateDiscoveryOutput
    | CandidateEnrichmentOutput
    | CandidateMetricOutput
    | CandidateCompilerOutput
    | CandidateGuardrailOutput
)


class EvaluationSample(StrictEvaluationModel):
    """Represent one Ragas-style evaluation row with typed payloads."""

    sample_id: str
    task: TaskName
    input: SampleInput
    reference: SampleReference
    response: SampleResponse | None = None
    tags: tuple[str, ...] = ()


def build_samples(
    dataset: DomainDataset,
    discovery: dict[str, CandidateDiscoveryOutput],
    enrichment: dict[str, CandidateEnrichmentOutput],
    metrics: dict[str, CandidateMetricOutput],
    compiler: dict[str, CandidateCompilerOutput],
    guardrail: dict[str, CandidateGuardrailOutput],
) -> tuple[EvaluationSample, ...]:
    """Join dataset cases with captured candidates into typed samples."""
    samples: list[EvaluationSample] = []
    samples.extend(_discovery_samples(dataset, discovery, enrichment))
    samples.extend(_metric_samples(dataset, metrics))
    samples.extend(_compiler_samples(dataset, compiler))
    samples.extend(_guardrail_samples(dataset, guardrail))
    return tuple(samples)


def _entity_refs(case: DiscoveryCaseExpected) -> tuple[str, ...]:
    return tuple(Path(ref).stem for ref in case.entity_refs)


def _discovery_samples(
    dataset: DomainDataset,
    discovery: dict[str, CandidateDiscoveryOutput],
    enrichment: dict[str, CandidateEnrichmentOutput],
) -> list[EvaluationSample]:
    samples: list[EvaluationSample] = []
    for case in dataset.discovery_cases:
        samples.append(_discovery_sample(dataset, case, discovery.get(case.case_id)))
        samples.append(
            EvaluationSample(
                sample_id=case.case_id,
                task="enrichment",
                input=EnrichmentInput(entity_refs=_entity_refs(case.expected)),
                reference=_enrichment_reference(dataset, case),
                response=enrichment.get(case.case_id),
                tags=tuple(case.tags),
            )
        )
    return samples


def _discovery_sample(
    dataset: DomainDataset,
    case: DiscoveryCase,
    response: CandidateDiscoveryOutput | None,
) -> EvaluationSample:
    return EvaluationSample(
        sample_id=case.case_id,
        task="discovery",
        input=DiscoveryInput(source_type=case.source_type, dialect=case.dialect, raw_schema_ref=case.raw_schema_ref),
        reference=DiscoveryReference(raw_schema=dataset.raw_schemas[case.raw_schema_ref]),
        response=response,
        tags=tuple(case.tags),
    )


def _enrichment_reference(dataset: DomainDataset, case: DiscoveryCase) -> EnrichmentReference:
    stems = _entity_refs(case.expected)
    canonical = tuple(dataset.canonical_entities[stem] for stem in stems if stem in dataset.canonical_entities)
    return EnrichmentReference(
        entity_refs=stems,
        relationship_expectations=tuple(case.expected.relationship_expectations),
        canonical_entities=canonical,
    )


def _metric_samples(dataset: DomainDataset, metrics: dict[str, CandidateMetricOutput]) -> list[EvaluationSample]:
    return [
        EvaluationSample(
            sample_id=case.case_id,
            task="metric_generation",
            input=MetricGenerationInput(
                request=case.request,
                canonical_entities=tuple(case.canonical_context.entities),
                canonical_dimensions=tuple(case.canonical_context.dimensions),
            ),
            reference=MetricReference(
                expected_metric=case.expected_metric,
                expected_error=case.expected_error,
                expected_preview_facts=tuple(case.expected_preview_facts),
            ),
            response=metrics.get(case.case_id),
            tags=tuple(case.tags),
        )
        for case in dataset.metric_cases
    ]


def _compiler_samples(dataset: DomainDataset, compiler: dict[str, CandidateCompilerOutput]) -> list[EvaluationSample]:
    samples: list[EvaluationSample] = []
    for case in dataset.query_cases:
        rows = dataset.expected_query_results.get(case.expected.result_ref, []) if case.expected else []
        samples.append(
            EvaluationSample(
                sample_id=case.case_id,
                task="query_compilation",
                input=QueryCompilationInput(question=case.question, difficulty=case.difficulty),
                reference=QueryReference(
                    expected=case.expected, expected_error=case.expected_error, expected_rows=list(rows)
                ),
                response=compiler.get(case.case_id),
                tags=(*case.tags, case.difficulty),
            )
        )
    return samples


def _guardrail_samples(
    dataset: DomainDataset, guardrail: dict[str, CandidateGuardrailOutput]
) -> list[EvaluationSample]:
    return [
        EvaluationSample(
            sample_id=case.case_id,
            task="guardrail",
            input=GuardrailInput(sql=case.sql, dialect=case.dialect),
            reference=case.expected,
            response=guardrail.get(case.case_id),
            tags=tuple(case.tags),
        )
        for case in dataset.guardrail_cases
    ]
