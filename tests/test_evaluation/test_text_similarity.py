"""Tests for Vietnamese text normalization and semantic injection."""

import pytest

from eval.evaluator.schemas import EvaluationConfig
from eval.evaluator.text_similarity import compare_business_name, normalize_text


class FakeProvider:
    """Return a deterministic semantic score."""

    async def similarity(self, left: str, right: str) -> float:
        return 0.9


def test_normalize_preserves_vietnamese_accents() -> None:
    assert normalize_text("  Doanh THU, thuần! ") == "doanh thu thuần"


@pytest.mark.asyncio
async def test_compare_returns_separate_scores() -> None:
    result = await compare_business_name(
        "Doanh thu thuần",
        ("doanh thu thuần",),
        EvaluationConfig(),
        FakeProvider(),
    )
    assert result.exact_match == 1.0
    assert result.semantic_similarity == 0.9
    assert result.semantic_status == "available"
    assert result.accepted


@pytest.mark.asyncio
async def test_semantic_is_not_available_without_provider() -> None:
    result = await compare_business_name("a", ("b",), EvaluationConfig())
    assert result.semantic_similarity is None
    assert result.semantic_status == "not_available"
