"""Metric-level contracts shared by deterministic and AI-judge executors."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from eval.evaluator.schemas import StrictEvaluationModel

HYBRID_CONTRACT_VERSION = "1.0.0"

MetricType = Literal["deterministic", "ai_judge"]
MetricResultStatus = Literal["passed", "failed", "error", "not_applicable"]
RunStatus = Literal["PASS", "WARN", "FAIL", "INCOMPLETE"]
RunType = Literal["smoke", "benchmark", "release"]
CandidateSource = Literal["golden_derived", "agent_live", "agent_recorded"]
EvaluationProfile = Literal["pipeline", "component"]


class MetricProvenance(StrictEvaluationModel):
    """Record rubric, prompt, and model versions used to produce one score."""

    rubric_version: str | None = None
    prompt_version: str | None = None
    model: str | None = None


class MetricResult(StrictEvaluationModel):
    """Unify deterministic and AI-judge scores in one result contract."""

    sample_id: str
    metric: str
    metric_type: MetricType
    status: MetricResultStatus
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    details: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: MetricProvenance = Field(default_factory=MetricProvenance)

    @property
    def scored(self) -> bool:
        """Report whether this result contributes a numeric score."""
        return self.status in {"passed", "failed"} and self.score is not None
