"""Deterministic metric base class, result builders, and payload accessors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar

from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricProvenance, MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.samples import EvaluationSample
from eval.evaluator.schemas import JsonValue
from eval.evaluator.scoring import SetMatchResult


class CandidateFailure(RuntimeError):  # noqa: N818 — name is fixed by the metric contract
    """Signal that the candidate response cannot be scored (error or empty)."""


T = TypeVar("T")


@dataclass
class DeterministicMetric(ABC):
    """Isolate one deterministic scoring rule behind the unified contract."""

    spec: MetricSpec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def metric_type(self) -> str:
        return "deterministic"

    async def score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        """Delegate to the rule and convert failures into safe results."""
        try:
            return await self._score(sample, context)
        except CandidateFailure as exc:
            return boolean_result(self.spec, sample.sample_id, False, f"CANDIDATE_ERROR:{exc}")
        except Exception as exc:
            return error_result(self.spec, sample.sample_id, exc)

    @abstractmethod
    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        """Compute the metric result for one applicable sample."""


def error_result(spec: MetricSpec, sample_id: str, exc: Exception) -> MetricResult:
    """Build an ``error`` result that records the exception class name."""
    return MetricResult(
        sample_id=sample_id,
        metric=spec.name,
        metric_type=spec.metric_type,
        status="error",
        threshold=spec.threshold,
        reason=type(exc).__name__,
    )


def not_applicable_result(spec: MetricSpec, sample_id: str, reason: str) -> MetricResult:
    """Build a ``not_applicable`` result explaining why scoring was skipped."""
    return MetricResult(
        sample_id=sample_id,
        metric=spec.name,
        metric_type=spec.metric_type,
        status="not_applicable",
        threshold=spec.threshold,
        reason=reason,
    )


def boolean_result(spec: MetricSpec, sample_id: str, matched: bool, reason: str = "") -> MetricResult:
    """Build a passed/failed result from one boolean decision."""
    return MetricResult(
        sample_id=sample_id,
        metric=spec.name,
        metric_type=spec.metric_type,
        status="passed" if matched else "failed",
        score=float(matched),
        threshold=spec.threshold,
        reason=reason,
    )


def score_result(
    spec: MetricSpec,
    sample_id: str,
    score: float,
    reason: str = "",
    details: dict[str, JsonValue] | None = None,
    provenance: MetricProvenance | None = None,
) -> MetricResult:
    """Build a thresholded numeric-score result with details and provenance."""
    passed = score >= spec.threshold
    return MetricResult(
        sample_id=sample_id,
        metric=spec.name,
        metric_type=spec.metric_type,
        status="passed" if passed else "failed",
        score=score,
        threshold=spec.threshold,
        reason=reason,
        details=details or {},
        provenance=provenance or MetricProvenance(),
    )


def set_match_result(spec: MetricSpec, sample_id: str, match: SetMatchResult, field: str = "f1") -> MetricResult:
    """Build a result from one set-match score field and its counts."""
    value = getattr(match.metrics, field)
    details = {
        "true_positive": match.counts.true_positive,
        "false_positive": match.counts.false_positive,
        "false_negative": match.counts.false_negative,
        "duplicates": [repr(d) for d in match.duplicates],
    }
    return score_result(spec, sample_id, value, details=details)


def reference_as(sample: EvaluationSample, cls: type[T]) -> T:
    """Return the typed reference payload or raise ``TypeError``."""
    if not isinstance(sample.reference, cls):
        raise TypeError(f"expected {cls.__name__} reference for task {sample.task}")
    return sample.reference


def response_as(sample: EvaluationSample, cls: type[T]) -> T:
    """Return the typed response payload or raise ``CandidateFailure``."""
    if sample.response is None:
        raise CandidateFailure("no candidate response")
    if not isinstance(sample.response, cls):
        raise TypeError(f"expected {cls.__name__} response for task {sample.task}")
    return sample.response
