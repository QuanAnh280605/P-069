"""Structured, Pydantic-validated judge output (no chain-of-thought)."""

from __future__ import annotations

from pydantic import Field, field_validator

from eval.evaluator.schemas import StrictEvaluationModel


class CriterionScore(StrictEvaluationModel):
    """Score one rubric criterion with a concise justification."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    justification: str = ""


class JudgeVerdict(StrictEvaluationModel):
    """Contain the complete structured verdict of one judge call."""

    criteria: list[CriterionScore] = Field(min_length=1)
    overall: float = Field(ge=0.0, le=1.0)
    summary: str = ""

    @field_validator("criteria")
    @classmethod
    def unique_names(cls, value: list[CriterionScore]) -> list[CriterionScore]:
        """Reject duplicate criterion names so weights apply exactly once."""
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("criterion names must be unique")
        return value


def weighted_score(verdict: JudgeVerdict, rubric: tuple[tuple[str, float], ...]) -> float:
    """Compute the rubric-weighted score; missing criteria count as zero."""
    by_name = {item.name: item.score for item in verdict.criteria}
    return sum(weight * by_name.get(name, 0.0) for name, weight in rubric)
