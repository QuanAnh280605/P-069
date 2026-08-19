"""Tests for the hybrid evaluation sample envelope and builder."""

import pytest
from pydantic import ValidationError

from eval.dataset.models import GuardrailExpected
from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.hybrid.samples import (
    EvaluationSample,
    GuardrailInput,
    build_samples,
)
from eval.evaluator.schemas import (
    CandidateCompilerOutput,
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateGuardrailOutput,
    CandidateMetricDefinition,
    CandidateMetricOutput,
)
from tests.test_evaluation.hybrid.conftest import _metric_case, _raw_schema


def _guardrail_response() -> CandidateGuardrailOutput:
    return CandidateGuardrailOutput(
        accepted=True, sql="SELECT * FROM orders LIMIT 100", effective_limit=100, effective_timeout_seconds=15
    )


def _metric_candidate() -> CandidateMetricOutput:
    expected = _metric_case().expected_metric
    assert expected is not None
    return CandidateMetricOutput(
        metric=CandidateMetricDefinition(
            **expected.model_dump(),
            expected_preview_facts=("Tổng doanh thu",),
        )
    )


def test_envelope_accepts_typed_payloads(mini_dataset) -> None:
    sample = EvaluationSample(
        sample_id="guard_001",
        task="guardrail",
        input=GuardrailInput(sql="SELECT * FROM orders", dialect="sqlite"),
        reference=mini_dataset.guardrail_cases[0].expected,
        response=_guardrail_response(),
        tags=("mini",),
    )
    assert sample.task == "guardrail"
    assert isinstance(sample.reference, GuardrailExpected)


def test_envelope_rejects_unknown_fields(mini_dataset) -> None:
    with pytest.raises(ValidationError):
        EvaluationSample(
            sample_id="x",
            task="guardrail",
            input=GuardrailInput(sql="SELECT 1", dialect="sqlite"),
            reference=mini_dataset.guardrail_cases[0].expected,
            response=_guardrail_response(),
            unknown=1,
        )


def test_build_samples_covers_all_tasks(mini_dataset) -> None:
    compiler = CandidateCompilerOutput(
        canonical_query={
            "intent": "aggregate",
            "domain": "mini",
            "primary_entity": "orders",
            "metrics": ["total_revenue"],
            "dimensions": ["order_month"],
        },
        sql="SELECT order_month, SUM(amount) AS total FROM orders GROUP BY order_month LIMIT 100",
    )
    enrichment = CandidateEnrichmentOutput(
        entities=(
            CandidateEntity(
                entity="orders",
                business_name="Đơn hàng",
                dimensions=(CandidateDimension(name="order_amount", business_name="Giá trị đơn hàng"),),
            ),
        )
    )
    samples = build_samples(
        mini_dataset,
        discovery={"disc_001": CandidateDiscoveryOutput(raw_schema=_raw_schema())},
        enrichment={"disc_001": enrichment},
        metrics={"metric_001": _metric_candidate()},
        compiler={"query_001": compiler},
        guardrail={"guard_001": _guardrail_response()},
    )
    tasks = {sample.task for sample in samples}
    assert tasks == {"discovery", "enrichment", "metric_generation", "query_compilation", "guardrail"}
