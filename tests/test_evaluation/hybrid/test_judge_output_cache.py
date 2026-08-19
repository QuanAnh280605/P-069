"""Tests for judge structured output models and the judge cache."""

import pytest
from pydantic import ValidationError

from eval.evaluator.hybrid.judge.cache import (
    FileJudgeCache,
    MemoryJudgeCache,
    content_hash,
    judge_cache_key,
)
from eval.evaluator.hybrid.judge.output import CriterionScore, JudgeVerdict, weighted_score

_RUBRIC = (("business_meaning", 0.4), ("clarity", 0.6))


def _verdict() -> JudgeVerdict:
    return JudgeVerdict(
        criteria=[
            CriterionScore(name="business_meaning", score=0.9, justification="ok"),
            CriterionScore(name="clarity", score=0.5),
        ],
        overall=0.7,
        summary="mostly correct",
    )


def test_verdict_validates_bounds_and_json_round_trip() -> None:
    verdict = _verdict()
    assert weighted_score(verdict, _RUBRIC) == pytest.approx(0.9 * 0.4 + 0.5 * 0.6)
    with pytest.raises(ValidationError):
        CriterionScore(name="x", score=1.5)
    with pytest.raises(ValidationError):
        JudgeVerdict.model_validate_json('{"criteria": [], "overall": 0.5}')
    assert JudgeVerdict.model_validate_json(verdict.model_dump_json()) == verdict


def test_weighted_score_treats_missing_criterion_as_zero() -> None:
    verdict = JudgeVerdict(criteria=[CriterionScore(name="clarity", score=1.0)], overall=1.0)
    assert weighted_score(verdict, _RUBRIC) == pytest.approx(0.6)


def test_cache_key_is_deterministic_and_input_sensitive() -> None:
    key = judge_cache_key("s1", content_hash("abc"), "1.0.0", "v1", "m1")
    assert key == judge_cache_key("s1", content_hash("abc"), "1.0.0", "v1", "m1")
    assert key != judge_cache_key("s1", content_hash("abd"), "1.0.0", "v1", "m1")
    assert key != judge_cache_key("s1", content_hash("abc"), "1.1.0", "v1", "m1")


async def test_memory_cache_round_trip() -> None:
    cache = MemoryJudgeCache()
    assert await cache.get("missing") is None
    await cache.set("k", _verdict())
    assert (await cache.get("k")).overall == pytest.approx(0.7)


async def test_file_cache_round_trip(tmp_path) -> None:
    cache = FileJudgeCache(tmp_path)
    await cache.set("k", _verdict())
    assert (await cache.get("k")).summary == "mostly correct"
    assert list(tmp_path.glob("k.json"))
