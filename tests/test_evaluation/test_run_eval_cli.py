"""Tests for the run_eval CLI engine flag (no real LLM involved)."""

import json
from pathlib import Path

from eval.dataset.loader import DomainDataset
from eval.run_eval import parse_args, run_hybrid_engine
from tests.test_evaluation.hybrid.conftest import _executable_dataset

EXECUTION_METRICS = ("sql_execution_accuracy", "result_schema_accuracy")


def test_legacy_engine_is_the_default() -> None:
    args = parse_args(["--domain", "ecommerce"])
    assert args.engine == "legacy"


def test_hybrid_engine_flag_parses() -> None:
    args = parse_args(
        [
            "--domain",
            "ecommerce",
            "--engine",
            "hybrid",
            "--run-type",
            "benchmark",
            "--judge",
            "--report-dir",
            "tmp/reports",
        ]
    )
    assert args.engine == "hybrid"
    assert args.run_type == "benchmark"
    assert args.judge is True
    assert args.report_dir == Path("tmp/reports")


async def test_hybrid_engine_wires_execution_lane(mini_dataset, tmp_path, monkeypatch) -> None:
    dataset = _executable_dataset(mini_dataset, tmp_path)

    async def _load(golden_root: Path, domain: str) -> DomainDataset:
        return dataset

    monkeypatch.setattr("eval.run_eval.load_domain_dataset", _load)
    args = parse_args(["--engine", "hybrid", "--golden-root", str(tmp_path), "--report-dir", str(tmp_path / "reports")])
    exit_code = await run_hybrid_engine(args)
    report = json.loads((tmp_path / "reports" / "report.json").read_text(encoding="utf-8"))
    execution = [r for r in report["results"] if r["metric"] in EXECUTION_METRICS]
    assert execution and any(r["status"] != "not_applicable" for r in execution)
    assert report["status"] == "PASS"
    assert exit_code == 0


async def test_hybrid_without_judge_does_not_build_judge(mini_dataset, tmp_path, monkeypatch) -> None:
    dataset = _executable_dataset(mini_dataset, tmp_path)

    async def _load(golden_root: Path, domain: str) -> DomainDataset:
        return dataset

    def _unexpected() -> None:
        raise AssertionError("Judge must not be built without --judge")

    monkeypatch.setattr("eval.run_eval.load_domain_dataset", _load)
    monkeypatch.setattr("eval.run_eval._build_judge_runner", _unexpected)
    args = parse_args(["--engine", "hybrid", "--report-dir", str(tmp_path / "reports")])
    exit_code = await run_hybrid_engine(args)
    assert exit_code == 0
