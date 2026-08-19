"""Minimal end-to-end runner that wires the evaluation public API.

Skeleton/demo: loads a Golden Dataset domain and runs ``evaluate_domain_suite``
with placeholder (empty) candidate outputs so the framework executes end-to-end.
Replace ``_placeholder_candidates`` with real candidate outputs produced by the
agent (Stage 2-4) to score an actual run.

Run from the repository root:

    python -m eval.run_eval --domain ecommerce
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from eval.dataset.loader import load_domain_dataset
from eval.evaluator import (
    DomainCandidateOutputs,
    DomainEvaluationResult,
    EvaluationDependencies,
    evaluate_domain_suite,
)
from eval.evaluator.schemas import EvaluationConfig

if TYPE_CHECKING:
    from eval.evaluator.hybrid.judge.base import JudgeRunner

GOLDEN_ROOT = Path("eval/golden_dataset")
SUITES = ("enrichment", "metrics", "compiler", "guardrails")


async def run_evaluation(golden_root: Path, domain: str) -> DomainEvaluationResult:
    """Load one domain dataset and evaluate its candidate outputs."""
    dataset = await load_domain_dataset(golden_root, domain)
    deps = EvaluationDependencies(config=EvaluationConfig())
    return await evaluate_domain_suite(dataset, _placeholder_candidates(), deps)


def _placeholder_candidates() -> DomainCandidateOutputs:
    """Return empty candidate outputs (replace with real agent output)."""
    return DomainCandidateOutputs(enrichment={}, metrics={}, compiler={})


def _print_summary(result: DomainEvaluationResult) -> None:
    """Print micro precision/recall/F1 for each evaluated suite."""
    for name in SUITES:
        micro = getattr(result, name).micro
        if micro is None:
            print(f"{name:<12}: (chưa có case nào được chấm)")
            continue
        print(f"{name:<12}: F1={micro.f1:.3f}  P={micro.precision:.3f}  R={micro.recall:.3f}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments; the legacy engine stays the default."""
    parser = argparse.ArgumentParser(description="Run the evaluation framework on one domain.")
    parser.add_argument("--golden-root", type=Path, default=GOLDEN_ROOT, help="Golden Dataset root directory.")
    parser.add_argument("--domain", default="ecommerce", help="Domain identifier to evaluate.")
    parser.add_argument("--engine", choices=("legacy", "hybrid"), default="legacy")
    parser.add_argument("--run-type", choices=("smoke", "benchmark", "release"), default="smoke")
    parser.add_argument(
        "--judge",
        action="store_true",
        help="enable the isolated AI Judge lane (requires JUDGE_* configuration)",
    )
    parser.add_argument("--report-dir", type=Path, default=Path("eval/reports/hybrid"))
    return parser.parse_args(argv)


def _build_judge_runner() -> JudgeRunner:
    """Wire the isolated get_llm(role='judge') lane."""
    from eval.evaluator.hybrid.judge.base import JudgeRunner, LangChainJudgeLLM
    from eval.evaluator.hybrid.judge.cache import MemoryJudgeCache

    return JudgeRunner(llm=LangChainJudgeLLM(), cache=MemoryJudgeCache())


async def run_hybrid_engine(args: argparse.Namespace) -> int:
    """Execute a golden-derived hybrid run and write the three reports."""
    from eval.evaluator.hybrid import HybridRunRequest, run_hybrid_evaluation, smoke_candidates
    from eval.evaluator.hybrid.reporting import write_csv_report, write_json_report, write_markdown_report
    from eval.evaluator.hybrid.smoke import SmokeGuardrailAdapter

    dataset = await load_domain_dataset(args.golden_root, args.domain)
    config = EvaluationConfig()
    candidates = await smoke_candidates(dataset, config)
    result = await run_hybrid_evaluation(
        HybridRunRequest(
            dataset=dataset,
            config=config,
            guardrail_adapter=SmokeGuardrailAdapter(config),
            judge_runner=_build_judge_runner() if args.judge else None,
            run_id=f"hybrid-{args.domain}",
            run_type=args.run_type,
            **asdict(candidates),
        )
    )
    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(result, args.report_dir / "report.json")
    write_csv_report(result, args.report_dir / "report.csv")
    write_markdown_report(result, args.report_dir / "report.md")
    print(
        f"hybrid run {result.run_id}: status={result.status} "
        f"score={result.overall_score} coverage={result.coverage:.0%}"
    )
    return 0 if result.status in {"PASS", "WARN"} else 1


def main() -> int:
    """CLI entry point: parse args, run evaluation, and print the summary."""
    args = parse_args()
    if args.engine == "hybrid":
        return asyncio.run(run_hybrid_engine(args))
    result = asyncio.run(run_evaluation(args.golden_root, args.domain))
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
