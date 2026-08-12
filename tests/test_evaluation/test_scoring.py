"""Tests for deterministic set matching and PRF policy."""

from eval.evaluator.schemas import MatchCounts
from eval.evaluator.scoring import macro_average, match_sets, micro_average


def test_empty_sets_score_one() -> None:
    result = match_sets([], [])
    assert result.metrics.model_dump() == {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_partial_match_and_duplicates() -> None:
    result = match_sets(["a", "b"], ["a", "a", "c"])
    assert result.counts == MatchCounts(true_positive=1, false_positive=1, false_negative=1)
    assert result.duplicates == ("a",)
    assert result.metrics.f1 == 0.5


def test_micro_and_macro_aggregation() -> None:
    counts = [MatchCounts(true_positive=1, false_positive=0, false_negative=0)]
    assert micro_average(counts).f1 == 1.0
    assert macro_average([1.0, None, 0.0]) == 0.5
