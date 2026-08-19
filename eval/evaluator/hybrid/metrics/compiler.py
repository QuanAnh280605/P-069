"""Deterministic query-compiler metrics with guarded execution (spec §7.4)."""

from __future__ import annotations

from eval.evaluator.execution import EvaluationExecutionError, compare_query_result, execute_guarded_sql
from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.base import (
    CandidateFailure,
    DeterministicMetric,
    boolean_result,
    not_applicable_result,
    reference_as,
    score_result,
)
from eval.evaluator.hybrid.samples import EvaluationSample, QueryReference
from eval.evaluator.schemas import CandidateCompilerOutput, ExecutionResult
from eval.evaluator.sql_normalization import SqlValidationError, structurally_equal


def build_compiler_metrics(specs: tuple[MetricSpec, ...]) -> dict[str, DeterministicMetric]:
    """Instantiate compiler metrics from catalog specs."""
    factory = {
        "request_validation_accuracy": RequestValidationAccuracy,
        "selection_preservation_accuracy": SelectionPreservationAccuracy,
        "invalid_selection_rejection": InvalidSelectionRejection,
        "sql_ast_equivalence": SqlAstEquivalence,
        "sql_execution_accuracy": SqlExecutionAccuracy,
        "result_schema_accuracy": ResultSchemaAccuracy,
    }
    return {spec.name: factory[spec.name](spec) for spec in specs if spec.name in factory}


def _payload(sample: EvaluationSample) -> tuple[QueryReference, CandidateCompilerOutput]:
    """Return the reference/response pair for a query-compilation sample."""
    reference = reference_as(sample, QueryReference)
    response = sample.response
    if response is None:
        raise _MissingCandidate()
    if not isinstance(response, CandidateCompilerOutput):
        raise TypeError("wrong response type for query_compilation")
    return reference, response


class _MissingCandidate(CandidateFailure):
    """Signal that no candidate response exists for this sample."""

    def __init__(self) -> None:
        super().__init__("no candidate response")


def _negative(reference: QueryReference, response: CandidateCompilerOutput) -> bool:
    return reference.expected_error is not None or response.error_code is not None


class RequestValidationAccuracy(DeterministicMetric):
    """Score intent/domain/primary-entity agreement, or outcome on negative cases."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, response = _payload(sample)
        if _negative(reference, response):
            matched = reference.expected_error is not None and reference.expected_error == response.error_code
            return boolean_result(self.spec, sample.sample_id, matched, "outcome comparison")
        assert reference.expected is not None and response.canonical_query is not None
        expected_query, actual_query = reference.expected.canonical_query, response.canonical_query
        checks = (
            expected_query.intent == actual_query.intent,
            expected_query.domain == actual_query.domain,
            expected_query.primary_entity == actual_query.primary_entity,
        )
        return score_result(self.spec, sample.sample_id, sum(checks) / len(checks))


class SelectionPreservationAccuracy(DeterministicMetric):
    """Score metric and dimension selection preservation."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, response = _payload(sample)
        if _negative(reference, response):
            return not_applicable_result(self.spec, sample.sample_id, "negative case")
        assert reference.expected is not None and response.canonical_query is not None
        expected_query, actual_query = reference.expected.canonical_query, response.canonical_query
        checks = (
            set(expected_query.metrics) == set(actual_query.metrics),
            set(expected_query.dimensions) == set(actual_query.dimensions),
        )
        return score_result(self.spec, sample.sample_id, sum(checks) / len(checks))


class InvalidSelectionRejection(DeterministicMetric):
    """Score rejection behavior on negative compiler cases only."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, response = _payload(sample)
        if reference.expected_error is None:
            return not_applicable_result(self.spec, sample.sample_id, "positive case")
        return boolean_result(
            self.spec, sample.sample_id, response.error_code == reference.expected_error, "outcome comparison"
        )


class SqlAstEquivalence(DeterministicMetric):
    """Compare compiled SQL ASTs against the golden dialect SQL."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference, response = _payload(sample)
        if _negative(reference, response) or response.sql is None:
            return not_applicable_result(self.spec, sample.sample_id, "negative case")
        assert reference.expected is not None
        expected_sql = reference.expected.sql_by_dialect[context.config.execution_dialect]
        try:
            matched = structurally_equal(expected_sql, response.sql, "sqlite")
        except SqlValidationError as exc:
            return boolean_result(self.spec, sample.sample_id, False, str(exc))
        return boolean_result(self.spec, sample.sample_id, matched)


class SqlExecutionAccuracy(DeterministicMetric):
    """Execute guarded SQL on isolated SQLite and compare result rows."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        rows_or_na = await _rows_for(sample, context)
        if isinstance(rows_or_na, str):
            return not_applicable_result(self.spec, sample.sample_id, rows_or_na)
        if rows_or_na is None:
            return boolean_result(self.spec, sample.sample_id, False, "EXECUTION_FAILED")
        reference = reference_as(sample, QueryReference)
        matched = compare_query_result(rows_or_na, reference.expected_rows, context.config)
        return boolean_result(self.spec, sample.sample_id, matched)


class ResultSchemaAccuracy(DeterministicMetric):
    """Compare executed columns against the expected row schema."""

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        rows_or_na = await _rows_for(sample, context)
        if isinstance(rows_or_na, str):
            return not_applicable_result(self.spec, sample.sample_id, rows_or_na)
        if rows_or_na is None:
            return boolean_result(self.spec, sample.sample_id, False, "EXECUTION_FAILED")
        reference = reference_as(sample, QueryReference)
        expected_columns = tuple(reference.expected_rows[0].keys()) if reference.expected_rows else rows_or_na.columns
        return boolean_result(self.spec, sample.sample_id, tuple(rows_or_na.columns) == expected_columns)


async def _rows_for(sample: EvaluationSample, context: EvaluationContext) -> ExecutionResult | None | str:
    """Return cached execution result, None on failure, or a not-applicable reason."""
    reference, response = _payload(sample)
    if _negative(reference, response) or response.sql is None:
        return "negative case"
    if context.guardrail_adapter is None or context.dataset is None:
        return "execution prerequisites unavailable"
    if sample.sample_id in context.execution_cache:
        return context.execution_cache[sample.sample_id]
    result = await _execute_once(context, response.sql)
    context.execution_cache[sample.sample_id] = result
    return result


async def _execute_once(context: EvaluationContext, sql: str) -> ExecutionResult | None:
    """Run the guarded query once against the domain's isolated SQLite fixture."""
    assert context.dataset is not None
    source = context.dataset.domain_dir / "sources" / "sqlite"
    try:
        guarded = await context.guardrail_adapter.validate(sql, "sqlite")
        return await execute_guarded_sql(sql, source / "schema.sql", source / "seed_data.sql", guarded, context.config)
    except (EvaluationExecutionError, SqlValidationError):
        return None
