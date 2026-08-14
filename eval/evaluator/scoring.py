"""Deterministic set matching and score aggregation primitives."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

from eval.evaluator.schemas import MatchCounts, PrecisionRecallF1


@dataclass(frozen=True)
class SetMatchResult:
    """Contain counts, metrics and duplicate candidate values."""

    counts: MatchCounts
    metrics: PrecisionRecallF1
    duplicates: tuple[Hashable, ...]


def precision_recall_f1(counts: MatchCounts) -> PrecisionRecallF1:
    """Calculate PRF with the documented empty-set zero-division policy."""
    tp = counts.true_positive
    predicted = tp + counts.false_positive
    expected = tp + counts.false_negative
    precision = tp / predicted if predicted else 1.0
    recall = tp / expected if expected else 1.0
    denominator = precision + recall
    f1 = 2 * precision * recall / denominator if denominator else 0.0
    return PrecisionRecallF1(precision=precision, recall=recall, f1=f1)


def match_sets(expected: Iterable[Hashable], actual: Iterable[Hashable]) -> SetMatchResult:
    """Match values as sets while reporting duplicate candidate values."""
    expected_set = set(expected)
    actual_values = tuple(actual)
    actual_set = set(actual_values)
    counts = MatchCounts(
        true_positive=len(expected_set & actual_set),
        false_positive=len(actual_set - expected_set),
        false_negative=len(expected_set - actual_set),
    )
    duplicates = _duplicates(actual_values)
    return SetMatchResult(counts, precision_recall_f1(counts), duplicates)


def micro_average(counts: Iterable[MatchCounts]) -> PrecisionRecallF1:
    """Calculate a micro average by summing all match counts."""
    values = tuple(counts)
    total = MatchCounts(
        true_positive=sum(item.true_positive for item in values),
        false_positive=sum(item.false_positive for item in values),
        false_negative=sum(item.false_negative for item in values),
    )
    return precision_recall_f1(total)


def macro_average(scores: Iterable[float | None]) -> float | None:
    """Average only available component scores."""
    available = tuple(score for score in scores if score is not None)
    return sum(available) / len(available) if available else None


def _duplicates(values: Sequence[Hashable]) -> tuple[Hashable, ...]:
    seen: set[Hashable] = set()
    duplicates: set[Hashable] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates, key=repr))
