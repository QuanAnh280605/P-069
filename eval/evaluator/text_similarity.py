"""Vietnamese-aware deterministic text similarity helpers."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Protocol

from eval.evaluator.schemas import EvaluationConfig, TextSimilarityScore

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


class TextSimilarityProvider(Protocol):
    """Provide injectable asynchronous semantic text similarity."""

    async def similarity(self, left: str, right: str) -> float:
        """Return semantic similarity in the inclusive zero-to-one range."""
        ...


def normalize_text(value: str) -> str:
    """Normalize Unicode, casing, punctuation and whitespace without removing accents."""
    normalized = unicodedata.normalize("NFC", value).casefold()
    normalized = _PUNCTUATION.sub(" ", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


def accent_insensitive(value: str) -> str:
    """Create an accent-insensitive diagnostic form without changing exact matching."""
    decomposed = unicodedata.normalize("NFD", normalize_text(value))
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def fuzzy_similarity(left: str, right: str) -> float:
    """Return deterministic character similarity with accent-insensitive diagnostics."""
    normal = SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()
    accentless = SequenceMatcher(None, accent_insensitive(left), accent_insensitive(right)).ratio()
    return max(normal, accentless)


async def compare_business_name(
    actual: str,
    accepted_names: list[str] | tuple[str, ...],
    config: EvaluationConfig,
    provider: TextSimilarityProvider | None = None,
) -> TextSimilarityScore:
    """Compare one candidate name against all accepted labels."""
    labels = tuple(accepted_names)
    exact = float(any(normalize_text(actual) == normalize_text(label) for label in labels))
    fuzzy = max((fuzzy_similarity(actual, label) for label in labels), default=0.0)
    semantic = await _best_semantic(actual, labels, provider)
    accepted = bool(exact or fuzzy >= config.fuzzy_threshold)
    if semantic is not None:
        accepted = accepted or semantic >= config.semantic_threshold
    return TextSimilarityScore(
        exact_match=exact,
        fuzzy_similarity=fuzzy,
        semantic_similarity=semantic,
        semantic_status="available" if semantic is not None else "not_available",
        accepted=accepted,
    )


async def _best_semantic(
    actual: str,
    labels: tuple[str, ...],
    provider: TextSimilarityProvider | None,
) -> float | None:
    if provider is None:
        return None
    scores = [await provider.similarity(actual, label) for label in labels]
    if any(score < 0.0 or score > 1.0 for score in scores):
        raise ValueError("semantic provider returned a score outside [0, 1]")
    return max(scores, default=0.0)
