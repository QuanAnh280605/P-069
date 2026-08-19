"""Tests for the schema-extraction fidelity (discovery) evaluator."""

from __future__ import annotations

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.evaluator.discovery_eval import (
    CandidateDiscoveryOutput,
    evaluate_discovery_suite,
)
from eval.evaluator.schemas import EvaluationConfig

GOLDEN_ROOT = "eval/golden_dataset"


async def _load():
    from pathlib import Path

    return await load_domain_dataset(Path(GOLDEN_ROOT), "ecommerce")


@pytest.mark.asyncio
async def test_perfect_extraction_scores_one():
    dataset = await _load()
    case = dataset.discovery_cases[0]
    perfect = CandidateDiscoveryOutput(raw_schema=dataset.raw_schemas[case.raw_schema_ref])
    result = await evaluate_discovery_suite(dataset, {case.case_id: perfect}, EvaluationConfig())
    assert result.macro_score == pytest.approx(1.0)
    assert result.cases[0].status == "passed"


@pytest.mark.asyncio
async def test_missing_table_lowers_score():
    dataset = await _load()
    case = dataset.discovery_cases[0]
    raw = {**dataset.raw_schemas[case.raw_schema_ref], "tables": []}
    result = await evaluate_discovery_suite(
        dataset,
        {case.case_id: CandidateDiscoveryOutput(raw_schema=raw)},
        EvaluationConfig(),
    )
    assert result.cases[0].status == "failed"
    assert result.macro_score is not None and result.macro_score < 1.0


@pytest.mark.asyncio
async def test_error_code_marks_case_error():
    dataset = await _load()
    case = dataset.discovery_cases[0]
    result = await evaluate_discovery_suite(
        dataset,
        {case.case_id: CandidateDiscoveryOutput(error_code="PARSE_ERROR")},
        EvaluationConfig(),
    )
    assert result.cases[0].status == "error"


@pytest.mark.asyncio
async def test_missing_candidate_is_not_available():
    dataset = await _load()
    result = await evaluate_discovery_suite(dataset, {}, EvaluationConfig())
    assert result.cases[0].status == "not_available"
