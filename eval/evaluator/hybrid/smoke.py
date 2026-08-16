"""Golden-derived smoke candidates for local hybrid runs (spec §4.1)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from eval.dataset.loader import DomainDataset
from eval.dataset.models import Dialect
from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.schemas import (
    CandidateCanonicalQuery,
    CandidateCompilerOutput,
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateGuardrailOutput,
    CandidateMetricDefinition,
    CandidateMetricOutput,
    CandidateRelationship,
    EvaluationConfig,
)
from eval.evaluator.sql_normalization import SqlValidationError, effective_limit, normalize_sql


@dataclass(frozen=True)
class SmokeCandidates:
    """Bundle every golden-derived smoke candidate mapping."""

    discovery: Mapping[str, CandidateDiscoveryOutput]
    enrichment: Mapping[str, CandidateEnrichmentOutput]
    metrics: Mapping[str, CandidateMetricOutput]
    compiler: Mapping[str, CandidateCompilerOutput]
    guardrail: Mapping[str, CandidateGuardrailOutput]


async def smoke_candidates(dataset: DomainDataset, config: EvaluationConfig) -> SmokeCandidates:
    """Derive every smoke candidate mapping from the golden fixtures."""
    return SmokeCandidates(
        discovery=smoke_discovery(dataset),
        enrichment=smoke_enrichment(dataset),
        metrics=smoke_metrics(dataset),
        compiler=smoke_compiler(dataset),
        guardrail=await smoke_guardrail_responses(dataset, config),
    )


def smoke_discovery(dataset: DomainDataset) -> dict[str, CandidateDiscoveryOutput]:
    """Replay each golden raw schema as the discovery candidate."""
    return {
        case.case_id: CandidateDiscoveryOutput(raw_schema=dict(dataset.raw_schemas[case.raw_schema_ref]))
        for case in dataset.discovery_cases
    }


def smoke_enrichment(dataset: DomainDataset) -> dict[str, CandidateEnrichmentOutput]:
    """Derive perfect enrichment candidates from the canonical entities."""
    entities = tuple(_candidate_entity(dataset, name) for name in dataset.canonical_entities)
    output = CandidateEnrichmentOutput(entities=entities)
    return {case.case_id: output for case in dataset.discovery_cases}


def _candidate_entity(dataset: DomainDataset, name: str) -> CandidateEntity:
    """Build one candidate entity from its canonical definition."""
    definition = dataset.canonical_entities[name]
    dimensions = tuple(
        CandidateDimension(name=dim.name, business_name=dim.business_name) for dim in definition.dimensions
    )
    return CandidateEntity(
        entity=definition.entity,
        business_name=definition.business_name,
        dimensions=dimensions,
        relationships=_candidate_relationships(dataset, definition.entity),
    )


def _candidate_relationships(dataset: DomainDataset, entity: str) -> tuple[CandidateRelationship, ...]:
    """Collect expected relationships whose source is the given entity."""
    return tuple(
        CandidateRelationship(
            source_entity=rel.source_entity,
            source_field=rel.source_field,
            target_entity=rel.target_entity,
            target_field=rel.target_field,
            relation_type=rel.relation_type,
            inferred=rel.inferred,
        )
        for case in dataset.discovery_cases
        for rel in case.expected.relationship_expectations
        if rel.source_entity == entity
    )


def smoke_metrics(dataset: DomainDataset) -> dict[str, CandidateMetricOutput]:
    """Replay expected metrics and errors as metric-generation candidates."""
    outputs: dict[str, CandidateMetricOutput] = {}
    for case in dataset.metric_cases:
        if case.expected_error is not None:
            outputs[case.case_id] = CandidateMetricOutput(error_code=case.expected_error)
            continue
        assert case.expected_metric is not None
        definition = CandidateMetricDefinition(
            **case.expected_metric.model_dump(),
            expected_preview_facts=tuple(case.expected_preview_facts),
        )
        outputs[case.case_id] = CandidateMetricOutput(metric=definition)
    return outputs


def smoke_compiler(dataset: DomainDataset) -> dict[str, CandidateCompilerOutput]:
    """Replay expected queries and SQL as compiler candidates."""
    outputs: dict[str, CandidateCompilerOutput] = {}
    dialect = dataset.manifest.execution_dialect
    for case in dataset.query_cases:
        if case.expected_error is not None:
            outputs[case.case_id] = CandidateCompilerOutput(error_code=case.expected_error)
            continue
        assert case.expected is not None
        query = CandidateCanonicalQuery(**case.expected.canonical_query.model_dump())
        outputs[case.case_id] = CandidateCompilerOutput(
            canonical_query=query, sql=case.expected.sql_by_dialect[dialect]
        )
    return outputs


class SmokeGuardrailAdapter:
    """Deterministic guardrail stand-in built on the shared normalization rules."""

    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config

    async def validate(self, sql: str, dialect: Dialect) -> CandidateGuardrailOutput:
        """Normalize SQL and derive the guardrail decision without executing it."""
        try:
            normalized = normalize_sql(sql, dialect)
            limit = effective_limit(sql, dialect) or self.config.default_limit
        except SqlValidationError as exc:
            return CandidateGuardrailOutput(accepted=False, error_code=str(exc))
        return CandidateGuardrailOutput(
            accepted=True,
            sql=normalized.canonical,
            effective_limit=limit,
            effective_timeout_seconds=self.config.statement_timeout_seconds,
        )


async def smoke_guardrail_responses(
    dataset: DomainDataset, config: EvaluationConfig
) -> dict[str, CandidateGuardrailOutput]:
    """Capture the smoke adapter decision for every guardrail case."""
    adapter = SmokeGuardrailAdapter(config)
    responses: dict[str, CandidateGuardrailOutput] = {}
    for case in dataset.guardrail_cases:
        responses[case.case_id] = await adapter.validate(case.sql, case.dialect)
    return responses
