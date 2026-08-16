"""Tests for llm_caller — JSON parsing, semaphore safety, retry, and timeout."""

from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from src.services.enrichment_config import EnrichmentConfig

# ---------------------------------------------------------------------------
# parse_llm_json — 4 strategies
# ---------------------------------------------------------------------------


class TestParseLlmJson:
    """Test all 4 JSON extraction strategies."""

    def test_fenced_code_block(self) -> None:
        """Strategy 1: extract from ```json ... ``` fenced block."""
        from src.services.llm_caller import parse_llm_json

        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_fenced_code_block_no_lang(self) -> None:
        """Fenced block without json language tag."""
        from src.services.llm_caller import parse_llm_json

        text = '```\n{"key": "value"}\n```'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_direct_json_loads(self) -> None:
        """Strategy 2: direct json.loads on entire text."""
        from src.services.llm_caller import parse_llm_json

        text = '{"tables": ["a", "b"]}'
        result = parse_llm_json(text)
        assert result == {"tables": ["a", "b"]}

    def test_raw_decode_from_brace(self) -> None:
        """Strategy 3: raw_decode starting from first { or [."""
        from src.services.llm_caller import parse_llm_json

        text = 'Sure! Here is the JSON: {"matched": 3} hope that helps'
        result = parse_llm_json(text)
        assert result == {"matched": 3}

    def test_raw_decode_array(self) -> None:
        """Strategy 3 with array: raw_decode from first [."""
        from src.services.llm_caller import parse_llm_json

        text = "Result: [1, 2, 3] done"
        result = parse_llm_json(text)
        assert result == [1, 2, 3]

    def test_slice_fallback_object_array(self) -> None:
        """Strategy 4: slice from first { to last } or [ to last ]."""
        from src.services.llm_caller import parse_llm_json

        text = "Here is [1, 2, 3] and more [4, 5] stuff"
        result = parse_llm_json(text)
        # raw_decode (strategy 3) catches this first
        assert result == [1, 2, 3]

    def test_no_json_raises_value_error(self) -> None:
        """Raise ValueError when no JSON found."""
        from src.services.llm_caller import parse_llm_json

        with pytest.raises(ValueError, match="No valid JSON"):
            parse_llm_json("no json here at all")

    def test_array_direct(self) -> None:
        """Direct json.loads for array."""
        from src.services.llm_caller import parse_llm_json

        result = parse_llm_json("[1, 2, 3]")
        assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# execute_llm_request — semaphore + timeout
# ---------------------------------------------------------------------------


class TestExecuteLlmRequest:
    """Test semaphore wrapping and timeout behavior."""

    @pytest.mark.asyncio
    async def test_returns_response_content(self) -> None:
        """Normal call returns LLM response content string."""
        from src.services.llm_caller import execute_llm_request

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(content='{"ok": true}')
        sem = asyncio.Semaphore(1)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            result = await execute_llm_request("test prompt", sem)

        assert result == '{"ok": true}'
        mock_llm.ainvoke.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_semaphore_released_after_response(self) -> None:
        """Semaphore is released after successful response."""
        from src.services.llm_caller import execute_llm_request

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(content="ok")
        sem = asyncio.Semaphore(1)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            await execute_llm_request("prompt", sem)

        assert sem.locked() is False

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        """Timeout triggers asyncio.TimeoutError when LLM hangs."""
        from src.services.llm_caller import execute_llm_request

        async def slow_invoke(prompt: str) -> None:
            await asyncio.sleep(60)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = slow_invoke
        sem = asyncio.Semaphore(1)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            with pytest.raises(asyncio.TimeoutError):
                await execute_llm_request("prompt", sem, timeout_sec=0.1)

    @pytest.mark.asyncio
    async def test_semaphore_released_after_timeout(self) -> None:
        """Semaphore released even when timeout occurs."""
        from src.services.llm_caller import execute_llm_request

        async def slow_invoke(prompt: str) -> None:
            await asyncio.sleep(60)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = slow_invoke
        sem = asyncio.Semaphore(1)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            with pytest.raises(asyncio.TimeoutError):
                await execute_llm_request("prompt", sem, timeout_sec=0.1)

        assert sem.locked() is False


# ---------------------------------------------------------------------------
# enrich_cluster_with_retry — retry + fallback
# ---------------------------------------------------------------------------


def _make_prompt_builder(response_text: str):
    """Create a prompt builder that also serves as LLM response selector."""

    def builder(cluster, global_glossary, dialect, is_retry=False):
        return response_text

    return builder


class TestEnrichClusterWithRetry:
    """Test retry loop, backoff, and fallback behavior."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self) -> None:
        """First attempt succeeds → return merged result."""
        from src.services.llm_caller import enrich_cluster_with_retry

        good_response = json.dumps({"matched_tables": ["t1", "t2"], "metrics": []})
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(content=good_response)
        sem = asyncio.Semaphore(3)
        config = EnrichmentConfig(llm_match_threshold=0.7)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            result = await enrich_cluster_with_retry(
                _make_prompt_builder(good_response),
                [{"table_name": "t1"}, {"table_name": "t2"}],
                {},
                "postgresql",
                sem,
                config,
            )

        assert result["matched_tables"] == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        """Attempt 1 fails, attempt 2 succeeds → return merged result."""
        from src.services.llm_caller import enrich_cluster_with_retry

        good_response = json.dumps({"matched_tables": ["t1"], "metrics": []})
        call_count = 0

        async def selective_invoke(prompt: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("rate limit 429")
            return AsyncMock(content=good_response)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = selective_invoke
        sem = asyncio.Semaphore(3)
        config = EnrichmentConfig(llm_match_threshold=0.7, retry_backoff_base_sec=0.01)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            result = await enrich_cluster_with_retry(
                _make_prompt_builder(good_response),
                [{"table_name": "t1"}],
                {},
                "postgresql",
                sem,
                config,
            )

        assert result["matched_tables"] == ["t1"]
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_returns_fallback(self, caplog) -> None:
        """All attempts fail → return fallback dict + warning log."""
        from src.services.llm_caller import enrich_cluster_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("server error 500")
        sem = asyncio.Semaphore(3)
        config = EnrichmentConfig(llm_match_threshold=0.7, retry_max_attempts=2, retry_backoff_base_sec=0.01)
        cluster = [{"table_name": "t1"}, {"table_name": "t2"}]

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            with caplog.at_level(logging.WARNING):
                result = await enrich_cluster_with_retry(
                    _make_prompt_builder("bad"),
                    cluster,
                    {},
                    "postgresql",
                    sem,
                    config,
                )

        assert "fallback" in result.get("source", "") or result.get("source") == "fallback"
        assert mock_llm.ainvoke.call_count == config.retry_max_attempts + 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_fallback_tables(self) -> None:
        """Fallback dict contains all cluster tables."""
        from src.services.llm_caller import enrich_cluster_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("timeout")
        sem = asyncio.Semaphore(3)
        config = EnrichmentConfig(retry_max_attempts=2, retry_backoff_base_sec=0.01)
        cluster = [{"table_name": "a"}, {"table_name": "b"}]

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            result = await enrich_cluster_with_retry(
                _make_prompt_builder("bad"),
                cluster,
                {},
                "postgresql",
                sem,
                config,
            )

        assert "tables" in result
        assert set(result["tables"]) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_semaphore_not_held_during_backoff(self) -> None:
        """Backoff sleep happens outside the semaphore."""
        from src.services.llm_caller import enrich_cluster_with_retry

        sem = asyncio.Semaphore(1)
        acquire_count = 0
        original_acquire = sem.acquire

        async def counting_acquire():
            nonlocal acquire_count
            acquire_count += 1
            return await original_acquire()

        good_response = json.dumps({"matched_tables": ["t1"], "metrics": []})
        call_count = 0

        async def selective_invoke(prompt: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429")
            return AsyncMock(content=good_response)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = selective_invoke
        config = EnrichmentConfig(llm_match_threshold=0.7, retry_backoff_base_sec=0.01)

        with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
            sem.acquire = counting_acquire
            result = await enrich_cluster_with_retry(
                _make_prompt_builder(good_response),
                [{"table_name": "t1"}],
                {},
                "postgresql",
                sem,
                config,
            )

        assert result["matched_tables"] == ["t1"]
        # Semaphore acquired once per attempt
        assert acquire_count == 2
