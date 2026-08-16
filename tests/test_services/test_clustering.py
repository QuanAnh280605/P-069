"""Tests for Hub-Detached Domain Graph Partitioning (clustering module)."""

from __future__ import annotations

from src.models.raw_schema import ColumnMetadata, ForeignKeyMetadata, TableMetadata
from src.services.clustering import (
    _build_hub_detached_graph,
    _compute_in_degrees,
    _find_connected_components,
    _identify_hub_tables,
    _split_component_by_budget,
    cluster_tables,
    table_key,
)
from src.services.enrichment_config import EnrichmentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _col(name: str, **overrides) -> ColumnMetadata:
    """Create a minimal ColumnMetadata."""
    base: ColumnMetadata = {
        "column_name": name,
        "data_type": "INTEGER",
        "is_nullable": True,
        "is_primary_key": False,
        "is_foreign_key": False,
        "default_value": None,
        "sample_values": None,
        "references": None,
    }
    base.update(overrides)
    return base


def _fk(
    constrained: list[str],
    referred_table: str,
    referred_columns: list[str],
    referred_schema: str | None = None,
) -> ForeignKeyMetadata:
    """Create a minimal ForeignKeyMetadata."""
    return {
        "constraint_name": None,
        "constrained_columns": constrained,
        "referred_schema": referred_schema,
        "referred_table": referred_table,
        "referred_columns": referred_columns,
    }


def _table(
    name: str,
    num_cols: int = 5,
    fks: list[ForeignKeyMetadata] | None = None,
    schema: str | None = None,
) -> TableMetadata:
    """Create a TableMetadata with num_cols auto-generated columns."""
    columns = [_col(f"col_{i}") for i in range(num_cols)]
    return {
        "table_name": name,
        "schema_name": schema,
        "table_type": "BASE TABLE",
        "row_count_estimate": None,
        "columns": columns,
        "primary_keys": ["col_0"],
        "foreign_keys": fks or [],
        "indexes": [],
    }


# ---------------------------------------------------------------------------
# table_key
# ---------------------------------------------------------------------------


class TestTableKey:
    def test_with_schema(self) -> None:
        t = _table("users", schema="public")
        assert table_key(t) == "public.users"

    def test_without_schema(self) -> None:
        t = _table("users")
        assert table_key(t) == "users"


# ---------------------------------------------------------------------------
# _compute_in_degrees
# ---------------------------------------------------------------------------


class TestComputeInDegrees:
    def test_self_referencing_fk_not_counted(self) -> None:
        emp = _table(
            "employee",
            fks=[_fk(["manager_id"], "employee", ["id"])],
        )
        result = _compute_in_degrees([emp])
        assert result["employee"] == 0

    def test_composite_fk_counted_once(self) -> None:
        orders = _table("orders")
        ol = _table(
            "order_line",
            fks=[_fk(["order_id", "line_no"], "orders", ["id", "line_no"])],
        )
        result = _compute_in_degrees([orders, ol])
        assert result["orders"] == 1

    def test_basic_in_degree(self) -> None:
        customer = _table("customer")
        o1 = _table("order1", fks=[_fk(["customer_id"], "customer", ["id"])])
        o2 = _table("order2", fks=[_fk(["customer_id"], "customer", ["id"])])
        result = _compute_in_degrees([customer, o1, o2])
        assert result["customer"] == 2
        assert result["order1"] == 0
        assert result["order2"] == 0

    def test_dedup_multiple_fk_same_destination(self) -> None:
        a = _table("a")
        b = _table(
            "b",
            fks=[
                _fk(["a_id1"], "a", ["id1"]),
                _fk(["a_id2"], "a", ["id2"]),
            ],
        )
        result = _compute_in_degrees([a, b])
        assert result["a"] == 1

    def test_fk_orphan_skipped(self) -> None:
        orders = _table(
            "orders",
            fks=[_fk(["customer_id"], "nonexistent", ["id"])],
        )
        result = _compute_in_degrees([orders])
        assert result["orders"] == 0

    def test_multi_schema_composite_key(self) -> None:
        orders = _table("orders", schema="sales")
        ol = _table(
            "order_line",
            schema="sales",
            fks=[_fk(["order_id", "line_no"], "orders", ["id", "line_no"], "sales")],
        )
        result = _compute_in_degrees([orders, ol])
        assert result["orders"] == 1
        assert result["order_line"] == 0


# ---------------------------------------------------------------------------
# _identify_hub_tables
# ---------------------------------------------------------------------------


class TestIdentifyHubTables:
    def test_basic_hub_detection(self) -> None:
        customer = _table("customer")
        t1 = _table("t1", fks=[_fk(["cid"], "customer", ["id"])])
        t2 = _table("t2", fks=[_fk(["cid"], "customer", ["id"])])
        t3 = _table("t3", fks=[_fk(["cid"], "customer", ["id"])])
        tables = [customer, t1, t2, t3]
        hubs = _identify_hub_tables(tables, EnrichmentConfig(hub_in_degree_threshold=3))
        assert hubs == {"customer"}

    def test_no_hubs_below_threshold(self) -> None:
        customer = _table("customer")
        t1 = _table("t1", fks=[_fk(["cid"], "customer", ["id"])])
        tables = [customer, t1]
        hubs = _identify_hub_tables(tables, EnrichmentConfig(hub_in_degree_threshold=3))
        assert hubs == set()

    def test_self_ref_not_inflating_hub(self) -> None:
        emp = _table(
            "employee",
            fks=[_fk(["mgr"], "employee", ["id"])],
        )
        hubs = _identify_hub_tables([emp], EnrichmentConfig(hub_in_degree_threshold=1))
        assert "employee" not in hubs


# ---------------------------------------------------------------------------
# _build_hub_detached_graph
# ---------------------------------------------------------------------------


class TestBuildHubDetachedGraph:
    def test_hub_edges_removed(self) -> None:
        customer = _table("customer")
        order = _table("order", fks=[_fk(["cid"], "customer", ["id"])])
        review = _table("review", fks=[_fk(["oid"], "order", ["id"])])
        graph = _build_hub_detached_graph([customer, order, review], {"customer"})
        assert "customer" not in graph
        assert "order" in graph
        assert "review" in graph.get("order", set())

    def test_no_edges_when_all_to_hub(self) -> None:
        customer = _table("customer")
        o = _table("o", fks=[_fk(["cid"], "customer", ["id"])])
        graph = _build_hub_detached_graph([customer, o], {"customer"})
        assert len(graph) == 0


# ---------------------------------------------------------------------------
# _find_connected_components
# ---------------------------------------------------------------------------


class TestFindConnectedComponents:
    def test_isolated_nodes(self) -> None:
        comps = _find_connected_components({}, {"a", "b", "c"})
        assert len(comps) == 3
        assert all(len(c) == 1 for c in comps)

    def test_single_component(self) -> None:
        graph = {"a": {"b"}, "b": {"a", "c"}, "c": {"b"}}
        comps = _find_connected_components(graph, {"a", "b", "c"})
        assert len(comps) == 1
        assert comps[0] == {"a", "b", "c"}

    def test_two_components(self) -> None:
        graph = {"a": {"b"}, "b": {"a"}, "c": {"d"}, "d": {"c"}}
        comps = _find_connected_components(graph, {"a", "b", "c", "d"})
        assert len(comps) == 2


# ---------------------------------------------------------------------------
# _split_component_by_budget
# ---------------------------------------------------------------------------


class TestSplitComponentByBudget:
    def test_single_table(self) -> None:
        t = _table("t1")
        table_map = {"t1": t}
        result = _split_component_by_budget({"t1"}, table_map)
        assert result == [["t1"]]

    def test_ultra_wide_table_independent(self) -> None:
        t = _table("wide", num_cols=51)
        table_map = {"wide": t}
        result = _split_component_by_budget({"wide"}, table_map)
        assert result == [["wide"]]

    def test_chain_respects_budget(self) -> None:
        tables = [
            _table("T1", num_cols=15),
            _table("T2", num_cols=10),
            _table("T3", num_cols=10),
            _table("T4", num_cols=15),
            _table("T5", num_cols=12),
            _table("T6", num_cols=8),
            _table("T7", num_cols=5),
        ]
        for i in range(len(tables) - 1):
            tables[i]["foreign_keys"].append(_fk(["next_id"], tables[i + 1]["table_name"], ["id"]))
            tables[i + 1]["foreign_keys"].append(_fk(["prev_id"], tables[i]["table_name"], ["id"]))
        table_map = {t["table_name"]: t for t in tables}
        config = EnrichmentConfig(max_cols_per_cluster=45, max_tables_per_cluster=6)
        result = _split_component_by_budget(set(table_map.keys()), table_map, config)
        assert len(result) >= 2
        for cluster in result:
            total = sum(len(table_map[n]["columns"]) for n in cluster)
            assert total <= 45
            assert len(cluster) <= 6


# ---------------------------------------------------------------------------
# cluster_tables — full integration
# ---------------------------------------------------------------------------


class TestClusterTables:
    def test_multi_hub_scenario(self) -> None:
        config = EnrichmentConfig(hub_in_degree_threshold=2, max_cols_per_cluster=45)

        customer = _table("customer", num_cols=10)
        item = _table("item", num_cols=10)
        store = _table("store", num_cols=10)

        order = _table("order", num_cols=10, fks=[_fk(["cid"], "customer", ["id"])])
        wishlist = _table("wishlist", num_cols=10, fks=[_fk(["cid"], "customer", ["id"])])

        review = _table("review", num_cols=10, fks=[_fk(["iid"], "item", ["id"])])
        cart = _table("cart", num_cols=10, fks=[_fk(["iid"], "item", ["id"])])

        staff = _table("staff", num_cols=10, fks=[_fk(["sid"], "store", ["id"])])
        shift = _table("shift", num_cols=10, fks=[_fk(["sid"], "store", ["id"])])

        tables = [customer, item, store, order, wishlist, review, cart, staff, shift]

        hubs = _identify_hub_tables(tables, config)
        assert hubs == {"customer", "item", "store"}

        result = cluster_tables(tables, config)
        assert len(result) == 3

        names_per_cluster = [{t["table_name"] for t in c} for c in result]
        assert {"customer", "order", "wishlist"} in names_per_cluster
        assert {"item", "review", "cart"} in names_per_cluster
        assert {"store", "staff", "shift"} in names_per_cluster

    def test_self_referencing_fk(self) -> None:
        emp = _table(
            "employee",
            num_cols=5,
            fks=[_fk(["manager_id"], "employee", ["id"])],
        )
        result = cluster_tables([emp])
        assert len(result) == 1
        assert result[0][0]["table_name"] == "employee"

        in_deg = _compute_in_degrees([emp])
        assert in_deg["employee"] == 0

    def test_composite_fk(self) -> None:
        orders = _table("orders", num_cols=5)
        ol = _table(
            "order_line",
            num_cols=5,
            fks=[_fk(["order_id", "line_no"], "orders", ["id", "line_no"])],
        )
        in_deg = _compute_in_degrees([orders, ol])
        assert in_deg["orders"] == 1
        assert in_deg["order_line"] == 0

        config = EnrichmentConfig(hub_in_degree_threshold=1)
        result = cluster_tables([orders, ol], config)
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_hub_vs_lookup_separation(self) -> None:
        customer = _table("customer", num_cols=5)
        product = _table("product", num_cols=5)
        log = _table("log", num_cols=5)

        for _ in range(3):
            customer["foreign_keys"].append(_fk(["x"], "customer", ["id"]))
            product["foreign_keys"].append(_fk(["x"], "product", ["id"]))

        tables = [customer, product, log]
        config = EnrichmentConfig(hub_in_degree_threshold=3)

        result = cluster_tables(tables, config)
        all_flat = [t for cluster in result for t in cluster]
        assert any(t["table_name"] == "log" for t in all_flat)
        assert len(result) == 3

    def test_fk_orphan_guard(self) -> None:
        orders = _table(
            "orders",
            fks=[_fk(["customer_id"], "nonexistent", ["id"])],
        )
        in_deg = _compute_in_degrees([orders])
        assert in_deg["orders"] == 0
        result = cluster_tables([orders])
        assert len(result) == 1

    def test_multi_table_cluster_budget(self) -> None:
        t1 = _table("t1", num_cols=20)
        t2 = _table("t2", num_cols=20)
        t3 = _table("t3", num_cols=20)
        t1["foreign_keys"].append(_fk(["t2_id"], "t2", ["id"]))
        t2["foreign_keys"].append(_fk(["t1_id"], "t1", ["id"]))
        t2["foreign_keys"].append(_fk(["t3_id"], "t3", ["id"]))
        t3["foreign_keys"].append(_fk(["t2_id"], "t2", ["id"]))
        tables = [t1, t2, t3]
        config = EnrichmentConfig(max_cols_per_cluster=45)
        result = cluster_tables(tables, config)
        assert len(result) >= 2
        for cluster in result:
            assert sum(len(t["columns"]) for t in cluster) <= 45

    def test_ultra_wide_table(self) -> None:
        wide = _table("wide", num_cols=51)
        result = cluster_tables([wide])
        assert len(result) == 1
        assert len(result[0][0]["columns"]) == 51

    def test_orphan_tables_lookup(self) -> None:
        customer = _table("customer", num_cols=5)
        product = _table("product", num_cols=5)
        log = _table("log", num_cols=5)
        for _ in range(3):
            customer["foreign_keys"].append(_fk(["x"], "customer", ["id"]))
            product["foreign_keys"].append(_fk(["x"], "product", ["id"]))

        tables = [customer, product, log]
        config = EnrichmentConfig(hub_in_degree_threshold=3)
        result = cluster_tables(tables, config)

        lookup_cluster = [c for c in result if len(c) == 1 and c[0]["table_name"] == "log"]
        assert len(lookup_cluster) == 1

    def test_single_table(self) -> None:
        t = _table("solo")
        result = cluster_tables([t])
        assert len(result) == 1
        assert result[0][0]["table_name"] == "solo"

    def test_empty_input(self) -> None:
        assert cluster_tables([]) == []

    def test_multi_schema_composite_key(self) -> None:
        orders = _table("orders", schema="sales")
        ol = _table(
            "order_line",
            schema="sales",
            fks=[_fk(["order_id", "line_no"], "orders", ["id", "line_no"], "sales")],
        )
        config = EnrichmentConfig(hub_in_degree_threshold=1)
        result = cluster_tables([orders, ol], config)
        assert len(result) == 1
        keys = {table_key(t) for t in result[0]}
        assert "sales.orders" in keys
        assert "sales.order_line" in keys

    def test_satellite_criterion(self) -> None:
        customer = _table("customer", num_cols=10)

        # 3 tables reference customer → hub (in-degree = 3)
        ref1 = _table("ref1", num_cols=10, fks=[_fk(["cid"], "customer", ["id"])])
        ref2 = _table("ref2", num_cols=10, fks=[_fk(["cid"], "customer", ["id"])])

        # order has FK to customer (hub) AND invoice (domain) → NOT a satellite
        order = _table(
            "order",
            num_cols=10,
            fks=[
                _fk(["customer_id"], "customer", ["id"]),
                _fk(["invoice_id"], "invoice", ["id"]),
            ],
        )
        invoice = _table("invoice", num_cols=10)

        tables = [customer, ref1, ref2, order, invoice]
        config = EnrichmentConfig(hub_in_degree_threshold=3)

        result = cluster_tables(tables, config)
        assert len(result) == 2

        domain = result[0]
        assert {t["table_name"] for t in domain} == {"order", "invoice"}

    def test_column_budget_splitter(self) -> None:
        chain_tables = [
            _table("T1", num_cols=15),
            _table("T2", num_cols=10),
            _table("T3", num_cols=10),
            _table("T4", num_cols=15),
            _table("T5", num_cols=12),
            _table("T6", num_cols=8),
            _table("T7", num_cols=5),
        ]
        for i in range(len(chain_tables) - 1):
            chain_tables[i]["foreign_keys"].append(_fk(["next_id"], chain_tables[i + 1]["table_name"], ["id"]))
            chain_tables[i + 1]["foreign_keys"].append(_fk(["prev_id"], chain_tables[i]["table_name"], ["id"]))
        config = EnrichmentConfig(max_cols_per_cluster=45, max_tables_per_cluster=6)
        result = cluster_tables(chain_tables, config)

        assert len(result) >= 2
        for cluster in result:
            total_cols = sum(len(t["columns"]) for t in cluster)
            assert total_cols <= 45
            assert len(cluster) <= 6
