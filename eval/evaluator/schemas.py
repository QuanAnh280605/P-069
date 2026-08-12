"""Strict contracts for deterministic evaluation inputs and results."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from eval.dataset.models import Aggregation, Dialect, MetricType, RelationType, TimeGrain

EVALUATION_CONTRACT_VERSION = "2.0.0"
CaseStatus = Literal["passed", "failed", "error", "skipped", "not_available"]


class StrictEvaluationModel(BaseModel):
    """Reject unknown fields and make evaluation data immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationConfig(StrictEvaluationModel):
    """Configure every threshold and safety bound used by evaluators."""

    fuzzy_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    semantic_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    float_absolute_tolerance: float = Field(default=1e-6, ge=0.0)
    float_relative_tolerance: float = Field(default=1e-6, ge=0.0)
    statement_timeout_seconds: int = Field(default=15, ge=1, le=15)
    default_limit: int = Field(default=100, ge=1, le=1000)
    maximum_limit: int = Field(default=1000, ge=1, le=1000)
    execution_dialect: Literal["sqlite"] = "sqlite"

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        """Require the default row limit not to exceed the maximum."""
        if self.default_limit > self.maximum_limit:
            raise ValueError("default_limit must not exceed maximum_limit")
        return self


class MatchCounts(StrictEvaluationModel):
    """Store set-matching true-positive, false-positive and false-negative counts."""

    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)


class PrecisionRecallF1(StrictEvaluationModel):
    """Store bounded precision, recall and F1 values."""

    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)


class EvaluationIssue(StrictEvaluationModel):
    """Describe a safe, structured evaluation diagnostic."""

    code: str
    message: str
    field: str | None = None
    expected: JsonValue | None = None
    actual: JsonValue | None = None


class TextSimilarityScore(StrictEvaluationModel):
    """Keep exact, fuzzy and semantic name scores as structured data."""

    exact_match: float = Field(ge=0.0, le=1.0)
    fuzzy_similarity: float = Field(ge=0.0, le=1.0)
    semantic_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    semantic_status: Literal["available", "not_available"]
    accepted: bool

    @model_validator(mode="after")
    def validate_semantic_status(self) -> Self:
        """Keep semantic availability consistent with its optional score."""
        unavailable = self.semantic_status == "not_available"
        if unavailable != (self.semantic_similarity is None):
            raise ValueError("semantic status must match score availability")
        return self


class FieldScore(StrictEvaluationModel):
    """Describe the score and availability of one evaluated component."""

    component: str
    status: CaseStatus = "passed"
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    matched: bool | None = None
    counts: MatchCounts | None = None
    metrics: PrecisionRecallF1 | None = None
    text_similarity: TextSimilarityScore | None = None
    diagnostics: tuple[str, ...] = ()


class CaseEvaluationResult(StrictEvaluationModel):
    """Contain all component scores and issues for one benchmark case."""

    case_id: str
    status: CaseStatus
    component_scores: tuple[FieldScore, ...] = ()
    issues: tuple[EvaluationIssue, ...] = ()
    tags: tuple[str, ...] = ()


class SuiteEvaluationResult(StrictEvaluationModel):
    """Contain versioned aggregate and per-case evaluation results."""

    contract_version: str = EVALUATION_CONTRACT_VERSION
    domain: str
    dataset_version: str
    dataset_contract_version: str
    dataset_review_status: Literal["pending", "approved"]
    frozen_evaluation_date: datetime
    evaluation_config: EvaluationConfig
    total_cases: int = Field(ge=0)
    evaluated_cases: int = Field(ge=0)
    micro: PrecisionRecallF1 | None = None
    macro_score: float | None = Field(default=None, ge=0.0, le=1.0)
    group_scores: tuple[GroupScore, ...] = ()
    cases: tuple[CaseEvaluationResult, ...] = ()


class GroupScore(StrictEvaluationModel):
    """Aggregate available component scores for one case tag."""

    tag: str
    case_count: int = Field(ge=1)
    macro_score: float = Field(ge=0.0, le=1.0)
    case_ids: tuple[str, ...]


class CandidateDimension(StrictEvaluationModel):
    """Represent a candidate dimension emitted during enrichment."""

    name: str
    business_name: str


class CandidateRelationship(StrictEvaluationModel):
    """Represent a candidate relationship with an explicit source and target."""

    source_entity: str
    source_field: str
    target_entity: str
    target_field: str
    relation_type: RelationType
    inferred: bool = False


class CandidateEntity(StrictEvaluationModel):
    """Represent one candidate enriched entity."""

    entity: str
    business_name: str
    dimensions: tuple[CandidateDimension, ...] = ()
    relationships: tuple[CandidateRelationship, ...] = ()


class CandidateEnrichmentOutput(StrictEvaluationModel):
    """Represent a complete candidate enrichment result."""

    entities: tuple[CandidateEntity, ...] | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require exactly one successful output or error code."""
        if (self.entities is None) == (self.error_code is None):
            raise ValueError("set exactly one of entities or error_code")
        return self


class CandidateMetricFilter(StrictEvaluationModel):
    """Represent one candidate metric filter."""

    condition: str


class CandidateMetricDefinition(StrictEvaluationModel):
    """Represent a generated simple or derived metric definition."""

    name: str
    business_name: str
    description: str = ""
    synonyms: tuple[str, ...] = ()
    metric_type: MetricType
    target_entity: str
    source_table: str
    aggregation: Aggregation
    field: str | None = None
    business_formula: str
    sql_expression: str
    dependencies: tuple[str, ...] = ()
    default_filters: tuple[CandidateMetricFilter, ...] = ()
    allowed_dimensions: tuple[str, ...]
    default_time_grain: TimeGrain
    reference_source: str = ""
    status: Literal["draft", "approved"] = "draft"
    owner: str = ""
    expected_preview_facts: tuple[str, ...] = ()


class CandidateMetricOutput(StrictEvaluationModel):
    """Represent mutually exclusive metric generation success or failure."""

    metric: CandidateMetricDefinition | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require exactly one metric or error code."""
        if (self.metric is None) == (self.error_code is None):
            raise ValueError("set exactly one of metric or error_code")
        return self


class CandidateTimeFilter(StrictEvaluationModel):
    """Represent a candidate canonical time filter."""

    dimension: str
    granularity: TimeGrain
    range: str


class CandidateWhereCondition(StrictEvaluationModel):
    """Represent a candidate canonical where condition."""

    dimension: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in", "like"]
    value: JsonValue


class CandidateCanonicalQuery(StrictEvaluationModel):
    """Represent a candidate Canonical Query Model."""

    intent: str
    domain: str
    primary_entity: str
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    time_filters: tuple[CandidateTimeFilter, ...] = ()
    where_conditions: tuple[CandidateWhereCondition, ...] = ()
    entities_in_path: tuple[str, ...] = ()


class CandidateCompilerOutput(StrictEvaluationModel):
    """Represent mutually exclusive compiler success or failure."""

    canonical_query: CandidateCanonicalQuery | None = None
    sql: str | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require both success fields or one error code."""
        success = self.canonical_query is not None and self.sql is not None
        partial = (self.canonical_query is None) != (self.sql is None)
        if partial or success == (self.error_code is not None):
            raise ValueError("set canonical_query and sql, or error_code")
        return self


class CandidateGuardrailOutput(StrictEvaluationModel):
    """Represent the system-under-test SQL guardrail decision."""

    accepted: bool
    sql: str | None = None
    error_code: str | None = None
    effective_limit: int | None = Field(default=None, ge=1, le=1000)
    effective_timeout_seconds: int | None = Field(default=None, ge=1, le=15)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Validate accepted and rejected guardrail result shapes."""
        if self.accepted and (self.sql is None or self.error_code is not None):
            raise ValueError("accepted output requires sql and forbids error_code")
        if self.accepted and (self.effective_limit is None or self.effective_timeout_seconds is None):
            raise ValueError("accepted output requires effective limit and timeout")
        if not self.accepted and (self.error_code is None or self.sql is not None):
            raise ValueError("rejected output requires error_code and forbids sql")
        if not self.accepted and (self.effective_limit is not None or self.effective_timeout_seconds is not None):
            raise ValueError("rejected output forbids effective limit and timeout")
        return self


class ExecutionResult(StrictEvaluationModel):
    """Contain normalized columns and rows from isolated SQLite execution."""

    columns: tuple[str, ...]
    rows: tuple[tuple[JsonValue, ...], ...]


class GuardrailAdapterOutput(StrictEvaluationModel):
    """Compatibility alias payload retained for external adapters."""

    dialect: Dialect
    result: CandidateGuardrailOutput


class DomainCandidateOutputs(StrictEvaluationModel):
    """Bundle typed candidate outputs for a complete domain replay."""

    enrichment: dict[str, CandidateEnrichmentOutput] = Field(default_factory=dict)
    metrics: dict[str, CandidateMetricOutput] = Field(default_factory=dict)
    compiler: dict[str, CandidateCompilerOutput] = Field(default_factory=dict)


class DomainEvaluationResult(StrictEvaluationModel):
    """Contain every component suite produced for one domain evaluation."""

    contract_version: str = EVALUATION_CONTRACT_VERSION
    domain: str
    dataset_version: str
    dataset_contract_version: str
    dataset_review_status: Literal["pending", "approved"]
    frozen_evaluation_date: datetime
    evaluation_config: EvaluationConfig
    enrichment: SuiteEvaluationResult
    metrics: SuiteEvaluationResult
    compiler: SuiteEvaluationResult
    guardrails: SuiteEvaluationResult
