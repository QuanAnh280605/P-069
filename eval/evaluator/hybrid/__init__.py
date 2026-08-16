"""Hybrid Ragas-style evaluation engine (spec §4.1 cycle-1 scope)."""

from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.run_result import HybridRunResult
from eval.evaluator.hybrid.runner import HybridRunRequest, run_hybrid_evaluation
from eval.evaluator.hybrid.samples import EvaluationSample, build_samples
from eval.evaluator.hybrid.smoke import smoke_candidates

__all__ = [
    "EvaluationSample",
    "HybridRunRequest",
    "HybridRunResult",
    "MetricResult",
    "build_samples",
    "run_hybrid_evaluation",
    "smoke_candidates",
]
