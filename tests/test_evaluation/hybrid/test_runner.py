"""Tests for the end-to-end hybrid runner on the mini dataset."""

from dataclasses import asdict

from eval.evaluator.hybrid.runner import HybridRunRequest, run_hybrid_evaluation
from eval.evaluator.hybrid.smoke import SmokeGuardrailAdapter, smoke_candidates
from eval.evaluator.schemas import EvaluationConfig
from tests.test_evaluation.hybrid.conftest import _executable_dataset


async def test_perfect_smoke_run_passes(mini_dataset) -> None:
    config = EvaluationConfig()
    candidates = await smoke_candidates(mini_dataset, config)
    result = await run_hybrid_evaluation(HybridRunRequest(dataset=mini_dataset, config=config, **asdict(candidates)))
    assert result.status == "PASS"
    assert result.overall_score is not None and result.overall_score >= 90.0
    assert result.coverage == 1.0
    assert result.score_valid is True


async def test_judge_metrics_not_applicable_without_runner(mini_dataset) -> None:
    candidates = await smoke_candidates(mini_dataset, EvaluationConfig())
    result = await run_hybrid_evaluation(
        HybridRunRequest(dataset=mini_dataset, config=EvaluationConfig(), **asdict(candidates))
    )
    judge = [r for r in result.results if r.metric_type == "ai_judge"]
    assert judge and all(r.status == "not_applicable" for r in judge)


async def test_missing_candidates_produce_failures_and_warnings(mini_dataset) -> None:
    result = await run_hybrid_evaluation(HybridRunRequest(dataset=mini_dataset, config=EvaluationConfig()))
    assert result.warnings, "missing responses must be reported"
    assert any(r.status == "failed" for r in result.results)
    assert result.status != "PASS"


async def test_benchmark_requires_deterministic_evidence(mini_dataset) -> None:
    candidates = await smoke_candidates(mini_dataset, EvaluationConfig())
    result = await run_hybrid_evaluation(
        HybridRunRequest(dataset=mini_dataset, config=EvaluationConfig(), run_type="benchmark", **asdict(candidates))
    )
    assert result.score_valid is False
    assert result.status == "INCOMPLETE"


async def test_benchmark_golden_derived_stays_invalid_with_execution(mini_dataset, tmp_path) -> None:
    dataset = _executable_dataset(mini_dataset, tmp_path)
    config = EvaluationConfig()
    candidates = await smoke_candidates(dataset, config)
    result = await run_hybrid_evaluation(
        HybridRunRequest(
            dataset=dataset,
            config=config,
            run_type="benchmark",
            guardrail_adapter=SmokeGuardrailAdapter(config),
            **asdict(candidates),
        )
    )
    assert not next(g for g in result.quality_gates if g.name == "release_evidence").passed
    assert result.score_valid is False
    assert result.status == "INCOMPLETE"


async def test_benchmark_agent_live_stays_valid_with_execution(mini_dataset, tmp_path) -> None:
    dataset = _executable_dataset(mini_dataset, tmp_path)
    config = EvaluationConfig()
    candidates = await smoke_candidates(dataset, config)
    result = await run_hybrid_evaluation(
        HybridRunRequest(
            dataset=dataset,
            config=config,
            run_type="benchmark",
            candidate_source="agent_live",
            guardrail_adapter=SmokeGuardrailAdapter(config),
            **asdict(candidates),
        )
    )
    assert result.score_valid is True
    assert result.status == "PASS"
