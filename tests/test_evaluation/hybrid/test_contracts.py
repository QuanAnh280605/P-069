"""Tests for hybrid evaluator metric-level contracts."""

import pytest
from pydantic import ValidationError

from eval.evaluator.hybrid.contracts import (
    HYBRID_CONTRACT_VERSION,
    MetricProvenance,
    MetricResult,
)


def _result(**overrides: object) -> MetricResult:
    base = dict(
        sample_id="s1",
        metric="table_f1",
        metric_type="deterministic",
        status="passed",
        score=0.9,
        threshold=0.95,
    )
    return MetricResult(**{**base, **overrides})  # type: ignore[arg-type]


def test_contract_version_is_frozen() -> None:
    assert HYBRID_CONTRACT_VERSION == "1.0.0"


def test_result_is_strict_and_frozen() -> None:
    result = _result()
    with pytest.raises(ValidationError):
        MetricResult(sample_id="s1")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        setattr(result, "score", 0.1)  # noqa: B010
    with pytest.raises(ValidationError):
        _result(unknown_field=1)


def test_score_bounds_and_defaults() -> None:
    with pytest.raises(ValidationError):
        _result(score=1.5)
    result = _result(score=None, status="not_applicable")
    assert result.reason == ""
    assert result.details == {}
    assert result.provenance == MetricProvenance()


def test_scored_property() -> None:
    assert _result(status="passed", score=0.99).scored is True
    assert _result(status="failed", score=0.1).scored is True
    assert _result(status="error").scored is False
    assert _result(status="not_applicable").scored is False
