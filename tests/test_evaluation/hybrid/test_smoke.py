"""Tests for golden-derived smoke candidates and the smoke guardrail adapter."""

from eval.evaluator.hybrid.smoke import (
    SmokeGuardrailAdapter,
    smoke_compiler,
    smoke_discovery,
    smoke_enrichment,
    smoke_metrics,
)
from eval.evaluator.schemas import EvaluationConfig
from eval.evaluator.sql_normalization import effective_limit


async def test_smoke_adapter_accepts_guarded_select(mini_dataset) -> None:
    adapter = SmokeGuardrailAdapter(EvaluationConfig())
    assert callable(adapter.validate)  # structurally satisfies the GuardrailAdapter protocol
    decision = await adapter.validate("SELECT * FROM orders LIMIT 100", "sqlite")
    assert decision.accepted and decision.effective_limit == 100


async def test_smoke_adapter_clamps_oversized_limit(mini_dataset) -> None:
    adapter = SmokeGuardrailAdapter(EvaluationConfig())
    decision = await adapter.validate("SELECT * FROM orders LIMIT 5000", "sqlite")
    assert decision.effective_limit == 1000
    assert decision.sql is not None
    assert effective_limit(decision.sql, "sqlite") == 1000


async def test_smoke_adapter_injects_default_limit(mini_dataset) -> None:
    adapter = SmokeGuardrailAdapter(EvaluationConfig())
    decision = await adapter.validate("SELECT * FROM orders", "sqlite")
    assert decision.effective_limit == 100
    assert decision.sql is not None
    assert effective_limit(decision.sql, "sqlite") == 100


async def test_smoke_adapter_rejects_unsafe_sql(mini_dataset) -> None:
    adapter = SmokeGuardrailAdapter(EvaluationConfig())
    decision = await adapter.validate("DELETE FROM orders", "sqlite")
    assert not decision.accepted and decision.error_code is not None


def test_smoke_discovery_replays_golden_schemas(mini_dataset) -> None:
    candidates = smoke_discovery(mini_dataset)
    case = mini_dataset.discovery_cases[0]
    assert candidates[case.case_id].raw_schema == mini_dataset.raw_schemas[case.raw_schema_ref]


def test_smoke_enrichment_covers_canonical_entities(mini_dataset) -> None:
    output = smoke_enrichment(mini_dataset)[mini_dataset.discovery_cases[0].case_id]
    assert output.entities is not None
    assert {entity.entity for entity in output.entities} == set(mini_dataset.canonical_entities)


def test_smoke_metrics_maps_negative_cases_to_errors(mini_dataset) -> None:
    candidates = smoke_metrics(mini_dataset)
    negative = next(c for c in mini_dataset.metric_cases if c.expected_error is not None)
    assert candidates[negative.case_id].error_code == negative.expected_error


def test_smoke_compiler_maps_negative_cases_to_errors(mini_dataset) -> None:
    candidates = smoke_compiler(mini_dataset)
    negative = next(c for c in mini_dataset.query_cases if c.expected_error is not None)
    assert candidates[negative.case_id].error_code == negative.expected_error
