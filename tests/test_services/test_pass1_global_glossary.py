"""Tests for Pass 1: Global Table Glossary generation."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.enrichment_config import EnrichmentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_table(name: str, schema: str | None = None) -> dict:
    return {
        "table_name": name,
        "schema_name": schema,
        "columns": [{"column_name": "id", "data_type": "INTEGER"}],
    }


def _glossary_response(table_names: list[str]) -> str:
    """Build a fake LLM JSON response for the given table names."""
    data = {}
    for t in table_names:
        data[t] = {"business_name": f"Bang {t}", "description": f"Mo ta {t}"}
    return json.dumps(data)


# ---------------------------------------------------------------------------
# table_key
# ---------------------------------------------------------------------------


class TestTableKey:
    def test_key_with_schema(self) -> None:
        from src.services.pass1_global_glossary import table_key

        t = _make_table("orders", schema="public")
        assert table_key(t) == "public.orders"

    def test_key_without_schema(self) -> None:
        from src.services.pass1_global_glossary import table_key

        t = _make_table("users", schema=None)
        assert table_key(t) == "users"


# ---------------------------------------------------------------------------
# build_pass1_prompt
# ---------------------------------------------------------------------------


class TestBuildPass1Prompt:
    def test_prompt_contains_table_names(self) -> None:
        from src.services.pass1_global_glossary import build_pass1_prompt

        prompt = build_pass1_prompt(["orders", "users"], "postgresql")
        assert "orders" in prompt
        assert "users" in prompt

    def test_prompt_requests_json_format(self) -> None:
        from src.services.pass1_global_glossary import build_pass1_prompt

        prompt = build_pass1_prompt(["t1"], "mysql")
        assert "JSON" in prompt or "json" in prompt


# ---------------------------------------------------------------------------
# _fallback_glossary
# ---------------------------------------------------------------------------


class TestFallbackGlossary:
    def test_fallback_has_description_field(self) -> None:
        from src.services.pass1_global_glossary import _fallback_glossary

        tables = [_make_table("orders", schema="public")]
        result = _fallback_glossary(tables)
        assert "public.orders" in result
        assert "description" in result["public.orders"]
        assert "business_name" in result["public.orders"]

    def test_fallback_no_tables_wrapper(self) -> None:
        from src.services.pass1_global_glossary import _fallback_glossary

        tables = [_make_table("users")]
        result = _fallback_glossary(tables)
        assert "tables" not in result

    def test_fallback_business_name_is_title_case(self) -> None:
        from src.services.pass1_global_glossary import _fallback_glossary

        tables = [_make_table("order_items")]
        result = _fallback_glossary(tables)
        name = result["order_items"]["business_name"]
        assert name[0].isupper()


# ---------------------------------------------------------------------------
# merge_glossaries
# ---------------------------------------------------------------------------


class TestMergeGlossaries:
    def test_merge_two_batches(self) -> None:
        from src.services.pass1_global_glossary import merge_glossaries

        b1 = {"public.a": {"business_name": "A", "description": "desc A"}}
        b2 = {"public.b": {"business_name": "B", "description": "desc B"}}
        merged = merge_glossaries([b1, b2])
        assert len(merged) == 2
        assert "public.a" in merged
        assert "public.b" in merged

    def test_merge_overwrites_later(self) -> None:
        from src.services.pass1_global_glossary import merge_glossaries

        b1 = {"x": {"business_name": "old", "description": "old desc"}}
        b2 = {"x": {"business_name": "new", "description": "new desc"}}
        merged = merge_glossaries([b1, b2])
        assert merged["x"]["business_name"] == "new"


# ---------------------------------------------------------------------------
# execute_pass1 — single prompt (≤ threshold)
# ---------------------------------------------------------------------------


class TestExecutePass1SinglePrompt:
    @pytest.mark.asyncio
    async def test_single_prompt_for_small_table_count(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table(f"t{i}", schema="public") for i in range(10)]
        table_names = [f"t{i}" for i in range(10)]
        fake_response = _glossary_response(table_names)

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_response))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert len(result) == 10
        for i in range(10):
            key = f"public.t{i}"
            assert key in result
            assert "business_name" in result[key]
            assert "description" in result[key]

    @pytest.mark.asyncio
    async def test_single_prompt_call_count(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table(f"t{i}") for i in range(5)]
        table_names = [f"t{i}" for i in range(5)]
        fake_response = _glossary_response(table_names)

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_response))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert llm.ainvoke.call_count == 1


# ---------------------------------------------------------------------------
# execute_pass1 — batched (> threshold)
# ---------------------------------------------------------------------------


class TestExecutePass1Batched:
    @pytest.mark.asyncio
    async def test_batched_for_large_table_count(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        n_tables = 80
        tables = [_make_table(f"t{i}", schema="public") for i in range(n_tables)]

        def fake_ainvoke(msg):
            content = msg.content if hasattr(msg, "content") else str(msg)
            # Extract table names mentioned in the prompt
            batch_names = [f"t{i}" for i in range(n_tables) if f"t{i}" in content]
            if not batch_names:
                batch_names = [f"t{i}" for i in range(40)]
            return MagicMock(content=_glossary_response(batch_names))

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)

        config = EnrichmentConfig(pass1_batch_size=40, pass1_single_prompt_threshold=60)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3), config=config)

        assert llm.ainvoke.call_count == 2
        assert len(result) == n_tables


# ---------------------------------------------------------------------------
# execute_pass1 — LLM failure → fallback
# ---------------------------------------------------------------------------


class TestExecutePass1Fallback:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table("orders", schema="public")]

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert "public.orders" in result
        assert "description" in result["public.orders"]
        assert "business_name" in result["public.orders"]

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_fallback(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table("users")]

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="not json"))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert "users" in result
        assert "description" in result["users"]


# ---------------------------------------------------------------------------
# Output schema: flat dict, no "tables" wrapper
# ---------------------------------------------------------------------------


class TestOutputSchema:
    @pytest.mark.asyncio
    async def test_flat_dict_no_tables_wrapper(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table("a"), _make_table("b")]
        fake = json.dumps(
            {
                "a": {"business_name": "A", "description": "desc a"},
                "b": {"business_name": "B", "description": "desc b"},
            }
        )
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert "tables" not in result
        assert isinstance(result, dict)
        for key, val in result.items():
            assert isinstance(key, str)
            assert "business_name" in val
            assert "description" in val


# ---------------------------------------------------------------------------
# Composite key: "schema.table" format
# ---------------------------------------------------------------------------


class TestCompositeKey:
    @pytest.mark.asyncio
    async def test_composite_key_with_schema(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table("orders", schema="public")]
        fake = json.dumps({"orders": {"business_name": "DH", "description": "Don hang"}})
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert "public.orders" in result

    @pytest.mark.asyncio
    async def test_composite_key_without_schema(self) -> None:
        from src.services.pass1_global_glossary import execute_pass1

        tables = [_make_table("users", schema=None)]
        fake = json.dumps({"users": {"business_name": "ND", "description": "Nguoi dung"}})
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake))

        with patch("src.services.pass1_global_glossary.get_llm", return_value=llm):
            result = await execute_pass1(tables, "postgresql", asyncio.Semaphore(3))

        assert "users" in result
        assert "None.users" not in result
