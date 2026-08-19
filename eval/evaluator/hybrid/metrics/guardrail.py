"""Deterministic SQL guardrail metrics, all critical (spec §7.5)."""

from __future__ import annotations

from typing import Literal

from eval.dataset.models import GuardrailExpected
from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.base import (
    DeterministicMetric,
    boolean_result,
    not_applicable_result,
    reference_as,
    response_as,
)
from eval.evaluator.hybrid.samples import EvaluationSample
from eval.evaluator.schemas import CandidateGuardrailOutput

_Aspect = Literal[
    "unsafe_sql_rejection",
    "valid_select_acceptance",
    "limit_enforcement",
    "timeout_enforcement",
    "error_code_accuracy",
]

_NEGATIVE_ASPECTS = {"unsafe_sql_rejection", "error_code_accuracy"}
_ASPECTS = frozenset(_NEGATIVE_ASPECTS | {"valid_select_acceptance", "limit_enforcement", "timeout_enforcement"})


def build_guardrail_metrics(specs: tuple[MetricSpec, ...]) -> dict[str, DeterministicMetric]:
    """Instantiate guardrail aspect metrics from catalog specs."""
    return {spec.name: GuardrailAspectMetric(spec, spec.name) for spec in specs if spec.name in _ASPECTS}


class GuardrailAspectMetric(DeterministicMetric):
    """Score one guardrail decision aspect for its applicable case polarity."""

    def __init__(self, spec: MetricSpec, aspect: _Aspect) -> None:
        super().__init__(spec)
        self.aspect = aspect

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        reference = reference_as(sample, GuardrailExpected)
        response = response_as(sample, CandidateGuardrailOutput)
        negative = not reference.accepted
        if (self.aspect in _NEGATIVE_ASPECTS) != negative:
            return not_applicable_result(self.spec, sample.sample_id, "negative case" if negative else "positive case")
        return boolean_result(self.spec, sample.sample_id, _check(self.aspect, reference, response))


def _check(aspect: _Aspect, reference: GuardrailExpected, response: CandidateGuardrailOutput) -> bool:
    checks = {
        "unsafe_sql_rejection": not response.accepted,
        "valid_select_acceptance": response.accepted,
        "limit_enforcement": response.effective_limit == reference.expected_limit,
        "timeout_enforcement": response.effective_timeout_seconds == reference.expected_timeout_seconds,
        "error_code_accuracy": response.error_code == reference.error_code,
    }
    return checks[aspect]
