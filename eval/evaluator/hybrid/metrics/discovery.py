"""Deterministic discovery metrics over raw schema fixtures (spec §7.1)."""

from __future__ import annotations

from typing import Literal

from eval.evaluator.discovery_eval import CandidateDiscoveryOutput
from eval.evaluator.hybrid.catalog import MetricSpec
from eval.evaluator.hybrid.contracts import MetricResult
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.base import (
    CandidateFailure,
    DeterministicMetric,
    reference_as,
    response_as,
    set_match_result,
)
from eval.evaluator.hybrid.samples import DiscoveryReference, EvaluationSample
from eval.evaluator.schemas import MatchCounts
from eval.evaluator.scoring import SetMatchResult, match_sets, precision_recall_f1

_Facet = Literal["tables", "columns", "primary_keys", "relationships"]
_Field = Literal["precision", "recall", "f1"]

_FACETS: dict[str, tuple[_Facet, _Field]] = {
    "table_precision": ("tables", "precision"),
    "table_recall": ("tables", "recall"),
    "table_f1": ("tables", "f1"),
    "column_f1": ("columns", "f1"),
    "primary_key_accuracy": ("primary_keys", "f1"),
    "relationship_f1": ("relationships", "f1"),
}


def build_discovery_metrics(specs: tuple[MetricSpec, ...]) -> dict[str, DeterministicMetric]:
    """Instantiate one set-matching metric per discovery catalog entry."""
    return {spec.name: DiscoverySetMetric(spec, *_FACETS[spec.name]) for spec in specs if spec.name in _FACETS}


class DiscoverySetMetric(DeterministicMetric):
    """Score one structural facet of a discovery raw schema."""

    def __init__(self, spec: MetricSpec, facet: _Facet, field: _Field) -> None:
        super().__init__(spec)
        self.facet = facet
        self.field = field

    async def _score(self, sample: EvaluationSample, context: EvaluationContext) -> MetricResult:
        expected, actual = _raw_pair(sample)
        if self.facet in {"tables", "relationships"}:
            match = match_sets(_facet_set(expected, self.facet), _facet_set(actual, self.facet))
            return set_match_result(self.spec, sample.sample_id, match, self.field)
        counts = _micro_counts(expected, actual, self.facet)
        wrapped = SetMatchResult(counts, precision_recall_f1(counts), ())
        return set_match_result(self.spec, sample.sample_id, wrapped, self.field)


def _raw_pair(sample: EvaluationSample) -> tuple[dict, dict]:
    reference = reference_as(sample, DiscoveryReference)
    response = response_as(sample, CandidateDiscoveryOutput)
    if response.raw_schema is None:
        raise CandidateFailure(response.error_code or "empty raw schema")
    return dict(reference.raw_schema), response.raw_schema


def _table_map(raw: dict) -> dict[str, dict]:
    return {table["table_name"]: table for table in raw.get("tables", [])}


def _facet_set(raw: dict, facet: _Facet) -> set:
    if facet == "tables":
        return set(_table_map(raw))
    return {
        (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])
        for rel in raw.get("relationships", [])
    }


def _selector(facet: _Facet) -> object:
    if facet == "columns":
        return lambda table: {column["column_name"] for column in table.get("columns", [])}
    return lambda table: set(table.get("primary_keys", []))


def _micro_counts(expected: dict, actual: dict, facet: _Facet) -> MatchCounts:
    exp_tables, act_tables = _table_map(expected), _table_map(actual)
    select = _selector(facet)
    tp = fp = fn = 0
    for name, exp_table in exp_tables.items():
        match = match_sets(select(exp_table), select(act_tables.get(name, {})))
        tp += match.counts.true_positive
        fp += match.counts.false_positive
        fn += match.counts.false_negative
    return MatchCounts(true_positive=tp, false_positive=fp, false_negative=fn)
