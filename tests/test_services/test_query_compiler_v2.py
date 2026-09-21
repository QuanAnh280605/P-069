"""Behavior tests for the canonical semantic query compiler interface."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.models.review_mixin import REVIEW_STATUS_APPROVED, REVIEW_STATUS_PENDING
from src.models.schemas import DimensionSelection, SemanticQueryFilter, SemanticQuerySpec
from src.services.query_compiler import SemanticQueryCompiler
from src.services.semantic_compile_error import SemanticCompileError


async def _seed_filtered_metrics(db: AsyncSession) -> tuple[int, list[int]]:
    semantic_db = SemanticDatabaseModel(
        created_by=1, display_name="Sales", db_type="sqlite", conn_url_enc="encrypted", status="draft"
    )
    db.add(semantic_db)
    await db.flush()
    table = SemanticTableModel(
        db_id=semantic_db.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="",
        primary_key_column="id",
    )
    db.add(table)
    await db.flush()
    columns = [
        SemanticColumnModel(
            table_id=table.id,
            column_name=name,
            data_type=data_type,
            business_name=name,
            is_primary_key=name == "id",
        )
        for name, data_type in [("id", "INTEGER"), ("amount", "NUMERIC"), ("status", "TEXT")]
    ]
    db.add_all(columns)
    await db.flush()
    metrics = [
        _metric(semantic_db.id, table.id, columns[1].id, columns[2].id, columns[0].id, status)
        for status in ("completed", "cancelled")
    ]
    db.add_all(metrics)
    await db.commit()
    return semantic_db.id, [metric.id for metric in metrics]


def _metric(
    db_id: int,
    table_id: int,
    amount_id: int,
    status_id: int,
    grain_id: int,
    status: str,
) -> SemanticMetricModel:
    definition = {
        "schema_version": 2,
        "metric": {
            "name": f"Revenue {status}",
            "formula": {
                "function": "SUM",
                "expression": "amount",
                "expression_ast": {"kind": "column", "column_id": amount_id},
            },
            "base_entity": "orders",
            "base_entity_id": table_id,
            "grain": {"column_ids": [grain_id]},
            "filters": [{"field": "status", "column_id": status_id, "operator": "eq", "value": status}],
            "status": "approved",
            "confidence": "high",
            "excluded_notes": "",
        },
    }
    return SemanticMetricModel(
        db_id=db_id,
        created_by=1,
        name=f"Revenue {status}",
        description="",
        sql_template="",
        source="ai",
        status="approved",
        base_entity_id=table_id,
        formula="",
        aggregation_type="SUM",
        definition=definition,
    )


@pytest.mark.asyncio
async def test_metrics_keep_their_fixed_filters_independent(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)

    compiled = await SemanticQueryCompiler(async_session).compile(
        db_id,
        SemanticQuerySpec(metric_ids=metric_ids),
    )

    assert compiled.parameters == {"metric_0": "completed", "metric_1": "cancelled"}
    assert compiled.sql.count("CASE WHEN") == 2
    assert " WHERE " not in compiled.sql


@pytest.mark.asyncio
async def test_runtime_filter_adds_its_required_join(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders = await _table(async_session, db_id, "orders")
    customers = SemanticTableModel(
        db_id=db_id, table_name="customers", business_name="Khách hàng", description="", primary_key_column="id"
    )
    async_session.add(customers)
    await async_session.flush()
    customer_id = SemanticColumnModel(
        table_id=orders.id, column_name="customer_id", data_type="INTEGER", business_name="Mã khách hàng"
    )
    customer_pk = SemanticColumnModel(
        table_id=customers.id,
        column_name="id",
        data_type="INTEGER",
        business_name="Mã khách hàng",
        is_primary_key=True,
    )
    segment = SemanticColumnModel(
        table_id=customers.id, column_name="segment", data_type="TEXT", business_name="Phân khúc"
    )
    async_session.add_all([customer_id, customer_pk, segment])
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=customers.id,
            relationship_type="many_to_one",
            join_condition="orders.customer_id = customers.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": customer_id.id, "to_column_id": customer_pk.id}],
        )
    )
    await async_session.commit()

    query = SemanticQuerySpec(
        metric_ids=[metric_ids[0]],
        filters=[SemanticQueryFilter(column_id=segment.id, operator="eq", value="enterprise")],
    )
    compiled = await SemanticQueryCompiler(async_session).compile(db_id, query)

    assert 'JOIN "customers"' in compiled.sql
    assert '"customers"."segment" = :runtime_1' in compiled.sql


@pytest.mark.asyncio
async def test_time_dimension_compiles_with_requested_sqlite_grain(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders = await _table(async_session, db_id, "orders")
    created_at = SemanticColumnModel(
        table_id=orders.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Ngày tạo",
        is_time_dimension=True,
    )
    async_session.add(created_at)
    await async_session.commit()

    query = SemanticQuerySpec(
        metric_ids=[metric_ids[0]],
        dimensions=[DimensionSelection(column_id=created_at.id, time_grain="month")],
    )
    compiled = await SemanticQueryCompiler(async_session).compile(db_id, query)

    assert """strftime('%Y-%m', "orders"."created_at")""" in compiled.sql
    assert f'"dimension_{created_at.id}"' in compiled.sql


@pytest.mark.asyncio
async def test_reverse_many_to_one_is_rejected_as_fanout(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders = await _table(async_session, db_id, "orders")
    customers = SemanticTableModel(
        db_id=db_id, table_name="customers", business_name="Khách hàng", description="", primary_key_column="id"
    )
    async_session.add(customers)
    await async_session.flush()
    customer_id = SemanticColumnModel(
        table_id=customers.id, column_name="id", data_type="INTEGER", business_name="ID", is_primary_key=True
    )
    async_session.add(customer_id)
    await async_session.flush()
    metric = await async_session.get(SemanticMetricModel, metric_ids[0])
    metric.base_entity_id = customers.id
    metric.definition["metric"]["base_entity"] = "customers"
    metric.definition["metric"]["formula"] = {
        "function": "COUNT",
        "expression": "*",
        "expression_ast": {"kind": "literal", "value": 1},
    }
    metric.definition["metric"]["base_entity_id"] = customers.id
    metric.definition["metric"]["grain"] = {"column_ids": [customer_id.id]}
    metric.definition["metric"]["filters"] = []
    amount = await _column(async_session, orders.id, "amount")
    async_session.add(
        CanonicalRelationshipModel(
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=customers.id,
            relationship_type="many_to_one",
            join_condition="orders.customer_id = customers.id",
            relationship_key="orders_customer",
            validation_status="valid",
            review_status=REVIEW_STATUS_APPROVED,
        )
    )
    await async_session.commit()

    query = SemanticQuerySpec(
        metric_ids=[metric.id],
        dimensions=[DimensionSelection(column_id=amount.id)],
    )
    with pytest.raises(SemanticCompileError) as error:
        await SemanticQueryCompiler(async_session).compile(db_id, query)
    assert error.value.code == "UNSAFE_FANOUT"


@pytest.mark.asyncio
async def test_compiler_normalizes_date_parameters(async_session: AsyncSession) -> None:
    """Date strings in metric filters are normalized to date objects in parameters."""
    from datetime import date

    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    metric = await async_session.get(SemanticMetricModel, metric_ids[0])
    table = await _table(async_session, db_id, "orders")
    created_col = SemanticColumnModel(
        table_id=table.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Created At",
        is_time_dimension=True,
    )
    async_session.add(created_col)
    await async_session.flush()

    metric.definition["metric"]["filters"] = [
        {"field": "created_at", "operator": "gte", "value": "2025-01-01", "column_id": created_col.id},
        {"field": "created_at", "operator": "lt", "value": "2025-02-01", "column_id": created_col.id},
    ]
    await async_session.commit()

    query = SemanticQuerySpec(metric_ids=[metric.id])
    compiled = await SemanticQueryCompiler(async_session).compile(db_id, query)
    assert compiled.parameters["metric_0"] == date(2025, 1, 1)
    assert compiled.parameters["metric_1"] == date(2025, 2, 1)


async def _table(db: AsyncSession, db_id: int, name: str) -> SemanticTableModel:
    from sqlalchemy import select

    result = await db.execute(
        select(SemanticTableModel).where(SemanticTableModel.db_id == db_id, SemanticTableModel.table_name == name)
    )
    return result.scalar_one()


async def _column(db: AsyncSession, table_id: int, name: str) -> SemanticColumnModel:
    from sqlalchemy import select

    result = await db.execute(
        select(SemanticColumnModel).where(
            SemanticColumnModel.table_id == table_id,
            SemanticColumnModel.column_name == name,
        )
    )
    return result.scalar_one()


async def _seed_ambiguous_schema(
    db: AsyncSession,
    db_id: int,
    metric_ids: list[int],
    reverse_order: bool = False,
) -> tuple[int, int]:
    """Build two equal-shortest orders->products paths through different bridges.

    Returns (orders_table_id, product_name_column_id).
    """
    orders = await _table(db, db_id, "orders")
    order_lines = SemanticTableModel(
        db_id=db_id, table_name="order_lines", business_name="", description="", primary_key_column="id"
    )
    snapshots = SemanticTableModel(
        db_id=db_id, table_name="snapshots", business_name="", description="", primary_key_column="id"
    )
    products = SemanticTableModel(
        db_id=db_id, table_name="products", business_name="", description="", primary_key_column="id"
    )
    db.add_all([order_lines, snapshots, products])
    await db.flush()
    columns = {
        name: SemanticColumnModel(table_id=tid, column_name=name, data_type="INTEGER", business_name=name)
        for name, tid in [
            ("ol_fk", orders.id),
            ("ol_pk", order_lines.id),
            ("ol_prod_fk", order_lines.id),
            ("sn_fk", orders.id),
            ("sn_pk", snapshots.id),
            ("sn_prod_fk", snapshots.id),
            ("prod_pk", products.id),
            ("prod_name", products.id),
        ]
    }
    db.add_all(columns.values())
    await db.flush()
    rels = [
        CanonicalRelationshipModel(
            id=101 if not reverse_order else 201,
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=order_lines.id,
            relationship_type="many_to_one",
            join_condition="orders.ol_fk = order_lines.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": columns["ol_fk"].id, "to_column_id": columns["ol_pk"].id}],
        ),
        CanonicalRelationshipModel(
            id=102 if not reverse_order else 202,
            connection_id=db_id,
            from_entity_id=order_lines.id,
            to_entity_id=products.id,
            relationship_type="many_to_one",
            join_condition="order_lines.ol_prod_fk = products.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": columns["ol_prod_fk"].id, "to_column_id": columns["prod_pk"].id}],
        ),
        CanonicalRelationshipModel(
            id=103 if not reverse_order else 203,
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=snapshots.id,
            relationship_type="many_to_one",
            join_condition="orders.sn_fk = snapshots.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": columns["sn_fk"].id, "to_column_id": columns["sn_pk"].id}],
        ),
        CanonicalRelationshipModel(
            id=104 if not reverse_order else 204,
            connection_id=db_id,
            from_entity_id=snapshots.id,
            to_entity_id=products.id,
            relationship_type="many_to_one",
            join_condition="snapshots.sn_prod_fk = products.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": columns["sn_prod_fk"].id, "to_column_id": columns["prod_pk"].id}],
        ),
    ]
    if reverse_order:
        rels = list(reversed(rels))
    db.add_all(rels)
    await db.commit()
    return orders.id, columns["prod_name"].id


@pytest.mark.asyncio
async def test_ambiguous_join_path_fails_closed_and_builds_no_sql(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids)
    query = SemanticQuerySpec(metric_ids=[metric_ids[0]], dimensions=[DimensionSelection(column_id=prod_name_id)])

    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_mock:
        with pytest.raises(SemanticCompileError) as error:
            await SemanticQueryCompiler(async_session).compile(db_id, query)
    assert error.value.code == "AMBIGUOUS_JOIN_PATH"
    assert error.value.context["base_entity_id"] == await _table_id(async_session, db_id, "orders")
    assert error.value.context["target_entity_id"] == await _table_id(async_session, db_id, "products")
    assert len(error.value.context["candidate_paths"]) == 2
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_join_path_is_order_independent(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids, reverse_order=False)
    query = SemanticQuerySpec(metric_ids=[metric_ids[0]], dimensions=[DimensionSelection(column_id=prod_name_id)])
    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_fwd:
        with pytest.raises(SemanticCompileError) as forward:
            await SemanticQueryCompiler(async_session).compile(db_id, query)
        # Re-compiling the same data must be deterministic.
        with pytest.raises(SemanticCompileError) as forward_again:
            await SemanticQueryCompiler(async_session).compile(db_id, query)
    assert forward.value.code == forward_again.value.code == "AMBIGUOUS_JOIN_PATH"
    assert forward.value.context["candidate_paths"] == forward_again.value.context["candidate_paths"]
    assert len(forward.value.context["candidate_paths"]) == 2
    build_fwd.assert_not_called()

    db2_id, db2_metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id2 = await _seed_ambiguous_schema(async_session, db2_id, db2_metric_ids, reverse_order=True)
    query2 = SemanticQuerySpec(metric_ids=[db2_metric_ids[0]], dimensions=[DimensionSelection(column_id=prod_name_id2)])
    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_rev:
        with pytest.raises(SemanticCompileError) as reverse:
            await SemanticQueryCompiler(async_session).compile(db2_id, query2)
    assert reverse.value.code == "AMBIGUOUS_JOIN_PATH"
    assert len(reverse.value.context["candidate_paths"]) == 2
    build_rev.assert_not_called()


@pytest.mark.asyncio
async def test_pending_relationship_cannot_produce_sql(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders = await _table(async_session, db_id, "orders")
    customers = SemanticTableModel(
        db_id=db_id, table_name="customers", business_name="Khách hàng", description="", primary_key_column="id"
    )
    async_session.add(customers)
    await async_session.flush()
    customer_id = SemanticColumnModel(
        table_id=orders.id, column_name="customer_id", data_type="INTEGER", business_name="Mã khách hàng"
    )
    customer_pk = SemanticColumnModel(
        table_id=customers.id, column_name="id", data_type="INTEGER", business_name="Mã khách hàng", is_primary_key=True
    )
    segment = SemanticColumnModel(
        table_id=customers.id, column_name="segment", data_type="TEXT", business_name="Phân khúc"
    )
    async_session.add_all([customer_id, customer_pk, segment])
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=customers.id,
            relationship_type="many_to_one",
            join_condition="orders.customer_id = customers.id",
            validation_status="valid",
            review_status=REVIEW_STATUS_PENDING,
            column_pairs=[{"from_column_id": customer_id.id, "to_column_id": customer_pk.id}],
        )
    )
    await async_session.commit()

    query = SemanticQuerySpec(
        metric_ids=[metric_ids[0]],
        filters=[SemanticQueryFilter(column_id=segment.id, operator="eq", value="enterprise")],
    )
    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_mock:
        with pytest.raises(SemanticCompileError) as error:
            await SemanticQueryCompiler(async_session).compile(db_id, query)
    assert error.value.code == "UNREACHABLE_DIMENSION"
    build_mock.assert_not_called()


async def _table_id(db: AsyncSession, db_id: int, name: str) -> int:
    return (await _table(db, db_id, name)).id


def _metric_with_preferred(
    db_id: int,
    table_id: int,
    amount_id: int,
    status_id: int,
    grain_id: int,
    preferred: dict[int, list[int]],
    name: str = "Revenue",
) -> SemanticMetricModel:
    definition = {
        "schema_version": 2,
        "metric": {
            "name": name,
            "formula": {
                "function": "SUM",
                "expression": "amount",
                "expression_ast": {"kind": "column", "column_id": amount_id},
            },
            "base_entity": "orders",
            "base_entity_id": table_id,
            "grain": {"column_ids": [grain_id]},
            "filters": [{"field": "status", "column_id": status_id, "operator": "eq", "value": "completed"}],
            "status": "approved",
            "confidence": "high",
            "excluded_notes": "",
            "preferred_join_paths": preferred,
        },
    }
    return SemanticMetricModel(
        db_id=db_id,
        created_by=1,
        name=name,
        description="",
        sql_template="",
        source="ai",
        status="approved",
        base_entity_id=table_id,
        formula="",
        aggregation_type="SUM",
        definition=definition,
    )


@pytest.mark.asyncio
async def test_preferred_join_path_controls_generated_joins(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders_id, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids)
    products_id = await _table_id(async_session, db_id, "products")
    metric = _metric_with_preferred(
        db_id, orders_id, metric_ids[0], metric_ids[0], metric_ids[0], {products_id: [101, 102]}
    )
    async_session.add(metric)
    await async_session.commit()

    compiled = await SemanticQueryCompiler(async_session).compile(
        db_id, SemanticQuerySpec(metric_ids=[metric.id], dimensions=[DimensionSelection(column_id=prod_name_id)])
    )
    assert compiled.metadata["relationship_ids"] == [101, 102]
    assert '"order_lines"' in compiled.sql
    assert '"products"' in compiled.sql


@pytest.mark.asyncio
async def test_missing_preferred_path_on_ambiguous_target_fails_closed(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids)
    orders_id = await _table_id(async_session, db_id, "orders")
    metric = _metric_with_preferred(db_id, orders_id, metric_ids[0], metric_ids[0], metric_ids[0], {})
    async_session.add(metric)
    await async_session.commit()

    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_mock:
        with pytest.raises(SemanticCompileError) as error:
            await SemanticQueryCompiler(async_session).compile(
                db_id,
                SemanticQuerySpec(metric_ids=[metric.id], dimensions=[DimensionSelection(column_id=prod_name_id)]),
            )
    assert error.value.code == "AMBIGUOUS_JOIN_PATH"
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_stale_preferred_path_is_invalid(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids)
    orders_id = await _table_id(async_session, db_id, "orders")
    products_id = await _table_id(async_session, db_id, "products")
    metric = _metric_with_preferred(db_id, orders_id, metric_ids[0], metric_ids[0], metric_ids[0], {products_id: [999]})
    async_session.add(metric)
    await async_session.commit()

    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_mock:
        with pytest.raises(SemanticCompileError) as error:
            await SemanticQueryCompiler(async_session).compile(
                db_id,
                SemanticQuerySpec(metric_ids=[metric.id], dimensions=[DimensionSelection(column_id=prod_name_id)]),
            )
    assert error.value.code == "INVALID_PREFERRED_JOIN_PATH"
    assert error.value.context["preferred_path"] == [999]
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_conflicting_preferred_paths_raise_conflict(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    _, prod_name_id = await _seed_ambiguous_schema(async_session, db_id, metric_ids)
    orders_id = await _table_id(async_session, db_id, "orders")
    products_id = await _table_id(async_session, db_id, "products")
    metric_a = _metric_with_preferred(
        db_id, orders_id, metric_ids[0], metric_ids[0], metric_ids[0], {products_id: [101, 102]}, name="A"
    )
    metric_b = _metric_with_preferred(
        db_id, orders_id, metric_ids[0], metric_ids[0], metric_ids[0], {products_id: [103, 104]}, name="B"
    )
    async_session.add_all([metric_a, metric_b])
    await async_session.commit()

    with patch("src.services.query_compiler.SemanticQueryCompiler._build_query", new=MagicMock()) as build_mock:
        with pytest.raises(SemanticCompileError) as error:
            await SemanticQueryCompiler(async_session).compile(
                db_id,
                SemanticQuerySpec(
                    metric_ids=[metric_a.id, metric_b.id],
                    dimensions=[DimensionSelection(column_id=prod_name_id)],
                ),
            )
    assert error.value.code == "CONFLICTING_JOIN_PATH"
    context = error.value.context
    assert context["base_entity_id"] == orders_id
    assert context["target_entity_id"] == products_id
    sequences = {tuple(c["relationship_ids"]) for c in context["conflicts"]}
    assert sequences == {(101, 102), (103, 104)}
    offending = {c["metric_id"] for c in context["conflicts"]}
    assert offending == {metric_a.id, metric_b.id}
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_unambiguous_metric_with_empty_preferred_still_compiles(async_session: AsyncSession) -> None:
    db_id, metric_ids = await _seed_filtered_metrics(async_session)
    orders = await _table(async_session, db_id, "orders")
    customers = SemanticTableModel(
        db_id=db_id, table_name="customers", business_name="Khách hàng", description="", primary_key_column="id"
    )
    async_session.add(customers)
    await async_session.flush()
    customer_id = SemanticColumnModel(
        table_id=orders.id, column_name="customer_id", data_type="INTEGER", business_name="Mã khách hàng"
    )
    customer_pk = SemanticColumnModel(
        table_id=customers.id, column_name="id", data_type="INTEGER", business_name="Mã khách hàng", is_primary_key=True
    )
    segment = SemanticColumnModel(
        table_id=customers.id, column_name="segment", data_type="TEXT", business_name="Phân khúc"
    )
    async_session.add_all([customer_id, customer_pk, segment])
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            connection_id=db_id,
            from_entity_id=orders.id,
            to_entity_id=customers.id,
            relationship_type="many_to_one",
            join_condition="orders.customer_id = customers.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[{"from_column_id": customer_id.id, "to_column_id": customer_pk.id}],
        )
    )
    await async_session.commit()

    metric = _metric_with_preferred(db_id, orders.id, metric_ids[0], metric_ids[0], metric_ids[0], {})
    async_session.add(metric)
    await async_session.commit()

    compiled = await SemanticQueryCompiler(async_session).compile(
        db_id, SemanticQuerySpec(metric_ids=[metric.id], dimensions=[DimensionSelection(column_id=segment.id)])
    )
    assert '"customers"' in compiled.sql
