"""Golden Dataset integrity and SQL AST validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import sqlglot
from pydantic import ValidationError
from sqlglot import exp

from eval.dataset.models import (
    CanonicalEntityDefinition,
    CanonicalMetricDefinition,
    DiscoveryCase,
    DomainManifest,
    GuardrailCase,
    MetricDefinitionCase,
    QueryCase,
    QueryReferenceCatalog,
)
from src.models.raw_schema import RawSchema

CaseModel = TypeVar("CaseModel", DiscoveryCase, MetricDefinitionCase, QueryCase, GuardrailCase)
FORBIDDEN_SQL_NODES = (
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Into,
    exp.Merge,
    exp.Transaction,
    exp.TruncateTable,
    exp.Update,
)
FORBIDDEN_SELECT_FUNCTIONS = {
    "benchmark",
    "dblink_exec",
    "load_extension",
    "load_file",
    "lo_import",
    "pg_read_binary_file",
    "pg_read_file",
    "set_config",
    "sleep",
}


class DatasetValidationError(Exception):
    """Report an invalid or internally inconsistent Golden Dataset."""


def validate_read_only_sql(sql_str: str, dialect: str = "sqlite") -> bool:
    """Return whether SQL is exactly one side-effect-free SELECT statement."""
    try:
        statements = sqlglot.parse(sql_str, read=dialect)
    except sqlglot.errors.ParseError as exc:
        raise DatasetValidationError(f"Invalid SQL syntax: {exc}") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        return False
    statement = statements[0]
    if any(isinstance(node, FORBIDDEN_SQL_NODES) for node in statement.walk()):
        return False
    return not any(node.name.lower() in FORBIDDEN_SELECT_FUNCTIONS for node in statement.find_all(exp.Anonymous))


def validate_domain_files(domain_dir: Path) -> DomainManifest:
    """Load a domain manifest and validate its top-level identity."""
    manifest_path = domain_dir / "manifest.json"
    data = _read_json(manifest_path, "manifest")
    try:
        manifest = DomainManifest.model_validate(data)
    except ValidationError as exc:
        raise DatasetValidationError(f"Invalid manifest.json: {exc}") from exc
    if manifest.domain != domain_dir.name:
        raise DatasetValidationError("manifest domain must match its directory name")
    return manifest


def validate_discovery_cases(case_path: Path, case_ids: set[str]) -> list[DiscoveryCase]:
    """Load strict discovery cases and enforce globally unique IDs."""
    return _load_cases(case_path, DiscoveryCase, case_ids)


def validate_metric_cases(case_path: Path, case_ids: set[str]) -> list[MetricDefinitionCase]:
    """Load strict metric-definition cases and enforce unique IDs."""
    return _load_cases(case_path, MetricDefinitionCase, case_ids)


def validate_query_cases(case_path: Path, case_ids: set[str]) -> list[QueryCase]:
    """Load runtime query cases and validate every expected SQL statement."""
    cases = _load_cases(case_path, QueryCase, case_ids)
    for case in cases:
        if case.expected:
            _validate_expected_sql(case)
    return cases


def validate_guardrail_cases(case_path: Path, case_ids: set[str]) -> list[GuardrailCase]:
    """Load strict SQL guardrail cases and enforce unique IDs."""
    return _load_cases(case_path, GuardrailCase, case_ids)


def validate_canonical_references(
    entities: dict[str, CanonicalEntityDefinition],
    metrics: dict[str, CanonicalMetricDefinition],
) -> None:
    """Validate canonical fields and relationship endpoints."""
    for entity in entities.values():
        _validate_entity_references(entity, entities)
    for metric in metrics.values():
        _validate_metric_reference(metric, entities, metrics)


def validate_discovery_references(
    cases: list[DiscoveryCase],
    entities: dict[str, CanonicalEntityDefinition],
    raw_schemas: dict[str, RawSchema],
) -> None:
    """Validate Stage 1 raw-schema, entity, and relationship references."""
    for case in cases:
        raw_schema = raw_schemas.get(case.raw_schema_ref)
        if not raw_schema:
            raise DatasetValidationError(f"Unknown raw_schema_ref: {case.raw_schema_ref}")
        expected_entities = {Path(ref).stem for ref in case.expected.entity_refs}
        if not expected_entities.issubset(entities):
            raise DatasetValidationError(f"Unknown entity reference in {case.case_id}")
        expected_tables = {entities[name].table_mapping for name in expected_entities}
        raw_tables = {table["table_name"] for table in raw_schema["tables"]}
        if expected_tables != raw_tables:
            raise DatasetValidationError(f"Incomplete discovery expectation: {case.case_id}")
        _validate_discovery_relationships(case, entities, raw_schema)


def validate_metric_references(
    cases: list[MetricDefinitionCase],
    entities: dict[str, CanonicalEntityDefinition],
    metrics: dict[str, CanonicalMetricDefinition],
) -> None:
    """Validate Stage 3 context and expected metric references."""
    for case in cases:
        _validate_context_entities(case, entities)
        if case.expected_metric:
            metric = metrics.get(case.expected_metric.name)
            if not metric:
                raise DatasetValidationError(f"Unknown metric in {case.case_id}")
            _validate_expected_metric(case, metric)


def validate_query_references(
    cases: list[QueryCase],
    catalog: QueryReferenceCatalog,
) -> None:
    """Validate Stage 4 canonical and expected-result references."""
    referenced_results: set[str] = set()
    for case in cases:
        if case.expected:
            _validate_query_case(case, catalog.entities, catalog.metrics)
            if case.expected.result_ref not in catalog.expected_results:
                raise DatasetValidationError(f"Missing result_ref for {case.case_id}")
            referenced_results.add(case.expected.result_ref)
    orphaned = set(catalog.expected_results) - referenced_results
    if orphaned:
        raise DatasetValidationError(f"Orphan expected results: {sorted(orphaned)}")


def validate_query_dialects(cases: list[QueryCase], manifest: DomainManifest) -> None:
    """Require every query to use the manifest domain and declared dialects."""
    supported = set(manifest.supported_dialects)
    for case in cases:
        if case.expected and set(case.expected.sql_by_dialect) != supported:
            raise DatasetValidationError(f"Dialect coverage mismatch: {case.case_id}")
        if case.expected and case.expected.domain != manifest.domain:
            raise DatasetValidationError(f"Manifest domain mismatch: {case.case_id}")


def validate_canonical_domains(
    metrics: dict[str, CanonicalMetricDefinition],
    manifest: DomainManifest,
) -> None:
    """Require every canonical metric to belong to the manifest domain."""
    invalid = [metric.metric for metric in metrics.values() if metric.domain != manifest.domain]
    if invalid:
        raise DatasetValidationError(f"Metric domain mismatch: {sorted(invalid)}")


def validate_ground_truth_count(
    metrics: dict[str, CanonicalMetricDefinition],
    manifest: DomainManifest,
) -> None:
    """Require the manifest count to match the canonical metric registry."""
    if len(metrics) != manifest.ground_truth_metric_count:
        raise DatasetValidationError("ground_truth_metric_count does not match registry")


def validate_discovery_dialects(cases: list[DiscoveryCase], manifest: DomainManifest) -> None:
    """Require discovery cases to use only supported dialects."""
    unsupported = [case.case_id for case in cases if case.dialect not in manifest.supported_dialects]
    if unsupported:
        raise DatasetValidationError(f"Unsupported discovery dialects: {unsupported}")


def validate_guardrail_expectations(cases: list[GuardrailCase]) -> None:
    """Ensure every guardrail fixture agrees with the AST validator."""
    for case in cases:
        dialect = "postgres" if case.dialect == "postgresql" else case.dialect
        actual = validate_read_only_sql(case.sql, dialect)
        if actual != case.expected.accepted:
            raise DatasetValidationError(f"Guardrail expectation mismatch: {case.case_id}")


def _read_json(path: Path, label: str) -> object:
    if not path.is_file():
        raise DatasetValidationError(f"Missing {label} file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(f"Invalid {label} file {path}: {exc}") from exc


def _load_cases(
    case_path: Path,
    model: type[CaseModel],
    case_ids: set[str],
) -> list[CaseModel]:
    raw_items = _read_json(case_path, "case")
    if not isinstance(raw_items, list):
        raise DatasetValidationError(f"Cases must be a JSON list: {case_path}")
    try:
        cases = [model.model_validate(item) for item in raw_items]
    except ValidationError as exc:
        raise DatasetValidationError(f"Invalid case in {case_path}: {exc}") from exc
    for case in cases:
        _validate_unique_id(case_ids, case.case_id, case_path.name)
    return cases


def _validate_unique_id(case_ids: set[str], new_id: str, case_file: str) -> None:
    if new_id in case_ids:
        raise DatasetValidationError(f"Duplicate case_id '{new_id}' in {case_file}")
    case_ids.add(new_id)


def _validate_expected_sql(case: QueryCase) -> None:
    assert case.expected is not None
    for dialect, sql in case.expected.sql_by_dialect.items():
        parsed_dialect = "postgres" if dialect == "postgresql" else dialect
        if not validate_read_only_sql(sql, parsed_dialect):
            raise DatasetValidationError(f"Unsafe expected SQL: {case.case_id}/{dialect}")
        statement = sqlglot.parse_one(sql, read=parsed_dialect)
        aliases = {projection.alias_or_name for projection in statement.expressions}
        if not set(case.expected.canonical_query.metrics).issubset(aliases):
            raise DatasetValidationError(f"Metric alias missing: {case.case_id}/{dialect}")


def _dimension_names(entity: CanonicalEntityDefinition) -> set[str]:
    return {dimension.name for dimension in entity.dimensions}


def _validate_entity_references(
    entity: CanonicalEntityDefinition,
    entities: dict[str, CanonicalEntityDefinition],
) -> None:
    fields = [dimension.field for dimension in entity.dimensions]
    if len(fields) != len(set(fields)):
        raise DatasetValidationError(f"Duplicate dimension field in {entity.entity}")
    for relationship in entity.relationships:
        if relationship.target_entity not in entities:
            raise DatasetValidationError(f"Unknown relationship target in {entity.entity}")


def _validate_metric_reference(
    metric: CanonicalMetricDefinition,
    entities: dict[str, CanonicalEntityDefinition],
    metrics: dict[str, CanonicalMetricDefinition],
) -> None:
    entity = entities.get(metric.target_entity)
    if not entity or entity.table_mapping != metric.source_table:
        raise DatasetValidationError(f"Invalid source mapping for metric {metric.metric}")
    if metric.field and metric.field not in _dimension_names(entity):
        raise DatasetValidationError(f"Invalid target field for metric {metric.metric}")
    if not set(metric.dependencies).issubset(metrics):
        raise DatasetValidationError(f"Unknown dependency for metric {metric.metric}")
    for reference in metric.allowed_dimensions:
        _validate_dimension_reference(reference, entities, metric.metric)


def _validate_discovery_relationships(
    case: DiscoveryCase,
    entities: dict[str, CanonicalEntityDefinition],
    raw_schema: RawSchema,
) -> None:
    declared = {
        (item["from_table"], item["from_column"], item["to_table"], item["to_column"])
        for item in raw_schema["relationships"]
    }
    for relation in case.expected.relationship_expectations:
        source = entities.get(relation.source_entity)
        target = entities.get(relation.target_entity)
        if not source or not target:
            raise DatasetValidationError(f"Unknown relationship entity in {case.case_id}")
        if relation.source_field not in _dimension_names(source):
            raise DatasetValidationError(f"Unknown source field in {case.case_id}")
        if relation.target_field not in _dimension_names(target):
            raise DatasetValidationError(f"Unknown target field in {case.case_id}")
        physical_key = (
            source.table_mapping,
            relation.source_field,
            target.table_mapping,
            relation.target_field,
        )
        if relation.inferred == (physical_key in declared):
            raise DatasetValidationError(f"Incorrect inferred flag in {case.case_id}")


def _validate_context_entities(
    case: MetricDefinitionCase,
    entities: dict[str, CanonicalEntityDefinition],
) -> None:
    if not set(case.canonical_context.entities).issubset(entities):
        raise DatasetValidationError(f"Unknown context entity in {case.case_id}")
    for reference in case.canonical_context.dimensions:
        _validate_dimension_reference(reference, entities, case.case_id)


def _validate_expected_metric(
    case: MetricDefinitionCase,
    metric: CanonicalMetricDefinition,
) -> None:
    assert case.expected_metric is not None
    expected = case.expected_metric
    canonical = (
        metric.business_name,
        metric.description,
        metric.synonyms,
        metric.metric_type,
        metric.target_entity,
        metric.source_table,
        metric.aggregation,
        metric.field,
        metric.business_formula,
        metric.sql_expression,
        metric.dependencies,
        [item.condition for item in metric.default_filters],
        metric.allowed_dimensions,
        metric.default_time_grain,
        metric.reference_source,
        metric.status,
        metric.owner,
    )
    benchmark = (
        expected.business_name,
        expected.description,
        expected.synonyms,
        expected.metric_type,
        expected.target_entity,
        expected.source_table,
        expected.aggregation,
        expected.field,
        expected.business_formula,
        expected.sql_expression,
        expected.dependencies,
        [item.condition for item in expected.default_filters],
        expected.allowed_dimensions,
        expected.default_time_grain,
        expected.reference_source,
        expected.status,
        expected.owner,
    )
    if canonical != benchmark:
        raise DatasetValidationError(f"Metric ground truth mismatch in {case.case_id}")


def _validate_query_case(
    case: QueryCase,
    entities: dict[str, CanonicalEntityDefinition],
    metrics: dict[str, CanonicalMetricDefinition],
) -> None:
    assert case.expected is not None
    expected = case.expected
    query = expected.canonical_query
    if expected.domain != query.domain:
        raise DatasetValidationError(f"Domain mismatch in {case.case_id}")
    if not set(query.metrics).issubset(metrics):
        raise DatasetValidationError(f"Unknown query metric in {case.case_id}")
    if not set(query.entities_in_path + [query.primary_entity]).issubset(entities):
        raise DatasetValidationError(f"Unknown query entity in {case.case_id}")
    if set(expected.retrieval.metrics) != set(query.metrics):
        raise DatasetValidationError(f"Retrieval metric mismatch in {case.case_id}")
    if not set(query.entities_in_path).issubset(expected.retrieval.entities):
        raise DatasetValidationError(f"Retrieval entity mismatch in {case.case_id}")
    _validate_retrieved_relationships(case, entities)
    _validate_query_dimensions(case, entities)
    _validate_query_metric_contract(case, metrics)


def _validate_query_metric_contract(
    case: QueryCase,
    metrics: dict[str, CanonicalMetricDefinition],
) -> None:
    assert case.expected is not None
    query = case.expected.canonical_query
    selected = [metrics[name] for name in query.metrics]
    required_entities = {metric.target_entity for metric in selected}
    if not required_entities.issubset(query.entities_in_path):
        raise DatasetValidationError(f"Metric entity missing from path in {case.case_id}")
    allowed = {dimension for metric in selected for dimension in metric.allowed_dimensions}
    if not set(query.dimensions).issubset(allowed):
        raise DatasetValidationError(f"Metric dimension not allowed in {case.case_id}")


def _validate_query_dimensions(
    case: QueryCase,
    entities: dict[str, CanonicalEntityDefinition],
) -> None:
    assert case.expected is not None
    query = case.expected.canonical_query
    references = list(query.dimensions)
    references.extend(item.dimension for item in query.time_filters)
    references.extend(item.dimension for item in query.where_conditions)
    references.extend(case.expected.retrieval.dimensions)
    for reference in references:
        _validate_dimension_reference(reference, entities, case.case_id)


def _validate_dimension_reference(
    reference: str,
    entities: dict[str, CanonicalEntityDefinition],
    case_id: str,
) -> None:
    if "." not in reference:
        raise DatasetValidationError(f"Unqualified dimension in {case_id}: {reference}")
    entity_name, dimension_name = reference.split(".", 1)
    entity = entities.get(entity_name)
    if not entity or dimension_name not in _dimension_names(entity):
        raise DatasetValidationError(f"Unknown dimension in {case_id}: {reference}")


def _validate_retrieved_relationships(
    case: QueryCase,
    entities: dict[str, CanonicalEntityDefinition],
) -> None:
    assert case.expected is not None
    for reference in case.expected.retrieval.relationships:
        parts = reference.split("->")
        if len(parts) != 2 or parts[0] not in entities or parts[1] not in entities:
            raise DatasetValidationError(f"Invalid relationship reference in {case.case_id}")
        targets = {item.target_entity for item in entities[parts[0]].relationships}
        if parts[1] not in targets:
            raise DatasetValidationError(f"Unknown relationship in {case.case_id}: {reference}")
