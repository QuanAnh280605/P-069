# eval/evaluator/hybrid/catalog.py
"""Frozen task, metric, weight, threshold, and gate catalogs (spec §7, §9.1)."""

from __future__ import annotations

from dataclasses import dataclass

from eval.evaluator.hybrid.contracts import MetricType
from eval.evaluator.hybrid.samples import TaskName

SUITE_WEIGHTS: dict[str, float] = {
    "discovery": 0.15,
    "enrichment": 0.20,
    "metric_generation": 0.25,
    "query_compilation": 0.25,
    "guardrail": 0.15,
}

SUITE_MINIMUMS: dict[str, float] = {
    "discovery": 0.95,
    "enrichment": 0.85,
    "metric_generation": 0.85,
    "query_compilation": 0.90,
    "guardrail": 0.95,
}

JUDGE_WEIGHT_CAPS: dict[str, float] = {"enrichment": 0.30, "metric_generation": 0.25}


@dataclass(frozen=True)
class MetricSpec:
    """Describe one registered metric and its aggregation role."""

    name: str
    task: TaskName
    metric_type: MetricType
    threshold: float
    weight: float
    required: bool = True
    prerequisites: tuple[str, ...] = ()


_DISCOVERY: tuple[MetricSpec, ...] = (
    MetricSpec("table_precision", "discovery", "deterministic", 0.95, 0.0),
    MetricSpec("table_recall", "discovery", "deterministic", 0.95, 0.0),
    MetricSpec("table_f1", "discovery", "deterministic", 0.95, 0.4),
    MetricSpec("column_f1", "discovery", "deterministic", 0.95, 0.3),
    MetricSpec("primary_key_accuracy", "discovery", "deterministic", 0.95, 0.15),
    MetricSpec("relationship_f1", "discovery", "deterministic", 0.95, 0.15),
)

_ENRICHMENT: tuple[MetricSpec, ...] = (
    MetricSpec("entity_f1", "enrichment", "deterministic", 0.95, 0.3),
    MetricSpec("dimension_f1", "enrichment", "deterministic", 0.95, 0.2),
    MetricSpec("relationship_accuracy", "enrichment", "deterministic", 0.95, 0.1),
    MetricSpec("business_name_similarity", "enrichment", "deterministic", 0.85, 0.1),
    MetricSpec("business_semantic_correctness", "enrichment", "ai_judge", 0.80, 0.3, prerequisites=("entity_f1",)),
)

_METRIC_GENERATION: tuple[MetricSpec, ...] = (
    MetricSpec("metric_identity_accuracy", "metric_generation", "deterministic", 0.95, 0.25),
    MetricSpec("formula_equivalence", "metric_generation", "deterministic", 0.85, 0.15),
    MetricSpec("sql_expression_equivalence", "metric_generation", "deterministic", 0.95, 0.15),
    MetricSpec("filter_accuracy", "metric_generation", "deterministic", 0.95, 0.05),
    MetricSpec("allowed_dimension_f1", "metric_generation", "deterministic", 0.95, 0.15),
    MetricSpec(
        "business_definition_correctness",
        "metric_generation",
        "ai_judge",
        0.80,
        0.15,
        prerequisites=("metric_identity_accuracy",),
    ),
    MetricSpec(
        "formula_semantic_correctness",
        "metric_generation",
        "ai_judge",
        0.80,
        0.10,
        prerequisites=("metric_identity_accuracy",),
    ),
)

_QUERY_COMPILATION: tuple[MetricSpec, ...] = (
    MetricSpec("request_validation_accuracy", "query_compilation", "deterministic", 0.95, 0.15),
    MetricSpec("selection_preservation_accuracy", "query_compilation", "deterministic", 0.95, 0.15),
    MetricSpec("invalid_selection_rejection", "query_compilation", "deterministic", 0.95, 0.10),
    MetricSpec("sql_ast_equivalence", "query_compilation", "deterministic", 0.95, 0.30),
    MetricSpec("sql_execution_accuracy", "query_compilation", "deterministic", 0.95, 0.20),
    MetricSpec("result_schema_accuracy", "query_compilation", "deterministic", 0.95, 0.10),
)

_GUARDRAIL: tuple[MetricSpec, ...] = (
    MetricSpec("unsafe_sql_rejection", "guardrail", "deterministic", 1.0, 0.30),
    MetricSpec("valid_select_acceptance", "guardrail", "deterministic", 1.0, 0.20),
    MetricSpec("limit_enforcement", "guardrail", "deterministic", 1.0, 0.20),
    MetricSpec("timeout_enforcement", "guardrail", "deterministic", 1.0, 0.15),
    MetricSpec("error_code_accuracy", "guardrail", "deterministic", 1.0, 0.15),
)

_METRICS: tuple[MetricSpec, ...] = (
    *_DISCOVERY,
    *_ENRICHMENT,
    *_METRIC_GENERATION,
    *_QUERY_COMPILATION,
    *_GUARDRAIL,
)

_BY_NAME: dict[str, MetricSpec] = {spec.name: spec for spec in _METRICS}


def catalog_spec(metric_name: str) -> MetricSpec:
    """Return the frozen specification of one registered metric."""
    return _BY_NAME[metric_name]


def metrics_for_task(task: TaskName) -> tuple[MetricSpec, ...]:
    """Return every registered metric for one task, in catalog order."""
    return tuple(spec for spec in _METRICS if spec.task == task)


def all_metric_specs() -> tuple[MetricSpec, ...]:
    """Return the complete frozen metric catalog."""
    return _METRICS


def task_names() -> tuple[TaskName, ...]:
    """Return every task that owns at least one metric."""
    return tuple(SUITE_WEIGHTS)  # type: ignore[return-value]
