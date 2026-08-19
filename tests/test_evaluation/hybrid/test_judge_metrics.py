"""Tests for Ragas-style judge metrics with a fake judge LLM."""

import json

from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.judge.base import JudgeRunner
from eval.evaluator.hybrid.judge.cache import MemoryJudgeCache
from eval.evaluator.hybrid.judge.metrics import RUBRIC, build_judge_metrics
from eval.evaluator.hybrid.judge.prompts import RUBRIC_VERSION
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import (
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    EvaluationConfig,
)


class ScriptedLLM:
    """Return one fixed verdict for every call."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.prompts: list[str] = []

    async def invoke(self, system: str, user: str) -> str:
        self.prompts.append(user)
        criteria = [{"name": name, "score": score} for name, score in self.scores.items()]
        return json.dumps({"criteria": criteria, "overall": 0.5, "summary": "ok"})


def _runner(llm: ScriptedLLM) -> JudgeRunner:
    return JudgeRunner(llm, MemoryJudgeCache())


def _enrichment_sample(mini_dataset):
    entities = (
        CandidateEntity(
            entity="orders",
            business_name="Đơn hàng",
            dimensions=(CandidateDimension(name="order_amount", business_name="Giá trị đơn hàng"),),
        ),
    )
    samples = build_samples(mini_dataset, {}, {"disc_001": CandidateEnrichmentOutput(entities=entities)}, {}, {}, {})
    return next(s for s in samples if s.task == "enrichment")


def _expected_score(scores: dict[str, float]) -> float:
    return sum(weight * scores.get(name, 0.0) for name, weight in RUBRIC)


async def test_judge_pass_with_high_scores(mini_dataset) -> None:
    llm = ScriptedLLM(
        {"business_meaning": 1.0, "reference_alignment": 1.0, "unsupported_assumptions": 1.0, "clarity": 1.0}
    )
    metrics = build_judge_metrics(metrics_for_task("enrichment"))
    context = EvaluationContext(EvaluationConfig(), judge_runner=_runner(llm))
    result = await metrics["business_semantic_correctness"].score(_enrichment_sample(mini_dataset), context)
    assert result.status == "passed"
    assert result.score == 1.0
    assert result.provenance.rubric_version == RUBRIC_VERSION
    assert result.metric_type == "ai_judge"


async def test_judge_fail_below_threshold(mini_dataset) -> None:
    llm = ScriptedLLM(
        {"business_meaning": 0.5, "reference_alignment": 0.5, "unsupported_assumptions": 0.5, "clarity": 0.5}
    )
    metrics = build_judge_metrics(metrics_for_task("enrichment"))
    context = EvaluationContext(EvaluationConfig(), judge_runner=_runner(llm))
    result = await metrics["business_semantic_correctness"].score(_enrichment_sample(mini_dataset), context)
    assert result.status == "failed"
    assert result.score == _expected_score(llm.scores)


async def test_judge_unavailable_without_runner(mini_dataset) -> None:
    metrics = build_judge_metrics(metrics_for_task("enrichment"))
    result = await metrics["business_semantic_correctness"].score(
        _enrichment_sample(mini_dataset), EvaluationContext(EvaluationConfig())
    )
    assert result.status == "not_applicable"


async def test_prompt_blinds_judge_to_scores_and_models(mini_dataset) -> None:
    llm = ScriptedLLM(
        {"business_meaning": 1.0, "reference_alignment": 1.0, "unsupported_assumptions": 1.0, "clarity": 1.0}
    )
    metrics = build_judge_metrics(metrics_for_task("enrichment"))
    context = EvaluationContext(EvaluationConfig(), judge_runner=_runner(llm))
    await metrics["business_semantic_correctness"].score(_enrichment_sample(mini_dataset), context)
    prompt = llm.prompts[0]
    assert "Đơn hàng" in prompt  # candidate + reference content present
    assert "gpt" not in prompt.lower() and "score" not in prompt.lower()
