"""Tests for CQM, compiler and injected guardrail evaluation."""

from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.evaluator.compiler_eval import evaluate_compiler_case, evaluate_guardrail_case
from eval.evaluator.schemas import (
    CandidateCanonicalQuery,
    CandidateCompilerOutput,
    CandidateGuardrailOutput,
    EvaluationConfig,
)

GOLDEN_ROOT = Path("eval/golden_dataset")


class ReplayGuardrail:
    """Replay a prebuilt guardrail output."""

    def __init__(self, output: CandidateGuardrailOutput) -> None:
        self.output = output

    async def validate(self, sql: str, dialect: str) -> CandidateGuardrailOutput:
        return self.output


@pytest.mark.asyncio
async def test_perfect_compiler_without_adapter_marks_execution_unavailable() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.query_cases if item.expected)
    expected = case.expected
    candidate = CandidateCompilerOutput(
        canonical_query=CandidateCanonicalQuery.model_validate(expected.canonical_query.model_dump()),
        sql=expected.sql_by_dialect["sqlite"],
    )
    result = await evaluate_compiler_case(case, candidate, dataset, EvaluationConfig())
    execution = next(item for item in result.component_scores if item.component == "execution")
    assert result.status == "passed"
    assert execution.status == "not_available"


@pytest.mark.asyncio
async def test_guardrail_case_scores_all_fields() -> None:
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")
    case = next(item for item in dataset.guardrail_cases if not item.expected.accepted)
    output = CandidateGuardrailOutput(accepted=False, error_code=case.expected.error_code)
    result = await evaluate_guardrail_case(case, ReplayGuardrail(output))
    assert result.status == "passed"
    assert len(result.component_scores) == 4
