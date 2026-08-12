"""Asynchronous loader for versioned Golden Dataset domains."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TypeVar

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from eval.dataset.models import (
    CanonicalEntityDefinition,
    CanonicalMetricDefinition,
    DiscoveryCase,
    DomainManifest,
    ExpectedQueryResults,
    GuardrailCase,
    MetricDefinitionCase,
    QueryCase,
    QueryReferenceCatalog,
)
from eval.dataset.validator import (
    DatasetValidationError,
    validate_canonical_domains,
    validate_canonical_references,
    validate_discovery_cases,
    validate_discovery_dialects,
    validate_discovery_references,
    validate_domain_files,
    validate_ground_truth_count,
    validate_guardrail_cases,
    validate_guardrail_expectations,
    validate_metric_cases,
    validate_metric_references,
    validate_query_cases,
    validate_query_dialects,
    validate_query_references,
)
from src.models.raw_schema import RawSchema

CanonicalArtifact = TypeVar(
    "CanonicalArtifact",
    CanonicalEntityDefinition,
    CanonicalMetricDefinition,
)


class DomainDataset(BaseModel):
    """Contain fully loaded and cross-validated domain artifacts."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    domain_dir: Path
    manifest: DomainManifest
    discovery_cases: list[DiscoveryCase]
    metric_cases: list[MetricDefinitionCase]
    query_cases: list[QueryCase]
    guardrail_cases: list[GuardrailCase]
    raw_schemas: dict[str, RawSchema]
    canonical_entities: dict[str, CanonicalEntityDefinition]
    canonical_metrics: dict[str, CanonicalMetricDefinition]
    expected_query_results: ExpectedQueryResults


async def load_domain_dataset(golden_root: Path, domain: str) -> DomainDataset:
    """Load and validate one Golden Dataset domain without blocking the event loop."""
    return await asyncio.to_thread(_load_domain_dataset, golden_root, domain)


def _load_domain_dataset(golden_root: Path, domain: str) -> DomainDataset:
    domain_dir = _safe_domain_dir(golden_root, domain)
    manifest = validate_domain_files(domain_dir)
    case_ids: set[str] = set()
    discovery, metrics, queries, guardrails = _load_cases(domain_dir, manifest, case_ids)
    entities, canonical_metrics = _load_canonical_yaml(domain_dir / "canonical")
    raw_schemas = _load_raw_schemas(domain_dir, discovery)
    expected_results = _load_expected_results(domain_dir)
    dataset = DomainDataset(
        domain_dir=domain_dir,
        manifest=manifest,
        discovery_cases=discovery,
        metric_cases=metrics,
        query_cases=queries,
        guardrail_cases=guardrails,
        raw_schemas=raw_schemas,
        canonical_entities=entities,
        canonical_metrics=canonical_metrics,
        expected_query_results=expected_results,
    )
    _validate_dataset(dataset)
    return dataset


def _load_cases(
    domain_dir: Path,
    manifest: DomainManifest,
    case_ids: set[str],
) -> tuple[list[DiscoveryCase], list[MetricDefinitionCase], list[QueryCase], list[GuardrailCase]]:
    files = manifest.case_files
    discovery = validate_discovery_cases(_safe_ref(domain_dir, files.discovery), case_ids)
    metrics = validate_metric_cases(_safe_ref(domain_dir, files.metric_definition), case_ids)
    queries = validate_query_cases(_safe_ref(domain_dir, files.query), case_ids)
    guardrails = validate_guardrail_cases(_safe_ref(domain_dir, files.guardrail), case_ids)
    return discovery, metrics, queries, guardrails


def _load_canonical_yaml(
    canonical_dir: Path,
) -> tuple[dict[str, CanonicalEntityDefinition], dict[str, CanonicalMetricDefinition]]:
    entities = _load_yaml_models(canonical_dir / "entities", CanonicalEntityDefinition, "entity")
    metrics = _load_yaml_models(canonical_dir / "metrics", CanonicalMetricDefinition, "metric")
    return entities, metrics


def _load_yaml_models(
    directory: Path,
    model: type[CanonicalArtifact],
    key: str,
) -> dict[str, CanonicalArtifact]:
    if not directory.is_dir():
        raise DatasetValidationError(f"Missing canonical directory: {directory}")
    loaded: dict[str, CanonicalArtifact] = {}
    for path in sorted(directory.glob("*.yaml")):
        item = _parse_yaml(path, model)
        identifier = str(getattr(item, key))
        if identifier in loaded:
            raise DatasetValidationError(f"Duplicate canonical {key}: {identifier}")
        loaded[identifier] = item
    return loaded


def _parse_yaml(
    path: Path,
    model: type[CanonicalArtifact],
) -> CanonicalArtifact:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return model.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise DatasetValidationError(f"Invalid canonical YAML {path}: {exc}") from exc


def _load_raw_schemas(domain_dir: Path, cases: list[DiscoveryCase]) -> dict[str, RawSchema]:
    adapter = TypeAdapter(RawSchema)
    loaded: dict[str, RawSchema] = {}
    for reference in sorted({case.raw_schema_ref for case in cases}):
        path = _safe_ref(domain_dir, reference)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            loaded[reference] = adapter.validate_python(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise DatasetValidationError(f"Invalid raw schema {path}: {exc}") from exc
    return loaded


def _load_expected_results(domain_dir: Path) -> ExpectedQueryResults:
    path = domain_dir / "expected_results" / "query_results.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return TypeAdapter(ExpectedQueryResults).validate_python(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DatasetValidationError(f"Invalid expected results {path}: {exc}") from exc


def _validate_dataset(dataset: DomainDataset) -> None:
    entities = dataset.canonical_entities
    metrics = dataset.canonical_metrics
    validate_canonical_references(entities, metrics)
    validate_canonical_domains(metrics, dataset.manifest)
    validate_ground_truth_count(metrics, dataset.manifest)
    validate_discovery_references(dataset.discovery_cases, entities, dataset.raw_schemas)
    validate_discovery_dialects(dataset.discovery_cases, dataset.manifest)
    validate_metric_references(dataset.metric_cases, entities, metrics)
    catalog = QueryReferenceCatalog(
        entities=entities,
        metrics=metrics,
        expected_results=dataset.expected_query_results,
    )
    validate_query_references(dataset.query_cases, catalog)
    validate_query_dialects(dataset.query_cases, dataset.manifest)
    validate_guardrail_expectations(dataset.guardrail_cases)


def _safe_domain_dir(golden_root: Path, domain: str) -> Path:
    if not domain or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in domain):
        raise DatasetValidationError(f"Invalid domain identifier: {domain!r}")
    domain_dir = (golden_root / domain).resolve()
    if not domain_dir.is_relative_to(golden_root.resolve()) or not domain_dir.is_dir():
        raise DatasetValidationError(f"Missing or unsafe domain directory: {domain_dir}")
    return domain_dir


def _safe_ref(domain_dir: Path, reference: str) -> Path:
    path = (domain_dir / reference).resolve()
    if not path.is_relative_to(domain_dir.resolve()):
        raise DatasetValidationError(f"Reference escapes domain directory: {reference}")
    return path
