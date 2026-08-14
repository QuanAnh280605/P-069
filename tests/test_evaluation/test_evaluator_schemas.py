"""Tests for strict and mutually exclusive evaluator contracts."""

import pytest
from pydantic import ValidationError

from eval.evaluator.schemas import (
    CandidateCompilerOutput,
    CandidateEnrichmentOutput,
    EvaluationConfig,
    TextSimilarityScore,
)


def test_evaluation_config_validates_limits() -> None:
    with pytest.raises(ValidationError):
        EvaluationConfig(default_limit=101, maximum_limit=100)


def test_candidate_enrichment_rejects_ambiguous_outcome() -> None:
    with pytest.raises(ValidationError):
        CandidateEnrichmentOutput(entities=(), error_code="FAILED")


def test_compiler_output_rejects_partial_success() -> None:
    with pytest.raises(ValidationError):
        CandidateCompilerOutput(sql="SELECT 1")


def test_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationConfig(unknown=True)


def test_semantic_status_must_match_score_availability() -> None:
    with pytest.raises(ValidationError):
        TextSimilarityScore(
            exact_match=0.0,
            fuzzy_similarity=0.5,
            semantic_similarity=None,
            semantic_status="available",
            accepted=False,
        )
