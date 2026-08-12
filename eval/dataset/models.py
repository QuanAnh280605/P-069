"""Strict Pydantic contracts for Golden Dataset artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Dialect = Literal["sqlite", "postgresql", "mysql"]
Aggregation = Literal["sum", "count", "avg", "min", "max", "count_distinct", "ratio"]
MetricType = Literal["simple", "derived"]
MetricStatus = Literal["draft", "approved"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
RelationType = Literal["BELONGS_TO", "HAS_MANY", "HAS_ONE"]


class StrictModel(BaseModel):
    """Reject unknown fields and keep loaded fixtures immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestCaseFiles(StrictModel):
    """Map benchmark suites to files relative to a domain directory."""

    discovery: str
    metric_definition: str
    query: str
    guardrail: str


class DomainManifest(StrictModel):
    """Describe one versioned Golden Dataset domain."""

    dataset_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    contract_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    domain: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    language: Literal["vi"] = "vi"
    supported_dialects: list[Dialect] = Field(min_length=1)
    execution_dialect: Dialect = "sqlite"
    review_status: Literal["pending", "approved"] = "pending"
    approved_by: list[str] = Field(default_factory=list)
    reviewed_at: datetime | None = None
    frozen_evaluation_date: datetime
    ground_truth_source: str
    ground_truth_metric_count: int = Field(ge=1)
    case_files: ManifestCaseFiles

    @model_validator(mode="after")
    def validate_execution_dialect(self) -> Self:
        """Require the execution dialect to be declared as supported."""
        if self.execution_dialect not in self.supported_dialects:
            raise ValueError("execution_dialect must be listed in supported_dialects")
        if len(self.supported_dialects) != len(set(self.supported_dialects)):
            raise ValueError("supported_dialects must not contain duplicates")
        if self.review_status == "approved" and not self.approved_by:
            raise ValueError("approved datasets require approved_by")
        if self.review_status == "approved" and self.reviewed_at is None:
            raise ValueError("approved datasets require reviewed_at")
        return self


class RelationshipExpectation(StrictModel):
    """Describe one expected canonical relationship."""

    source_entity: str
    source_field: str
    target_entity: str
    target_field: str
    relation_type: RelationType
    inferred: bool = False


class DiscoveryCaseExpected(StrictModel):
    """Describe the complete expected structural discovery output."""

    entity_refs: list[str] = Field(min_length=1)
    relationship_expectations: list[RelationshipExpectation]


class DiscoveryCase(StrictModel):
    """Represent a Stage 1 structural discovery benchmark case."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    source_type: Literal["live_connection", "sql_dump"]
    dialect: Dialect
    raw_schema_ref: str
    expected: DiscoveryCaseExpected
    tags: list[str] = Field(min_length=2)


class ExpectedMetricFilter(StrictModel):
    """Represent a normalized default filter for a metric."""

    condition: str = Field(min_length=1)


class ExpectedMetricDefinition(StrictModel):
    """Represent the expected CanonicalMetric for a natural-language request."""

    name: str
    business_name: str
    description: str
    synonyms: list[str] = Field(default_factory=list)
    metric_type: MetricType
    target_entity: str
    source_table: str
    aggregation: Aggregation
    field: str | None = None
    business_formula: str
    sql_expression: str
    dependencies: list[str] = Field(default_factory=list)
    default_filters: list[ExpectedMetricFilter] = Field(default_factory=list)
    allowed_dimensions: list[str] = Field(min_length=1)
    default_time_grain: TimeGrain
    reference_source: str
    status: MetricStatus
    owner: str


class MetricDefinitionCaseContext(StrictModel):
    """Describe approved canonical artifacts available to metric generation."""

    entities: list[str] = Field(min_length=1)
    dimensions: list[str] = Field(min_length=1)


class MetricDefinitionCase(StrictModel):
    """Represent a Stage 3 metric-definition benchmark case."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    request: str = Field(min_length=1)
    canonical_context: MetricDefinitionCaseContext
    expected_metric: ExpectedMetricDefinition | None = None
    expected_preview_facts: list[str] = Field(default_factory=list)
    expected_error: str | None = None
    tags: list[str] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require exactly one success or error outcome."""
        if (self.expected_metric is None) == (self.expected_error is None):
            raise ValueError("set exactly one of expected_metric or expected_error")
        if self.expected_metric and not self.expected_preview_facts:
            raise ValueError("successful metric cases require expected_preview_facts")
        return self


class RetrievalExpectation(StrictModel):
    """List canonical artifacts expected from retrieval."""

    metrics: list[str]
    entities: list[str]
    dimensions: list[str]
    relationships: list[str]


class TimeFilterExpectation(StrictModel):
    """Represent a normalized CanonicalQueryModel time filter."""

    dimension: str
    granularity: TimeGrain
    range: str


class WhereConditionExpectation(StrictModel):
    """Represent a typed CanonicalQueryModel filter."""

    dimension: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in", "like"]
    value: JsonValue


class CanonicalQueryModelExpectation(StrictModel):
    """Represent the normalized expected CanonicalQueryModel."""

    intent: str
    domain: str
    primary_entity: str
    metrics: list[str]
    dimensions: list[str]
    time_filters: list[TimeFilterExpectation] = Field(default_factory=list)
    where_conditions: list[WhereConditionExpectation] = Field(default_factory=list)
    entities_in_path: list[str] = Field(default_factory=list)


class QueryCaseExpected(StrictModel):
    """Describe all expected Stage 4 component outputs."""

    intent: str
    domain: str
    retrieval: RetrievalExpectation
    canonical_query: CanonicalQueryModelExpectation
    sql_by_dialect: dict[Dialect, str]
    result_ref: str


class QueryCase(StrictModel):
    """Represent a Stage 4 runtime query benchmark case."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    question: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    expected: QueryCaseExpected | None = None
    expected_error: str | None = None
    tags: list[str] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require exactly one success or error outcome."""
        if (self.expected is None) == (self.expected_error is None):
            raise ValueError("set exactly one of expected or expected_error")
        return self


class GuardrailExpected(StrictModel):
    """Describe expected SQL guardrail behavior."""

    accepted: bool
    error_code: str | None = None
    expected_limit: int | None = Field(default=None, ge=1, le=1000)
    expected_timeout_seconds: int | None = Field(default=None, ge=1, le=15)

    @model_validator(mode="after")
    def validate_error_code(self) -> Self:
        """Require an error code only for rejected SQL."""
        if self.accepted == (self.error_code is not None):
            raise ValueError("rejected SQL requires error_code; accepted SQL forbids it")
        if self.accepted and self.expected_limit is None:
            raise ValueError("accepted SQL requires expected_limit")
        if not self.accepted and self.expected_limit is not None:
            raise ValueError("rejected SQL forbids expected_limit")
        return self


class GuardrailCase(StrictModel):
    """Represent a SQL security guardrail benchmark case."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    sql: str = Field(min_length=1)
    dialect: Dialect = "sqlite"
    expected: GuardrailExpected
    tags: list[str] = Field(min_length=2)


class CanonicalDimensionDefinition(StrictModel):
    """Represent one approved canonical dimension fixture."""

    name: str
    business_name: str
    type: Literal["string", "number", "time", "boolean"]
    field: str
    primary_key: bool = False
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)


class CanonicalRelationshipDefinition(StrictModel):
    """Represent one approved canonical relationship fixture."""

    target_entity: str
    relation_type: RelationType
    join_condition: str
    inferred: bool = False


class CanonicalEntityDefinition(StrictModel):
    """Represent one approved canonical entity fixture."""

    entity: str
    table_mapping: str
    business_name: str
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    accepted_business_names: list[str] = Field(default_factory=list)
    dimensions: list[CanonicalDimensionDefinition]
    relationships: list[CanonicalRelationshipDefinition]


class CanonicalMetricDefinition(StrictModel):
    """Represent one approved canonical metric fixture."""

    metric: str
    business_name: str
    domain: str
    metric_type: MetricType
    target_entity: str
    source_table: str
    aggregation: Aggregation
    field: str | None = None
    business_formula: str
    sql_expression: str
    dependencies: list[str] = Field(default_factory=list)
    description: str = ""
    default_filters: list[ExpectedMetricFilter] = Field(default_factory=list)
    allowed_dimensions: list[str] = Field(min_length=1)
    default_time_grain: TimeGrain
    reference_source: str
    status: MetricStatus
    owner: str
    ground_truth_source: str
    synonyms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metric_contract(self) -> Self:
        """Reject inconsistent ratio and reference declarations."""
        if self.aggregation == "ratio" and self.metric_type != "derived":
            raise ValueError("ratio aggregation requires a derived metric")
        if self.metric in self.dependencies:
            raise ValueError("a metric cannot depend on itself")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("metric dependencies must not contain duplicates")
        if len(self.allowed_dimensions) != len(set(self.allowed_dimensions)):
            raise ValueError("allowed_dimensions must not contain duplicates")
        return self


ExpectedQueryResults = dict[str, list[dict[str, JsonValue]]]


class QueryReferenceCatalog(StrictModel):
    """Bundle canonical and result references used by Stage 4 validation."""

    entities: dict[str, CanonicalEntityDefinition]
    metrics: dict[str, CanonicalMetricDefinition]
    expected_results: ExpectedQueryResults
