"""Integration tests for Two-Pass Semantic Enrichment pipeline.

Covers: clustering, Pass 1 → Pass 2 end-to-end, state flow, concurrency, HITL roundtrip.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.enrich_node import enrich_node
from src.agents.state import AgentState
from src.models.raw_schema import (
    ColumnMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    RawSchema,
    SourceMetadata,
    TableMetadata,
)
from src.services.clustering import cluster_tables, table_key

# ---------------------------------------------------------------------------
# Helpers — build mock schema with 34 tables (3 hubs, 3 domains, satellites, lookups)
# ---------------------------------------------------------------------------

_HUB_TABLES = ["customer", "product", "warehouse"]


def _col(name: str, dtype: str = "integer", pk: bool = False, fk: bool = False) -> ColumnMetadata:
    return ColumnMetadata(
        column_name=name,
        data_type=dtype,
        is_nullable=not pk,
        is_primary_key=pk,
        is_foreign_key=fk,
        default_value=None,
        sample_values=None,
        references=None,
    )


def _fk(col: str, ref_table: str, ref_col: str = "id") -> ForeignKeyMetadata:
    return ForeignKeyMetadata(
        constraint_name=f"fk_{col}_{ref_table}",
        constrained_columns=[col],
        referred_schema=None,
        referred_table=ref_table,
        referred_columns=[ref_col],
    )


def _table(name: str, cols: list[ColumnMetadata], fks: list[ForeignKeyMetadata] | None = None) -> TableMetadata:
    return TableMetadata(
        table_name=name,
        schema_name=None,
        table_type="BASE TABLE",
        row_count_estimate=None,
        columns=cols,
        primary_keys=["id"] if any(c["is_primary_key"] for c in cols) else [],
        foreign_keys=fks or [],
        indexes=[IndexMetadata(index_name=f"pk_{name}", columns=["id"], is_unique=True)]
        if any(c["is_primary_key"] for c in cols)
        else [],
    )


def _id_col(pk: bool = True) -> ColumnMetadata:
    return _col("id", "integer", pk=pk)


def _name_col() -> ColumnMetadata:
    return _col("name", "varchar")


def _ts_col() -> ColumnMetadata:
    return _col("created_at", "timestamp")


def _build_34_tables() -> list[TableMetadata]:
    """Build 34 tables: 3 hubs, 3 domains, 11 satellites, 12 lookups."""
    tables: list[TableMetadata] = []

    # Hub tables (no FKs, high in-degree)
    for hub in _HUB_TABLES:
        tables.append(
            _table(hub, [_id_col(), _name_col(), _col("status", "varchar"), _ts_col(), _col("notes", "text")])
        )

    # Domain 1 — Orders (self-contained, no hub FKs)
    tables.append(
        _table(
            "orders",
            [
                _id_col(),
                _col("order_number", "varchar"),
                _col("total", "numeric"),
                _col("status", "varchar"),
                _ts_col(),
            ],
        )
    )
    tables.append(
        _table(
            "order_items",
            [
                _id_col(),
                _col("quantity", "integer"),
                _col("unit_price", "numeric"),
                _col("discount", "numeric"),
                _col("line_total", "numeric"),
            ],
            [_fk("order_id", "orders")],
        )
    )
    tables.append(
        _table(
            "payments",
            [_id_col(), _col("amount", "numeric"), _col("method", "varchar"), _col("status", "varchar"), _ts_col()],
            [_fk("order_id", "orders")],
        )
    )

    # Domain 2 — Inventory (self-contained)
    tables.append(
        _table(
            "inventory",
            [_id_col(), _col("sku", "varchar"), _col("quantity", "integer"), _col("location", "varchar"), _ts_col()],
        )
    )
    tables.append(
        _table(
            "stock_transfers",
            [_id_col(), _col("from_loc", "varchar"), _col("to_loc", "varchar"), _col("qty", "integer"), _ts_col()],
            [_fk("inventory_id", "inventory")],
        )
    )
    tables.append(
        _table(
            "stock_counts",
            [
                _id_col(),
                _col("counted_qty", "integer"),
                _col("system_qty", "integer"),
                _col("variance", "integer"),
                _ts_col(),
            ],
            [_fk("inventory_id", "inventory")],
        )
    )

    # Domain 3 — Reviews (self-contained)
    tables.append(
        _table(
            "reviews", [_id_col(), _col("rating", "integer"), _col("title", "varchar"), _col("body", "text"), _ts_col()]
        )
    )
    tables.append(
        _table(
            "review_comments",
            [_id_col(), _col("body", "text"), _col("author", "varchar"), _col("is_edited", "boolean"), _ts_col()],
            [_fk("review_id", "reviews")],
        )
    )

    # Customer satellites (FK only to customer hub)
    for sat in ["customer_addresses", "customer_contacts", "customer_loyalty", "customer_preferences"]:
        tables.append(
            _table(
                sat,
                [
                    _id_col(),
                    _col("value", "varchar"),
                    _col("type", "varchar"),
                    _col("is_primary", "boolean"),
                    _ts_col(),
                ],
                [_fk("customer_id", "customer")],
            )
        )

    # Product satellites (FK only to product hub)
    for sat in ["product_images", "product_attributes", "product_variants", "product_reviews"]:
        tables.append(
            _table(
                sat,
                [
                    _id_col(),
                    _col("value", "varchar"),
                    _col("type", "varchar"),
                    _col("sort_order", "integer"),
                    _ts_col(),
                ],
                [_fk("product_id", "product")],
            )
        )

    # Warehouse satellites (FK only to warehouse hub)
    for sat in ["warehouse_zones", "warehouse_staff", "warehouse_inventory"]:
        tables.append(
            _table(
                sat,
                [
                    _id_col(),
                    _col("label", "varchar"),
                    _col("capacity", "integer"),
                    _col("is_active", "boolean"),
                    _ts_col(),
                ],
                [_fk("warehouse_id", "warehouse")],
            )
        )

    # Lookup tables (no FKs)
    for lk in [
        "categories",
        "brands",
        "suppliers",
        "currencies",
        "countries",
        "languages",
        "timezones",
        "tax_rates",
        "shipping_methods",
        "payment_methods",
        "units",
        "statuses",
    ]:
        tables.append(
            _table(
                lk,
                [
                    _id_col(),
                    _name_col(),
                    _col("code", "varchar"),
                    _col("description", "text"),
                    _col("is_active", "boolean"),
                ],
            )
        )

    return tables


def _make_raw_schema(tables: list[TableMetadata]) -> RawSchema:
    return RawSchema(
        source=SourceMetadata(
            type="live_connection", db_engine="postgresql", connection_id=1, extracted_at="2026-01-01T00:00:00"
        ),
        tables=tables,
        relationships=[],
    )


def _build_pass1_glossary(tables: list[TableMetadata]) -> dict[str, dict]:
    """Build mock Pass 1 glossary matching the expected LLM output format."""
    result: dict[str, dict] = {}
    for t in tables:
        key = table_key(t)
        name = t["table_name"]
        result[key] = {"business_name": name.replace("_", " ").title(), "description": f"Mock glossary for {name}"}
    return result


def _build_pass2_enrichment(cluster: list[TableMetadata]) -> dict[str, Any]:
    """Build mock Pass 2 LLM response for a single cluster."""
    tables_dict: dict[str, dict] = {}
    matched: list[str] = []
    for t in cluster:
        tname = t["table_name"]
        matched.append(tname)
        tables_dict[tname] = {
            "business_name": tname.replace("_", " ").title(),
            "description": f"Enriched {tname}",
            "columns": [
                {
                    "column_name": c["column_name"],
                    "business_name": c["column_name"].replace("_", " ").title(),
                    "description": f"Col {c['column_name']}",
                }
                for c in t["columns"]
            ],
        }
    return {"matched_tables": matched, "tables": tables_dict}


def _make_mock_llm_for_pass1(glossary: dict[str, dict], tables: list[TableMetadata]):
    """Return a mock LLM that responds to Pass 1 prompts with the glossary."""
    mock_llm = AsyncMock()

    async def _ainvoke(prompt: str):
        # Extract table names from prompt and return matching glossary entries
        batch: dict[str, dict] = {}
        for t in tables:
            if t["table_name"] in prompt:
                key = table_key(t)
                if key in glossary:
                    batch[t["table_name"]] = glossary[key]
        resp = MagicMock()
        resp.content = json.dumps(batch, ensure_ascii=False)
        return resp

    mock_llm.ainvoke = AsyncMock(side_effect=_ainvoke)
    return mock_llm


def _make_mock_llm_for_pass2(tables: list[TableMetadata]):
    """Return a mock LLM that responds to Pass 2 prompts with enrichment data."""
    mock_llm = AsyncMock()
    table_map = {t["table_name"]: t for t in tables}

    async def _ainvoke(prompt: str):
        # Find which tables are mentioned in the prompt
        cluster_tables_list: list[TableMetadata] = []
        for tname, tmeta in table_map.items():
            if f"### Bảng: {tname}" in prompt or tname in prompt:
                cluster_tables_list.append(tmeta)
        enrichment = _build_pass2_enrichment(cluster_tables_list or tables[:1])
        resp = MagicMock()
        resp.content = json.dumps(enrichment, ensure_ascii=False)
        return resp

    mock_llm.ainvoke = AsyncMock(side_effect=_ainvoke)
    return mock_llm


# ---------------------------------------------------------------------------
# Test 1: Clustering separates domains correctly
# ---------------------------------------------------------------------------


class TestClusteringWith30PlusTables:
    """Verify hub-detached clustering with 34 tables, 3 hubs."""

    def test_total_table_count(self) -> None:
        tables = _build_34_tables()
        assert len(tables) == 34

    def test_clustering_produces_correct_cluster_count(self) -> None:
        tables = _build_34_tables()
        clusters = cluster_tables(tables)
        # 3 domain clusters + 3 hub entity clusters + 12 lookup singletons = 18
        assert len(clusters) == 18

    def test_clustering_preserves_all_tables(self) -> None:
        tables = _build_34_tables()
        clusters = cluster_tables(tables)
        all_names = set()
        for cluster in clusters:
            for t in cluster:
                all_names.add(t["table_name"])
        assert all_names == {t["table_name"] for t in tables}

    def test_domain_clusters_composition(self) -> None:
        """Domain clusters contain connected non-hub, non-satellite tables."""
        tables = _build_34_tables()
        clusters = cluster_tables(tables)

        all_cluster_names = [{t["table_name"] for t in c} for c in clusters]

        assert {"orders", "order_items", "payments"} in all_cluster_names
        assert {"inventory", "stock_transfers", "stock_counts"} in all_cluster_names
        assert {"reviews", "review_comments"} in all_cluster_names

    def test_hub_entity_clusters_composition(self) -> None:
        """Hub entity clusters contain hub table + its satellites."""
        tables = _build_34_tables()
        clusters = cluster_tables(tables)

        all_cluster_names = [{t["table_name"] for t in c} for c in clusters]

        assert {
            "customer",
            "customer_addresses",
            "customer_contacts",
            "customer_loyalty",
            "customer_preferences",
        } in all_cluster_names
        assert {
            "product",
            "product_images",
            "product_attributes",
            "product_variants",
            "product_reviews",
        } in all_cluster_names
        assert {"warehouse", "warehouse_zones", "warehouse_staff", "warehouse_inventory"} in all_cluster_names

    def test_lookup_tables_are_singletons(self) -> None:
        """Lookup tables appear as singleton clusters."""
        tables = _build_34_tables()
        clusters = cluster_tables(tables)
        lookup_names = {
            "categories",
            "brands",
            "suppliers",
            "currencies",
            "countries",
            "languages",
            "timezones",
            "tax_rates",
            "shipping_methods",
            "payment_methods",
            "units",
            "statuses",
        }
        singleton_names = {cluster[0]["table_name"] for cluster in clusters if len(cluster) == 1}
        # Lookup singletons are among the singletons (hub satellites are NOT singletons)
        assert lookup_names.issubset(singleton_names)


# ---------------------------------------------------------------------------
# Test 2 + 3: End-to-end pipeline (enrich_node with mocked LLM)
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Full pipeline: enrich_node → Pass 1 → cluster → Pass 2 → enriched_schema."""

    @pytest.mark.asyncio
    async def test_enrich_node_returns_correct_output_format(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        assert "enriched_schema" in result
        assert "global_glossary" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_enriched_schema_has_all_tables(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        enriched = result["enriched_schema"]
        assert "tables" in enriched
        assert len(enriched["tables"]) == 34
        # All enriched tables must have business_name (core requirement)
        for et in enriched["tables"]:
            assert et.get("business_name"), "Missing business_name in enriched table"

    @pytest.mark.asyncio
    async def test_enriched_tables_have_business_fields(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        for enriched_table in result["enriched_schema"]["tables"]:
            assert "business_name" in enriched_table
            assert "description" in enriched_table
            assert "columns" in enriched_table
            for col in enriched_table["columns"]:
                assert "column_name" in col
                assert "business_name" in col

    @pytest.mark.asyncio
    async def test_global_glossary_populated(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        glossary = result["global_glossary"]
        assert isinstance(glossary, dict)
        assert len(glossary) == 34
        for key in glossary:
            assert "business_name" in glossary[key]
            assert "description" in glossary[key]


# ---------------------------------------------------------------------------
# Test 4: State flow — global_glossary and enriched_schema format
# ---------------------------------------------------------------------------


class TestStateFlow:
    """Verify output state is compatible with metric_suggest_node."""

    @pytest.mark.asyncio
    async def test_output_state_has_required_keys(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        # State fields expected by downstream nodes
        assert "enriched_schema" in result
        assert "global_glossary" in result
        assert isinstance(result["enriched_schema"], dict)
        assert isinstance(result["global_glossary"], dict)

    @pytest.mark.asyncio
    async def test_enriched_schema_tables_is_list(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                result = await enrich_node(state)

        assert isinstance(result["enriched_schema"]["tables"], list)
        assert len(result["enriched_schema"]["tables"]) == 34


# ---------------------------------------------------------------------------
# Test 5: Concurrency — max 3 concurrent LLM calls
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Verify semaphore limits concurrent LLM calls to max_concurrency (3)."""

    @pytest.mark.asyncio
    async def test_max_concurrent_llm_calls(self) -> None:
        tables = _build_34_tables()
        raw_schema = _make_raw_schema(tables)
        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        pass1_glossary = _build_pass1_glossary(tables)

        concurrent_count = 0
        max_observed = 0

        async def _tracked_ainvoke(prompt: str):
            nonlocal concurrent_count, max_observed
            concurrent_count += 1
            max_observed = max(max_observed, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            # Return valid JSON for any prompt
            for t in tables:
                if t["table_name"] in prompt:
                    batch = {
                        t2["table_name"]: pass1_glossary.get(table_key(t2), {"business_name": "X", "description": "Y"})
                        for t2 in tables
                        if t2["table_name"] in prompt
                    }
                    resp = MagicMock()
                    resp.content = json.dumps(batch)
                    return resp
            # Pass 2 response
            enrichment = _build_pass2_enrichment(tables[:1])
            resp = MagicMock()
            resp.content = json.dumps(enrichment)
            return resp

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=_tracked_ainvoke)

        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm):
                await enrich_node(state)

        assert max_observed <= 3


# ---------------------------------------------------------------------------
# Test 6: HITL roundtrip — enrich → user edits → save (no LLM re-call)
# ---------------------------------------------------------------------------


class TestHITLRoundtrip:
    """Verify enrich → user edits → save_node uses edited enrichment without LLM."""

    @pytest.mark.asyncio
    async def test_save_node_uses_edited_enrichment_no_llm(self) -> None:
        tables = _build_34_tables()[:5]
        raw_schema = _make_raw_schema(tables)

        pass1_glossary = _build_pass1_glossary(tables)
        mock_llm_p1 = _make_mock_llm_for_pass1(pass1_glossary, tables)
        mock_llm_p2 = _make_mock_llm_for_pass2(tables)

        state: AgentState = {"raw_schema": raw_schema, "db_type": "postgresql"}

        # Step 1: Run enrichment
        with patch("src.services.pass1_global_glossary.get_llm", return_value=mock_llm_p1):
            with patch("src.services.llm_caller.get_llm", return_value=mock_llm_p2):
                enrich_result = await enrich_node(state)

        # Step 2: User edits enrichment (HITL)
        edited_enrichment = enrich_result["enriched_schema"]
        edited_enrichment["tables"][0]["business_name"] = "User Edited Name"

        # Step 3: save_node should NOT call LLM
        save_state: AgentState = {
            **state,
            "enriched_schema": edited_enrichment,
            "global_glossary": enrich_result["global_glossary"],
            "hitl_approved": True,
            "user_id": 1,
            "db_id": 1,
        }

        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock(return_value=False)
        mock_db_session.commit = AsyncMock()

        mock_canonical = MagicMock()
        tracking_llm = AsyncMock()
        tracking_llm.ainvoke = AsyncMock(side_effect=Exception("LLM should not be called during save"))

        mock_save_fn = AsyncMock(return_value={"tables": [], "relationships": []})

        with patch("src.agents.nodes.save_node.raw_schema_to_canonical", return_value=mock_canonical):
            with patch("src.agents.nodes.save_node.get_db_session", return_value=async_iter([mock_db_session])):
                with patch("src.agents.nodes.save_node.enrich_and_save_canonical_schema", mock_save_fn):
                    with patch("src.agents.nodes.save_node._save_approved_metrics", new_callable=AsyncMock):
                        with patch("src.services.llm.get_llm", return_value=tracking_llm):
                            from src.agents.nodes.save_node import save_node

                            save_result = await save_node(save_state)

        assert "error" not in save_result, f"save_node returned error: {save_result.get('error')}"
        assert "semantic_layer_id" in save_result
        tracking_llm.ainvoke.assert_not_called()
        mock_save_fn.assert_called_once()
        save_call_kwargs = mock_save_fn.call_args.kwargs
        assert save_call_kwargs.get("enrichment") == edited_enrichment


async def async_iter(items):
    """Async generator helper for mocking get_db_session."""
    for item in items:
        yield item
