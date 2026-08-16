"""Tests for Pass 2: Parallel Cluster Enrichment."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from src.services.enrichment_config import EnrichmentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_table(
    name: str,
    num_cols: int = 3,
    fks: list[dict] | None = None,
    schema: str | None = None,
) -> dict:
    columns = [
        {
            "column_name": f"col_{i}",
            "data_type": "INTEGER",
            "is_nullable": True,
            "is_primary_key": i == 0,
            "is_foreign_key": False,
            "default_value": None,
            "sample_values": None,
            "references": None,
        }
        for i in range(num_cols)
    ]
    return {
        "table_name": name,
        "schema_name": schema,
        "columns": columns,
        "foreign_keys": fks or [],
    }


def _make_wide_table(name: str, num_cols: int, schema: str | None = None) -> dict:
    columns = [
        {
            "column_name": f"col_{i}",
            "data_type": "VARCHAR",
            "is_nullable": True,
            "is_primary_key": i == 0,
            "is_foreign_key": False,
            "default_value": None,
            "sample_values": [f"val_{i}"],
            "references": None,
        }
        for i in range(num_cols)
    ]
    return {
        "table_name": name,
        "schema_name": schema,
        "columns": columns,
        "foreign_keys": [],
    }


def _llm_response_for_tables(table_names: list[str], columns_per_table: int = 3) -> dict:
    """Build a fake LLM enrichment response for the given table names."""
    matched = []
    tables_data = {}
    for tname in table_names:
        matched.append(tname)
        cols = [
            {
                "column_name": f"col_{i}",
                "business_name": f"Trường {i}",
                "description": f"Mô tả cột {i}",
            }
            for i in range(columns_per_table)
        ]
        tables_data[tname] = {
            "business_name": f"Bang {tname}",
            "description": f"Mo ta {tname}",
            "columns": cols,
        }
    return {"matched_tables": matched, "tables": tables_data}


def _build_global_glossary(table_names: list[str]) -> dict:
    """Build a fake global_glossary as returned by Pass 1."""
    result = {}
    for tname in table_names:
        result[tname] = {
            "business_name": f"Global {tname}",
            "description": f"Global mo ta {tname}",
        }
    return result


# ---------------------------------------------------------------------------
# table_key
# ---------------------------------------------------------------------------


class TestTableKey:
    def test_key_with_schema(self) -> None:
        from src.services.pass2_cluster_enrichment import table_key

        t = _make_table("orders", schema="public")
        assert table_key(t) == "public.orders"

    def test_key_without_schema(self) -> None:
        from src.services.pass2_cluster_enrichment import table_key

        t = _make_table("users")
        assert table_key(t) == "users"


# ---------------------------------------------------------------------------
# build_cluster_prompt
# ---------------------------------------------------------------------------


class TestBuildClusterPrompt:
    def test_prompt_contains_table_names(self) -> None:
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders"), _make_table("items")]
        prompt = build_cluster_prompt(cluster, {}, "postgresql")
        assert "orders" in prompt
        assert "items" in prompt

    def test_prompt_contains_column_info(self) -> None:
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders", num_cols=2)]
        prompt = build_cluster_prompt(cluster, {}, "postgresql")
        assert "col_0" in prompt
        assert "col_1" in prompt

    def test_prompt_contains_sample_values(self) -> None:
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        table = _make_table("orders", num_cols=1)
        table["columns"][0]["sample_values"] = ["ORD-001", "ORD-002"]
        prompt = build_cluster_prompt([table], {}, "postgresql")
        assert "ORD-001" in prompt

    def test_prompt_contains_glossary_context(self) -> None:
        """Verify prompt includes glossary header for cluster tables and hub FKs."""
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders"), _make_table("items")]
        glossary = _build_global_glossary(["orders", "items"])
        prompt = build_cluster_prompt(cluster, glossary, "postgresql")
        assert "Global orders" in prompt
        assert "Global mo ta orders" in prompt

    def test_prompt_contains_hub_glossary_from_fk_targets(self) -> None:
        """When cluster tables FK to hub tables, hub glossary context is included."""
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        fks = [
            {
                "constrained_columns": ["customer_id"],
                "referred_table": "customer",
                "referred_columns": ["id"],
            }
        ]
        cluster = [_make_table("orders", fks=fks)]
        glossary = _build_global_glossary(["orders", "customer"])
        prompt = build_cluster_prompt(cluster, glossary, "postgresql")
        assert "customer" in prompt

    def test_prompt_is_vietnamese(self) -> None:
        """Prompt should contain Vietnamese text."""
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders")]
        prompt = build_cluster_prompt(cluster, {}, "postgresql")
        # Vietnamese keywords
        viet_markers = ["bảng", "cột", "khóa", "mô tả", "JSON"]
        assert any(m.lower() in prompt.lower() for m in viet_markers)

    def test_retry_prompt_has_format_hint(self) -> None:
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders")]
        normal = build_cluster_prompt(cluster, {}, "postgresql", is_retry=False)
        retry = build_cluster_prompt(cluster, {}, "postgresql", is_retry=True)
        assert len(retry) > len(normal)

    def test_prompt_contains_fk_info(self) -> None:
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        fks = [
            {
                "constrained_columns": ["customer_id"],
                "referred_table": "customer",
                "referred_columns": ["id"],
            }
        ]
        cluster = [_make_table("orders", fks=fks)]
        prompt = build_cluster_prompt(cluster, {}, "postgresql")
        assert "customer_id" in prompt
        assert "customer" in prompt

    def test_prompt_only_includes_cluster_tables_from_glossary(self) -> None:
        """Glossary context should only show tables in cluster + hub FK targets, not all 100+ tables."""
        from src.services.pass2_cluster_enrichment import build_cluster_prompt

        cluster = [_make_table("orders"), _make_table("items")]
        # glossary has many tables, but only orders and items should appear
        all_tables = ["orders", "items", "users", "products", "logs", "audit"]
        glossary = _build_global_glossary(all_tables)
        prompt = build_cluster_prompt(cluster, glossary, "postgresql")
        assert "Global orders" in prompt
        assert "Global items" in prompt
        # These should NOT appear in glossary context section
        assert "Global users" not in prompt
        assert "Global products" not in prompt


# ---------------------------------------------------------------------------
# _merge_cluster_result
# ---------------------------------------------------------------------------


class TestMergeClusterResult:
    def test_merge_full_llm_response(self) -> None:
        """All tables in LLM response → use LLM data."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        cluster = [_make_table("orders"), _make_table("items")]
        parsed = _llm_response_for_tables(["orders", "items"])
        result = _merge_cluster_result(cluster, parsed, {})
        assert "orders" in result
        assert "items" in result
        assert result["orders"]["business_name"] == "Bang orders"

    def test_merge_partial_response_uses_glossary_fallback(self) -> None:
        """Table missing from LLM → fallback to global_glossary."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        cluster = [_make_table("orders"), _make_table("items")]
        # LLM only returns orders, missing items
        parsed = _llm_response_for_tables(["orders"])
        glossary = _build_global_glossary(["orders", "items"])
        result = _merge_cluster_result(cluster, parsed, glossary)
        assert "orders" in result
        assert "items" in result
        assert result["items"]["business_name"] == "Global items"
        assert result["items"]["description"] == "Global mo ta items"

    def test_merge_fallback_title_case_when_glossary_missing(self) -> None:
        """Table missing from LLM AND glossary → title-case fallback."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        cluster = [_make_table("order_items")]
        parsed = {"matched_tables": [], "tables": {}}
        result = _merge_cluster_result(cluster, parsed, {})
        assert "order_items" in result
        assert result["order_items"]["business_name"][0].isupper()

    def test_merge_column_matching_case_insensitive(self) -> None:
        """LLM returns ORDER_ID vs metadata order_id → match succeeds."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        table = _make_table("orders", num_cols=1)
        cluster = [table]
        parsed = {
            "matched_tables": ["orders"],
            "tables": {
                "orders": {
                    "business_name": "Don hang",
                    "description": "Mo ta",
                    "columns": [{"column_name": "COL_0", "business_name": "Ma", "description": "Desc"}],
                }
            },
        }
        result = _merge_cluster_result(cluster, parsed, {})
        assert result["orders"]["columns"][0]["column_name"] == "col_0"
        assert result["orders"]["columns"][0]["business_name"] == "Ma"

    def test_merge_output_uses_composite_key(self) -> None:
        """Output keys should be composite keys (schema.table)."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        cluster = [_make_table("orders", schema="public")]
        parsed = _llm_response_for_tables(["orders"])
        result = _merge_cluster_result(cluster, parsed, {})
        assert "public.orders" in result
        assert "orders" not in result

    def test_merge_ensures_business_name_and_description(self) -> None:
        """Merged result always has business_name and description."""
        from src.services.pass2_cluster_enrichment import _merge_cluster_result

        cluster = [_make_table("orders")]
        # LLM response without business_name
        parsed = {
            "matched_tables": ["orders"],
            "tables": {"orders": {"columns": []}},
        }
        result = _merge_cluster_result(cluster, parsed, {})
        assert "business_name" in result["orders"]
        assert "description" in result["orders"]


# ---------------------------------------------------------------------------
# enrich_clusters_parallel
# ---------------------------------------------------------------------------


class TestEnrichClustersParallel:
    @pytest.mark.asyncio
    async def test_parallel_execution_with_semaphore(self) -> None:
        """4 clusters with semaphore=3 → max 3 concurrent LLM calls."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        clusters = [[_make_table(f"t{i}_a"), _make_table(f"t{i}_b")] for i in range(4)]
        glossary = _build_global_glossary([f"t{i}_{s}" for i in range(4) for s in ("a", "b")])

        max_concurrent = 0
        current_concurrent = 0

        async def mock_enrich(prompt_builder, cluster_data, glossary_data, dialect, sem, config):
            nonlocal max_concurrent, current_concurrent
            async with sem:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
                await asyncio.sleep(0.05)
                current_concurrent -= 1
            return _llm_response_for_tables([t["table_name"] for t in cluster_data])

        config = EnrichmentConfig(max_concurrency=3, llm_match_threshold=0.0, retry_backoff_base_sec=0.01)

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", side_effect=mock_enrich):
            result = await enrich_clusters_parallel(clusters, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert max_concurrent <= 3
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_flat_dict_with_composite_keys(self) -> None:
        """Result is flat dict keyed by composite key."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        cluster = [[_make_table("orders", schema="public"), _make_table("items", schema="public")]]
        glossary = _build_global_glossary(["orders", "items"])

        resp = _llm_response_for_tables(["orders", "items"])

        config = EnrichmentConfig(llm_match_threshold=0.0, retry_backoff_base_sec=0.01)

        async def mock_execute(prompt, sem, timeout_sec=30.0):
            return json.dumps(resp)

        with patch("src.services.pass2_cluster_enrichment.execute_llm_request", side_effect=mock_execute):
            result = await enrich_clusters_parallel(cluster, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert "public.orders" in result
        assert "public.items" in result
        assert "business_name" in result["public.orders"]
        assert "columns" in result["public.orders"]

    @pytest.mark.asyncio
    async def test_semaphore_reuse_from_caller(self) -> None:
        """Must receive sem from caller, not create its own."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        cluster = [[_make_table("t1")]]
        glossary = _build_global_glossary(["t1"])

        sem_value_at_call = None

        async def mock_enrich(prompt_builder, cluster, glossary, dialect, sem, config):
            nonlocal sem_value_at_call
            sem_value_at_call = id(sem)
            return _llm_response_for_tables([t["table_name"] for t in cluster])

        caller_sem = asyncio.Semaphore(5)

        config = EnrichmentConfig(llm_match_threshold=0.0, retry_backoff_base_sec=0.01)

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", side_effect=mock_enrich):
            await enrich_clusters_parallel(cluster, glossary, "postgresql", caller_sem, config)

        assert sem_value_at_call == id(caller_sem)

    @pytest.mark.asyncio
    async def test_partial_response_merge_integration(self) -> None:
        """LLM returns 3/4 tables → 4th table auto-fallback from global_glossary."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        tables = [_make_table(f"t{i}") for i in range(4)]
        cluster = [tables]
        glossary = _build_global_glossary([f"t{i}" for i in range(4)])

        # LLM returns only t0, t1, t2 — missing t3
        partial_resp = _llm_response_for_tables(["t0", "t1", "t2"])

        config = EnrichmentConfig(llm_match_threshold=0.0, retry_backoff_base_sec=0.01)

        async def mock_enrich(prompt_builder, cluster, glossary, dialect, sem, config):
            return partial_resp

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", side_effect=mock_enrich):
            result = await enrich_clusters_parallel(cluster, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert "t0" in result
        assert "t1" in result
        assert "t2" in result
        assert "t3" in result
        assert result["t3"]["business_name"] == "Global t3"


# ---------------------------------------------------------------------------
# _handle_ultra_wide_table
# ---------------------------------------------------------------------------


class TestHandleUltraWideTable:
    @pytest.mark.asyncio
    async def test_51_cols_split_into_2_chunks(self) -> None:
        """51 cols > 40 threshold, chunk_size=30 → 2 sub-prompts."""
        from src.services.pass2_cluster_enrichment import _handle_ultra_wide_table

        table = _make_wide_table("wide_table", 51)
        glossary = _build_global_glossary(["wide_table"])

        call_count = 0
        columns_seen = []

        async def mock_execute(prompt, sem, timeout_sec=30.0):
            nonlocal call_count
            call_count += 1
            # Count how many col_ columns appear in prompt
            import re

            cols_in_prompt = re.findall(r"col_\d+", prompt)
            columns_seen.append(len(set(cols_in_prompt)))
            # Return enrichment for columns mentioned
            cols_data = [
                {"column_name": c, "business_name": f"Field {c}", "description": f"Desc {c}"}
                for c in set(cols_in_prompt)
            ]
            return json.dumps(
                {
                    "matched_tables": ["wide_table"],
                    "tables": {
                        "wide_table": {
                            "business_name": "Wide Table",
                            "description": "A wide table",
                            "columns": cols_data,
                        }
                    },
                }
            )

        config = EnrichmentConfig(
            ultra_wide_threshold=40,
            ultra_wide_chunk_size=30,
            llm_match_threshold=0.0,
            retry_backoff_base_sec=0.01,
        )

        with patch("src.services.pass2_cluster_enrichment.execute_llm_request", side_effect=mock_execute):
            result = await _handle_ultra_wide_table(table, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert call_count == 2
        assert result["business_name"] == "Wide Table"
        assert len(result["columns"]) == 51

    @pytest.mark.asyncio
    async def test_120_cols_split_into_4_chunks(self) -> None:
        """120 cols, chunk_size=30 → 4 sub-prompts."""
        from src.services.pass2_cluster_enrichment import _handle_ultra_wide_table

        table = _make_wide_table("huge_table", 120)
        glossary = _build_global_glossary(["huge_table"])

        call_count = 0

        async def mock_execute(prompt, sem, timeout_sec=30.0):
            nonlocal call_count
            call_count += 1
            import re

            cols_in_prompt = re.findall(r"col_\d+", prompt)
            cols_data = [
                {"column_name": c, "business_name": f"Field {c}", "description": f"Desc {c}"}
                for c in set(cols_in_prompt)
            ]
            return json.dumps(
                {
                    "matched_tables": ["huge_table"],
                    "tables": {
                        "huge_table": {
                            "business_name": "Huge Table",
                            "description": "A huge table",
                            "columns": cols_data,
                        }
                    },
                }
            )

        config = EnrichmentConfig(
            ultra_wide_threshold=40,
            ultra_wide_chunk_size=30,
            llm_match_threshold=0.0,
            retry_backoff_base_sec=0.01,
        )

        with patch("src.services.pass2_cluster_enrichment.execute_llm_request", side_effect=mock_execute):
            result = await _handle_ultra_wide_table(table, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert call_count == 4
        assert len(result["columns"]) == 120

    @pytest.mark.asyncio
    async def test_35_cols_no_split(self) -> None:
        """35 cols < 40 threshold → no splitting, handled as normal table."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        table = _make_wide_table("normal_table", 35)
        cluster = [[table]]
        glossary = _build_global_glossary(["normal_table"])

        call_count = 0

        async def mock_enrich(prompt_builder, cluster_data, glossary_data, dialect, sem, config):
            nonlocal call_count
            call_count += 1
            return _llm_response_for_tables(
                [t["table_name"] for t in cluster_data],
                columns_per_table=max(len(t.get("columns", [])) for t in cluster_data),
            )

        config = EnrichmentConfig(
            ultra_wide_threshold=40,
            llm_match_threshold=0.0,
            retry_backoff_base_sec=0.01,
        )

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", side_effect=mock_enrich):
            result = await enrich_clusters_parallel(cluster, glossary, "postgresql", asyncio.Semaphore(3), config)

        assert call_count == 1
        assert "normal_table" in result

    @pytest.mark.asyncio
    async def test_fallback_response_merges_glossary(self) -> None:
        """When enrich_cluster_with_retry returns fallback dict with tables list, merge gracefully."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        cluster = [[_make_table("orders"), _make_table("items")]]
        glossary = {
            "orders": {"business_name": "Đơn hàng", "description": "Bảng đơn hàng"},
            "items": {"business_name": "Sản phẩm", "description": "Bảng sản phẩm"},
        }
        fallback_resp = {
            "source": "fallback",
            "tables": ["orders", "items"],
            "matched_tables": [],
            "metrics": [],
        }

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", return_value=fallback_resp):
            result = await enrich_clusters_parallel(cluster, glossary, "postgresql", asyncio.Semaphore(1))

        assert result["orders"]["business_name"] == "Đơn hàng"
        assert result["orders"]["description"] == "Bảng đơn hàng"
        assert result["items"]["business_name"] == "Sản phẩm"
        assert len(result["orders"]["columns"]) == 3

    @pytest.mark.asyncio
    async def test_list_tables_format_merged(self) -> None:
        """When LLM returns tables as list of dicts, normalize and merge."""
        from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

        cluster = [[_make_table("orders")]]
        glossary = {"orders": {"business_name": "Đơn hàng", "description": "Bảng đơn hàng"}}
        llm_resp = {
            "matched_tables": ["orders"],
            "tables": [
                {
                    "table_name": "orders",
                    "business_name": "Đơn hàng LLM",
                    "description": "Mô tả LLM",
                    "columns": [{"column_name": "col_0", "business_name": "Cột 0", "description": "ID"}],
                }
            ],
        }

        with patch("src.services.pass2_cluster_enrichment.enrich_cluster_with_retry", return_value=llm_resp):
            result = await enrich_clusters_parallel(cluster, glossary, "postgresql", asyncio.Semaphore(1))

        assert result["orders"]["business_name"] == "Đơn hàng LLM"
        assert result["orders"]["columns"][0]["business_name"] == "Cột 0"
