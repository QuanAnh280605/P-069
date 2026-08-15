"""Behavior tests for the canonical semantic query compiler interface."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
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
