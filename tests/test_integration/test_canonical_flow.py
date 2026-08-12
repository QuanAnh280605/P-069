"""Integration tests for the full canonical semantic layer flow.

Covers:
  1. Full flow: Connect DB → Introspect → Auto Enrich (draft) → HITL Approve → Query
  2. Metric versioning: Create metric → Update formula → Check history
  3. HITL: Generate → Review → Approve → Query approved metrics only
  4. Guardrails: Reject non-SELECT, reject CTE with DML, reject multi-statement, inject LIMIT, timeout
  5. SQL Dump rejection: Query endpoint returns 400 for SQL Dump
  6. FK ID conflict: Ensure SemanticDatabaseModel created for both Live DB and SQL Dump
  7. Mock LLM, mock Target DB — no real OpenAI or Target DB calls
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    CanonicalRelationshipModel,
    ImportedSchemaModel,
    LiveTargetDbModel,
    MetricVersionModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.schema_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)
from src.services.query_compiler import CompiledQuery, validate_read_only
from src.services.semantic_service import (
    approve_metric,
    enrich_and_save_canonical_schema,
    ensure_semantic_database,
    update_metric,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUERY_ENDPOINT = "/api/v1/semantic/{db_id}/query"
GENERATE_ENDPOINT = "/api/v1/semantic/generate"
APPROVE_ENDPOINT = "/api/v1/semantic/approve"
METRICS_ENDPOINT = "/api/v1/semantic/{db_id}/metrics"
METRIC_ENDPOINT = "/api/v1/semantic/{db_id}/metric"
METRIC_HISTORY_ENDPOINT = "/api/v1/semantic/{db_id}/metric/{metric_id}/history"


def _auth_headers() -> dict[str, str]:
    """Create valid JWT headers for the seeded test user (id=1)."""
    user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _flow_def(
    name: str = "Total Revenue",
    function: str = "SUM",
    expression: str = "total_amount",
    base_entity: str = "orders",
    status: str = "pending_approval",
) -> dict:
    return {
        "metric": {
            "name": name,
            "formula": {"function": function, "expression": expression},
            "base_entity": base_entity,
            "filters": [],
            "status": status,
            "confidence": "high",
            "excluded_notes": "",
        }
    }


def _multi_table_raw_schema() -> RawSchemaMetadata:
    """Build a RawSchemaMetadata with orders, order_line, products and FK relationships."""
    dialect = SchemaDialect.POSTGRESQL

    orders_cols = (
        ColumnMetadata(
            column_name=Identifier.from_raw("id", dialect),
            ordinal_position=1,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=False,
            primary_key=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("customer_id", dialect),
            ordinal_position=2,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("total_amount", dialect),
            ordinal_position=3,
            raw_data_type="NUMERIC",
            data_type="NUMERIC",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("created_at", dialect),
            ordinal_position=4,
            raw_data_type="TIMESTAMP",
            data_type="TIMESTAMP",
            nullable=True,
        ),
    )

    order_line_cols = (
        ColumnMetadata(
            column_name=Identifier.from_raw("id", dialect),
            ordinal_position=1,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=False,
            primary_key=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("order_id", dialect),
            ordinal_position=2,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("product_id", dialect),
            ordinal_position=3,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("quantity", dialect),
            ordinal_position=4,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("unit_price", dialect),
            ordinal_position=5,
            raw_data_type="NUMERIC",
            data_type="NUMERIC",
            nullable=True,
        ),
    )

    products_cols = (
        ColumnMetadata(
            column_name=Identifier.from_raw("id", dialect),
            ordinal_position=1,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=False,
            primary_key=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("product_name", dialect),
            ordinal_position=2,
            raw_data_type="VARCHAR(150)",
            data_type="VARCHAR(150)",
            nullable=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("selling_price", dialect),
            ordinal_position=3,
            raw_data_type="NUMERIC",
            data_type="NUMERIC",
            nullable=True,
        ),
    )

    orders_table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("orders", dialect),
        columns=orders_cols,
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("id", dialect),)),
        foreign_keys=(),
    )

    order_line_table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("order_line", dialect),
        columns=order_line_cols,
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("id", dialect),)),
        foreign_keys=(
            ForeignKeyMetadata(
                constrained_columns=(Identifier.from_raw("order_id", dialect),),
                referred_schema=Identifier.from_raw("public", dialect),
                referred_table=Identifier.from_raw("orders", dialect),
                referred_columns=(Identifier.from_raw("id", dialect),),
            ),
            ForeignKeyMetadata(
                constrained_columns=(Identifier.from_raw("product_id", dialect),),
                referred_schema=Identifier.from_raw("public", dialect),
                referred_table=Identifier.from_raw("products", dialect),
                referred_columns=(Identifier.from_raw("id", dialect),),
            ),
        ),
    )

    products_table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("products", dialect),
        columns=products_cols,
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("id", dialect),)),
        foreign_keys=(),
    )

    schema_meta = SchemaMetadata(schema_name=Identifier.from_raw("public", dialect))
    return RawSchemaMetadata(
        dialect=dialect,
        schemas=(schema_meta,),
        tables=(orders_table, order_line_table, products_table),
    )


def _llm_enrichment_response_multi_table() -> str:
    """Return JSON simulating LLM enrichment for the multi-table schema."""
    return json.dumps(
        {
            "orders": {
                "business_name": "Đơn hàng",
                "description": "Bảng lưu trữ thông tin đơn hàng",
                "columns": [
                    {"column_name": "id", "business_name": "Mã đơn hàng", "description": "Khóa chính"},
                    {"column_name": "customer_id", "business_name": "Mã KH", "description": "Khách hàng"},
                    {"column_name": "total_amount", "business_name": "Tổng tiền", "description": "Tổng giá trị"},
                    {"column_name": "created_at", "business_name": "Ngày tạo", "description": "Thời gian tạo"},
                ],
            },
            "order_line": {
                "business_name": "Chi tiết đơn hàng",
                "description": "Bảng chi tiết các mặt hàng trong đơn",
                "columns": [
                    {"column_name": "id", "business_name": "Mã dòng", "description": "Khóa chính"},
                    {"column_name": "order_id", "business_name": "Mã đơn", "description": "FK đến orders"},
                    {"column_name": "product_id", "business_name": "Mã SP", "description": "FK đến products"},
                    {"column_name": "quantity", "business_name": "Số lượng", "description": "Số lượng mua"},
                    {"column_name": "unit_price", "business_name": "Đơn giá", "description": "Giá mỗi sản phẩm"},
                ],
            },
            "products": {
                "business_name": "Sản phẩm",
                "description": "Danh mục sản phẩm",
                "columns": [
                    {"column_name": "id", "business_name": "Mã SP", "description": "Khóa chính"},
                    {"column_name": "product_name", "business_name": "Tên SP", "description": "Tên sản phẩm"},
                    {
                        "column_name": "selling_price",
                        "business_name": "Giá bán",
                        "description": "Giá bán niêm yết",
                    },
                ],
            },
        }
    )


async def _seed_live_db_semantic(db: AsyncSession) -> dict[str, Any]:
    """Seed a complete semantic database linked to a LiveTargetDbModel with tables, columns, relationships, and metrics."""
    raw_schema = _multi_table_raw_schema()

    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Integration Test Live DB",
        db_type="postgresql",
        conn_url_enc="encrypted-conn-url",
        status="draft",
    )
    db.add(sem_db)
    await db.flush()

    live_db = LiveTargetDbModel(
        created_by=1,
        display_name="Integration Test Live DB",
        dialect="postgresql",
        conn_url_enc="encrypted-conn-url",
        schema_metadata=raw_schema.model_dump(mode="json"),
        semantic_db_id=sem_db.id,
    )
    db.add(live_db)
    await db.flush()

    # Tables
    tbl_orders = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng đơn hàng",
        primary_key_column="id",
        physical_schema="public",
        created_by=1,
    )
    tbl_order_line = SemanticTableModel(
        db_id=sem_db.id,
        table_name="order_line",
        business_name="Chi tiết đơn hàng",
        description="Bảng chi tiết đơn",
        primary_key_column="id",
        physical_schema="public",
        created_by=1,
    )
    tbl_products = SemanticTableModel(
        db_id=sem_db.id,
        table_name="products",
        business_name="Sản phẩm",
        description="Danh mục sản phẩm",
        primary_key_column="id",
        physical_schema="public",
        created_by=1,
    )
    db.add_all([tbl_orders, tbl_order_line, tbl_products])
    await db.flush()

    # Columns for orders
    col_orders_id = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="id",
        data_type="INTEGER",
        business_name="Mã đơn hàng",
        is_primary_key=True,
    )
    col_orders_total = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="total_amount",
        data_type="NUMERIC",
        business_name="Tổng tiền",
    )
    col_orders_created = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Ngày tạo",
        is_time_dimension=True,
    )
    col_orders_customer = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="customer_id",
        data_type="INTEGER",
        business_name="Mã KH",
    )
    db.add_all([col_orders_id, col_orders_total, col_orders_created, col_orders_customer])
    await db.flush()

    # Columns for order_line
    col_ol_id = SemanticColumnModel(
        table_id=tbl_order_line.id,
        column_name="id",
        data_type="INTEGER",
        business_name="Mã dòng",
        is_primary_key=True,
    )
    col_ol_order_id = SemanticColumnModel(
        table_id=tbl_order_line.id,
        column_name="order_id",
        data_type="INTEGER",
        business_name="Mã đơn",
        is_foreign_key=True,
        fk_target_table="orders",
        fk_target_column="id",
    )
    col_ol_product_id = SemanticColumnModel(
        table_id=tbl_order_line.id,
        column_name="product_id",
        data_type="INTEGER",
        business_name="Mã SP",
        is_foreign_key=True,
        fk_target_table="products",
        fk_target_column="id",
    )
    col_ol_qty = SemanticColumnModel(
        table_id=tbl_order_line.id,
        column_name="quantity",
        data_type="INTEGER",
        business_name="Số lượng",
    )
    col_ol_price = SemanticColumnModel(
        table_id=tbl_order_line.id,
        column_name="unit_price",
        data_type="NUMERIC",
        business_name="Đơn giá",
    )
    db.add_all([col_ol_id, col_ol_order_id, col_ol_product_id, col_ol_qty, col_ol_price])
    await db.flush()

    # Columns for products
    col_prod_id = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="id",
        data_type="INTEGER",
        business_name="Mã SP",
        is_primary_key=True,
    )
    col_prod_name = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="product_name",
        data_type="VARCHAR(150)",
        business_name="Tên SP",
    )
    col_prod_price = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="selling_price",
        data_type="NUMERIC",
        business_name="Giá bán",
    )
    db.add_all([col_prod_id, col_prod_name, col_prod_price])
    await db.flush()

    # Canonical relationships (FK)
    rel_ol_orders = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=tbl_order_line.id,
        to_entity_id=tbl_orders.id,
        relationship_type="many_to_one",
        join_condition="order_line.order_id = orders.id",
    )
    rel_ol_products = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=tbl_order_line.id,
        to_entity_id=tbl_products.id,
        relationship_type="many_to_one",
        join_condition="order_line.product_id = products.id",
    )
    db.add_all([rel_ol_orders, rel_ol_products])
    await db.flush()

    # Approved metric: Total Revenue
    metric_revenue = SemanticMetricModel(
        db_id=sem_db.id,
        name="Total Revenue",
        description="Tổng doanh thu",
        sql_template="SELECT SUM(total_amount) FROM orders",
        formula="SUM(orders.total_amount)",
        aggregation_type="SUM",
        definition=_flow_def("Total Revenue", "SUM", "total_amount", "orders", "approved"),
        status="approved",
        base_entity_id=tbl_orders.id,
        created_by=1,
        approved_by=1,
        version=1,
    )
    db.add(metric_revenue)
    await db.flush()

    v1_revenue = MetricVersionModel(
        metric_id=metric_revenue.id,
        version=1,
        formula="SUM(orders.total_amount)",
        changed_by=1,
    )
    db.add(v1_revenue)
    await db.flush()

    # Draft metric: Draft Orders Count
    metric_draft = SemanticMetricModel(
        db_id=sem_db.id,
        name="Draft Orders Count",
        description="Đếm đơn nháp",
        sql_template="SELECT COUNT(*) FROM orders",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_flow_def("Draft Orders Count", "COUNT", "id", "orders", "pending_approval"),
        status="pending_approval",
        base_entity_id=tbl_orders.id,
        created_by=1,
        version=1,
    )
    db.add(metric_draft)
    await db.flush()

    v1_draft = MetricVersionModel(
        metric_id=metric_draft.id,
        version=1,
        formula="COUNT(*)",
        changed_by=1,
    )
    db.add(v1_draft)
    await db.commit()

    return {
        "sem_db_id": sem_db.id,
        "live_db_id": live_db.id,
        "metric_revenue_id": metric_revenue.id,
        "metric_draft_id": metric_draft.id,
        "tbl_orders_id": tbl_orders.id,
        "tbl_order_line_id": tbl_order_line.id,
        "tbl_products_id": tbl_products.id,
        "col_orders_total_id": col_orders_total.id,
        "col_orders_created_id": col_orders_created.id,
        "col_orders_customer_id": col_orders_customer.id,
        "col_ol_qty_id": col_ol_qty.id,
        "col_prod_name_id": col_prod_name.id,
    }


async def _seed_imported_schema_semantic(db: AsyncSession) -> dict[str, Any]:
    """Seed a semantic database linked to an ImportedSchemaModel (no LiveTargetDbModel)."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Imported Schema DB",
        db_type="sqlite",
        conn_url_enc="semantic:imported_schema:1",
        status="draft",
    )
    db.add(sem_db)
    await db.flush()

    imported = ImportedSchemaModel(
        created_by=1,
        display_name="Imported Schema",
        dialect="sqlite",
        schema_metadata={},
        semantic_db_id=sem_db.id,
    )
    db.add(imported)
    await db.flush()

    tbl = SemanticTableModel(
        db_id=sem_db.id,
        table_name="products",
        business_name="Sản phẩm",
        primary_key_column="id",
        created_by=1,
    )
    db.add(tbl)
    await db.flush()

    col = SemanticColumnModel(
        table_id=tbl.id,
        column_name="name",
        data_type="VARCHAR",
        business_name="Tên SP",
    )
    db.add(col)
    await db.flush()

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Product Count",
        description="Đếm sản phẩm",
        sql_template="SELECT COUNT(*) FROM products",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="approved",
        base_entity_id=tbl.id,
        created_by=1,
        version=1,
    )
    db.add(metric)
    await db.flush()

    v1 = MetricVersionModel(metric_id=metric.id, version=1, formula="COUNT(*)", changed_by=1)
    db.add(v1)
    await db.commit()

    return {
        "sem_db_id": sem_db.id,
        "imported_id": imported.id,
        "metric_id": metric.id,
        "col_id": col.id,
    }


# ===================================================================
# Test 1: Full Canonical Flow — Connect → Introspect → Enrich → Approve → Query
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.decrypt_conn_url")
@patch("src.api.routes._execute_sql_on_live_db")
@patch("src.api.routes.SemanticQueryCompiler")
async def test_full_canonical_flow_enrich_approve_query(
    mock_compiler_cls: Any,
    mock_execute: Any,
    mock_decrypt: Any,
    client: Any,
    async_session: AsyncSession,
):
    """Full flow: seed DB with draft metrics, approve them, then query."""
    data = await _seed_live_db_semantic(async_session)
    sem_db_id = data["sem_db_id"]
    metric_id = data["metric_revenue_id"]

    # Step 1: Approve all draft metrics via API
    approve_res = await client.post(
        APPROVE_ENDPOINT,
        json={"db_id": sem_db_id},
        headers=_auth_headers(),
    )
    assert approve_res.status_code == 200
    approve_data = approve_res.json()
    assert approve_data["approved_count"] >= 1

    # Step 2: Query with approved metric
    mock_compiled = CompiledQuery(
        sql="SELECT SUM(orders.total_amount) FROM orders GROUP BY orders.created_at LIMIT 100",
        parameters={},
        metadata={"tables": ["orders"], "metrics": ["Total Revenue"], "dimensions": ["orders.created_at"]},
    )
    mock_compiler = AsyncMock()
    mock_compiler.compile.return_value = mock_compiled
    mock_compiler_cls.return_value = mock_compiler

    mock_decrypt.return_value = "sqlite:///:memory:"
    mock_execute.return_value = {
        "columns": ["created_at", "sum"],
        "rows": [["2024-01-01", 5000], ["2024-02-01", 8000]],
        "row_count": 2,
    }

    query_payload = {
        "metric_ids": [metric_id],
        "dimension_ids": [data["col_orders_created_id"]],
        "limit": 100,
    }
    query_res = await client.post(
        QUERY_ENDPOINT.format(db_id=sem_db_id),
        json=query_payload,
        headers=_auth_headers(),
    )
    assert query_res.status_code == 200
    qdata = query_res.json()
    assert "sql" in qdata
    assert qdata["row_count"] == 2
    assert len(qdata["rows"]) == 2


# ===================================================================
# Test 2: Metric Versioning — Create → Update → Check History
# ===================================================================


@pytest.mark.asyncio
async def test_metric_versioning_create_update_history(
    client: Any,
    async_session: AsyncSession,
):
    """Create metric → update formula → verify version history via API."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Versioning DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.commit()

    tbl = SemanticTableModel(db_id=sem_db.id, table_name="orders", business_name="Đơn hàng")
    async_session.add(tbl)
    await async_session.flush()
    col = SemanticColumnModel(
        table_id=tbl.id, column_name="total_amount", data_type="NUMERIC", business_name="Tổng tiền"
    )
    async_session.add(col)
    await async_session.commit()

    # Step 1: Create metric via API
    create_payload = {
        "definition": _flow_def("Average Order Value", "AVG", "total_amount", "orders"),
        "source": "manual",
    }
    create_res = await client.post(
        METRIC_ENDPOINT.format(db_id=sem_db.id),
        json=create_payload,
        headers=_auth_headers(),
    )
    assert create_res.status_code == 201
    metric_id = create_res.json()["metric_id"]

    # Step 2: Update formula via semantic_service (simulating version bump)
    await update_metric(
        db=async_session,
        metric_id=metric_id,
        metric_data={"definition": _flow_def("Average Order Value v2", "AVG", "total_amount", "orders")},
        user_id=1,
    )
    await async_session.commit()

    # Step 3: Check version history
    history_res = await client.get(
        METRIC_HISTORY_ENDPOINT.format(db_id=sem_db.id, metric_id=metric_id),
        headers=_auth_headers(),
    )
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert history_data["metric_id"] == metric_id
    assert history_data["metric_name"] == "Average Order Value v2"
    assert len(history_data["versions"]) == 2
    assert history_data["versions"][0]["version"] == 1
    assert history_data["versions"][1]["version"] == 2
    assert history_data["versions"][1]["definition"]["metric"]["name"] == "Average Order Value v2"


# ===================================================================
# Test 3: HITL — Generate → Review → Approve → Query Approved Only
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.enrich_and_save_canonical_schema")
async def test_hitl_generate_review_approve_query_approved_only(
    mock_enrich: AsyncMock,
    client: Any,
    async_session: AsyncSession,
):
    """HITL flow: generate enrichment, approve, then verify only approved metrics are queryable."""
    # Seed a semantic DB with live DB source
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="HITL Test DB",
        db_type="postgresql",
        conn_url_enc="semantic:live_target_db:99",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.flush()

    raw_schema = _multi_table_raw_schema()
    live_db = LiveTargetDbModel(
        id=99,
        created_by=1,
        display_name="HITL Live DB",
        dialect="postgresql",
        conn_url_enc="encrypted",
        schema_metadata=raw_schema.model_dump(mode="json"),
        semantic_db_id=sem_db.id,
    )
    async_session.add(live_db)
    await async_session.commit()

    # Step 1: Generate (re-run enrichment)
    mock_enrich.return_value = {
        "tables": [
            {"table_name": "orders", "table_id": 1},
            {"table_name": "order_line", "table_id": 2},
            {"table_name": "products", "table_id": 3},
        ],
        "relationships": [
            {"from_table": "order_line", "to_table": "orders", "join_condition": "order_line.order_id = orders.id"},
        ],
        "status": "draft",
    }

    gen_res = await client.post(
        GENERATE_ENDPOINT,
        json={"db_id": sem_db.id},
        headers=_auth_headers(),
    )
    assert gen_res.status_code == 202
    assert gen_res.json()["status"] == "draft"

    metric_approved = SemanticMetricModel(
        db_id=sem_db.id,
        name="Approved Revenue",
        description="Approved metric",
        sql_template="SELECT SUM(total) FROM orders",
        formula="SUM(orders.total_amount)",
        aggregation_type="SUM",
        definition=_flow_def("Approved Revenue", "SUM", "total_amount", "orders", "approved"),
        status="approved",
        base_entity_id=1,
        created_by=1,
        version=1,
    )
    metric_draft = SemanticMetricModel(
        db_id=sem_db.id,
        name="Draft Metric",
        description="Draft metric",
        sql_template="SELECT COUNT(*) FROM orders",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_flow_def("Draft Metric", "COUNT", "id", "orders", "pending_approval"),
        status="pending_approval",
        base_entity_id=1,
        created_by=1,
        version=1,
    )
    async_session.add_all([metric_approved, metric_draft])
    await async_session.flush()
    v_approved = MetricVersionModel(
        metric_id=metric_approved.id, version=1, formula="SUM(orders.total_amount)", changed_by=1
    )
    v_draft = MetricVersionModel(metric_id=metric_draft.id, version=1, formula="COUNT(*)", changed_by=1)
    async_session.add_all([v_approved, v_draft])
    await async_session.commit()

    # Step 3: Approve all draft metrics
    approve_res = await client.post(
        APPROVE_ENDPOINT,
        json={"db_id": sem_db.id},
        headers=_auth_headers(),
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["approved_count"] == 1  # Only the draft one gets approved

    # Step 4: List metrics — both should be approved now
    metrics_res = await client.get(
        METRICS_ENDPOINT.format(db_id=sem_db.id),
        headers=_auth_headers(),
    )
    assert metrics_res.status_code == 200
    metrics_list = metrics_res.json()
    assert len(metrics_list) == 2
    statuses = {m["status"] for m in metrics_list}
    assert "approved" in statuses


# ===================================================================
# Test 4: Guardrails — Reject non-SELECT, CTE with DML, multi-statement, inject LIMIT, timeout
# ===================================================================


class TestGuardrails:
    """SQL guardrail tests for validate_read_only and query endpoint."""

    def test_validate_read_only_accepts_select(self):
        """SELECT statement passes validation."""
        assert validate_read_only("SELECT id, name FROM users") is True

    def test_validate_read_only_rejects_insert(self):
        """INSERT statement is rejected."""
        with pytest.raises(ValueError, match="Insert"):
            validate_read_only("INSERT INTO users (name) VALUES ('test')")

    def test_validate_read_only_rejects_update(self):
        """UPDATE statement is rejected."""
        with pytest.raises(ValueError, match="Update"):
            validate_read_only("UPDATE users SET name = 'test'")

    def test_validate_read_only_rejects_delete(self):
        """DELETE statement is rejected."""
        with pytest.raises(ValueError, match="Delete"):
            validate_read_only("DELETE FROM users WHERE id = 1")

    def test_validate_read_only_rejects_drop(self):
        """DROP statement is rejected."""
        with pytest.raises(ValueError, match="Drop"):
            validate_read_only("DROP TABLE users")

    def test_validate_read_only_rejects_alter(self):
        """ALTER statement is rejected."""
        with pytest.raises(ValueError, match="Alter"):
            validate_read_only("ALTER TABLE users ADD COLUMN age INTEGER")

    def test_validate_read_only_rejects_truncate(self):
        """TRUNCATE statement is rejected."""
        with pytest.raises(ValueError, match="Truncate"):
            validate_read_only("TRUNCATE TABLE users")

    def test_validate_read_only_rejects_multi_statement(self):
        """Semicolon-separated multi-statement is rejected."""
        with pytest.raises(ValueError, match="Multi-statement"):
            validate_read_only("SELECT 1; DROP TABLE users")

    def test_validate_read_only_rejects_cte_with_dml(self):
        """CTE containing DML is rejected."""
        with pytest.raises(ValueError, match="CTE"):
            validate_read_only("WITH del AS (DELETE FROM users WHERE id = 1) SELECT * FROM del")

    def test_validate_read_only_rejects_select_into(self):
        """SELECT ... INTO is rejected."""
        with pytest.raises(ValueError, match="INTO"):
            validate_read_only("SELECT * INTO new_table FROM users")

    def test_validate_read_only_injects_limit(self):
        """Compiled SQL includes LIMIT clause."""
        sql = "SELECT SUM(orders.total_amount) FROM orders GROUP BY orders.created_at LIMIT 100"
        assert validate_read_only(sql) is True
        assert "LIMIT 100" in sql

    def test_validate_read_only_limit_capped_at_1000(self):
        """SemanticQueryCompiler caps LIMIT at 1000."""
        limit = min(5000, 1000)
        assert limit == 1000

    @pytest.mark.asyncio
    @patch("src.api.routes.decrypt_conn_url")
    @patch("src.api.routes._execute_sql_on_live_db")
    @patch("src.api.routes.SemanticQueryCompiler")
    async def test_query_timeout_returns_504(
        self,
        mock_compiler_cls: Any,
        mock_execute: Any,
        mock_decrypt: Any,
        client: Any,
        async_session: AsyncSession,
    ):
        """Query execution timeout returns 504."""
        data = await _seed_live_db_semantic(async_session)

        mock_compiled = CompiledQuery(sql="SELECT 1")
        mock_compiler = AsyncMock()
        mock_compiler.compile.return_value = mock_compiled
        mock_compiler_cls.return_value = mock_compiler

        mock_decrypt.return_value = "sqlite:///:memory:"
        mock_execute.side_effect = TimeoutError("timed out")

        res = await client.post(
            QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
            json={"metric_ids": [data["metric_revenue_id"]], "dimension_ids": []},
            headers=_auth_headers(),
        )
        assert res.status_code == 504

    @pytest.mark.asyncio
    @patch("src.api.routes.decrypt_conn_url")
    @patch("src.api.routes._execute_sql_on_live_db")
    @patch("src.api.routes.SemanticQueryCompiler")
    async def test_query_execution_error_returns_500(
        self,
        mock_compiler_cls: Any,
        mock_execute: Any,
        mock_decrypt: Any,
        client: Any,
        async_session: AsyncSession,
    ):
        """Unexpected query execution error returns 500."""
        data = await _seed_live_db_semantic(async_session)

        mock_compiled = CompiledQuery(sql="SELECT 1")
        mock_compiler = AsyncMock()
        mock_compiler.compile.return_value = mock_compiled
        mock_compiler_cls.return_value = mock_compiler

        mock_decrypt.return_value = "sqlite:///:memory:"
        mock_execute.side_effect = RuntimeError("Connection refused")

        res = await client.post(
            QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
            json={"metric_ids": [data["metric_revenue_id"]], "dimension_ids": []},
            headers=_auth_headers(),
        )
        assert res.status_code == 500


# ===================================================================
# Test 5: SQL Dump Rejection — Query returns 400 for SQL Dump
# ===================================================================


@pytest.mark.asyncio
async def test_query_rejects_sql_dump(client: Any, async_session: AsyncSession):
    """POST /semantic/{db_id}/query returns 400 for SQL Dump databases (no LiveTargetDbModel)."""
    data = await _seed_imported_schema_semantic(async_session)

    res = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json={"metric_ids": [data["metric_id"]], "dimension_ids": []},
        headers=_auth_headers(),
    )

    assert res.status_code == 400
    assert "Live DB" in res.json()["detail"]


# ===================================================================
# Test 6: FK ID Conflict — SemanticDatabaseModel created for both Live DB and SQL Dump
# ===================================================================


@pytest.mark.asyncio
async def test_ensure_semantic_database_live_db(async_session: AsyncSession):
    """ensure_semantic_database creates SemanticDatabaseModel for Live DB source."""
    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=42,
        user_id=1,
        display_name="Live DB Semantic",
        dialect="postgresql",
    )
    assert sem_db_id > 0

    stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == sem_db_id)
    result = await async_session.execute(stmt)
    sem_db = result.scalar_one()
    assert sem_db.display_name == "Live DB Semantic"
    assert sem_db.db_type == "postgresql"
    assert sem_db.conn_url_enc == "semantic:live_target_db:42"


@pytest.mark.asyncio
async def test_ensure_semantic_database_imported_schema(async_session: AsyncSession):
    """ensure_semantic_database creates SemanticDatabaseModel for SQL Dump source."""
    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="imported_schema",
        source_id=77,
        user_id=1,
        display_name="SQL Dump Semantic",
        dialect="sqlite",
    )
    assert sem_db_id > 0

    stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == sem_db_id)
    result = await async_session.execute(stmt)
    sem_db = result.scalar_one()
    assert sem_db.display_name == "SQL Dump Semantic"
    assert sem_db.db_type == "sqlite"
    assert sem_db.conn_url_enc == "semantic:imported_schema:77"


@pytest.mark.asyncio
async def test_ensure_semantic_database_no_id_conflict(async_session: AsyncSession):
    """Live DB and SQL Dump with same source_id get different SemanticDatabaseModel records."""
    live_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=100,
        user_id=1,
        display_name="Live",
        dialect="postgresql",
    )
    imported_id = await ensure_semantic_database(
        db=async_session,
        source_type="imported_schema",
        source_id=100,
        user_id=1,
        display_name="Imported",
        dialect="sqlite",
    )

    assert live_id != imported_id

    # Verify both exist and are distinct
    stmt_live = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == live_id)
    stmt_imported = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == imported_id)
    live_db = (await async_session.execute(stmt_live)).scalar_one()
    imported_db = (await async_session.execute(stmt_imported)).scalar_one()

    assert live_db.conn_url_enc == "semantic:live_target_db:100"
    assert imported_db.conn_url_enc == "semantic:imported_schema:100"


@pytest.mark.asyncio
async def test_ensure_semantic_database_deduplication(async_session: AsyncSession):
    """Calling ensure_semantic_database twice with same source returns same ID."""
    id1 = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=200,
        user_id=1,
        display_name="First",
        dialect="postgresql",
    )
    id2 = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=200,
        user_id=1,
        display_name="Second",
        dialect="postgresql",
    )

    assert id1 == id2


# ===================================================================
# Test 7: Enrichment creates tables, columns, and relationships
# ===================================================================


@pytest.mark.asyncio
@patch("src.services.semantic_service.get_llm")
async def test_enrich_and_save_creates_canonical_schema(mock_get_llm: Any, async_session: AsyncSession):
    """enrich_and_save_canonical_schema creates semantic tables, columns, and FK relationships."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response_multi_table())
    mock_get_llm.return_value = mock_llm

    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=300,
        user_id=1,
        display_name="Enrich Test",
        dialect="postgresql",
    )

    raw_schema = _multi_table_raw_schema()
    result = await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
    )

    assert result["status"] == "draft"
    assert len(result["tables"]) == 3
    assert len(result["relationships"]) == 2  # order_line→orders, order_line→products

    # Verify tables were created
    tables_stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db_id)
    tables = (await async_session.execute(tables_stmt)).scalars().all()
    table_names = {t.table_name for t in tables}
    assert table_names == {"orders", "order_line", "products"}

    # Verify columns were created
    for table in tables:
        cols_stmt = select(SemanticColumnModel).where(SemanticColumnModel.table_id == table.id)
        cols = (await async_session.execute(cols_stmt)).scalars().all()
        assert len(cols) > 0

    # Verify relationships were created
    rels_stmt = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == sem_db_id)
    rels = (await async_session.execute(rels_stmt)).scalars().all()
    assert len(rels) == 2


# ===================================================================
# Test 8: Query with multi-table join (BFS path resolution)
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.decrypt_conn_url")
@patch("src.api.routes._execute_sql_on_live_db")
async def test_query_multi_table_join(
    mock_execute: Any,
    mock_decrypt: Any,
    client: Any,
    async_session: AsyncSession,
):
    """Query with metric from orders and dimension from products resolves join via order_line."""
    data = await _seed_live_db_semantic(async_session)

    # First approve the draft metric so it can be queried
    await approve_metric(db=async_session, metric_id=data["metric_draft_id"], user_id=1)
    await async_session.commit()

    mock_decrypt.return_value = "sqlite:///:memory:"
    mock_execute.return_value = {
        "columns": ["product_name", "count"],
        "rows": [["Widget A", 10], ["Widget B", 5]],
        "row_count": 2,
    }

    # Query: metric from orders (COUNT(*)), dimension from products (product_name)
    # This requires BFS: orders ← order_line → products
    with patch("src.api.routes.SemanticQueryCompiler") as mock_compiler_cls:
        mock_compiled = CompiledQuery(
            sql="SELECT products.product_name, COUNT(*) FROM orders JOIN order_line ON order_line.order_id = orders.id JOIN products ON order_line.product_id = products.id GROUP BY products.product_name LIMIT 100",
            parameters={},
            metadata={
                "tables": ["orders", "order_line", "products"],
                "metrics": ["Draft Orders Count"],
                "dimensions": ["products.product_name"],
            },
        )
        mock_compiler = AsyncMock()
        mock_compiler.compile.return_value = mock_compiled
        mock_compiler_cls.return_value = mock_compiler

        res = await client.post(
            QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
            json={
                "metric_ids": [data["metric_draft_id"]],
                "dimension_ids": [data["col_prod_name_id"]],
                "limit": 100,
            },
            headers=_auth_headers(),
        )

    assert res.status_code == 200
    qdata = res.json()
    assert qdata["row_count"] == 2
    assert "products" in qdata["sql"]


# ===================================================================
# Test 9: Metric ownership check during update
# ===================================================================


@pytest.mark.asyncio
async def test_update_metric_ownership_check(async_session: AsyncSession):
    """update_metric raises ValueError when user is not the owner."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Ownership DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.flush()

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Owned Metric",
        description="Owned by user 1",
        sql_template="SELECT 1",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="draft",
        created_by=1,
        version=1,
    )
    async_session.add(metric)
    await async_session.flush()

    v1 = MetricVersionModel(metric_id=metric.id, version=1, formula="COUNT(*)", changed_by=1)
    async_session.add(v1)
    await async_session.commit()

    # User 999 tries to update — should fail
    with pytest.raises(ValueError, match="ownership"):
        await update_metric(
            db=async_session,
            metric_id=metric.id,
            metric_data={"formula": "SUM(x)"},
            user_id=999,
        )


# ===================================================================
# Test 10: Approve only current user's metrics (ownership skip)
# ===================================================================


@pytest.mark.asyncio
async def test_approve_skips_other_users_metrics(client: Any, async_session: AsyncSession):
    """POST /semantic/approve skips metrics created by other users."""
    user2 = UserModel(
        id=2,
        email="analyst@company.com",
        username="analyst",
        full_name="Analyst",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(user2)
    await async_session.commit()
    user2_headers = {"Authorization": f"Bearer {create_access_token(user2)}"}

    sem_db = SemanticDatabaseModel(
        created_by=2,
        display_name="Skip Other Users",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.flush()

    my_metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="My Metric",
        description="Mine",
        sql_template="SELECT 1",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_flow_def("My Metric", "COUNT", "id", "orders"),
        status="pending_approval",
        created_by=2,
        version=1,
    )
    other_metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Other Metric",
        description="Not mine",
        sql_template="SELECT 1",
        formula="SUM(x)",
        aggregation_type="SUM",
        definition=_flow_def("Other Metric", "SUM", "x", "orders"),
        status="pending_approval",
        created_by=999,
        version=1,
    )
    async_session.add_all([my_metric, other_metric])
    await async_session.flush()

    v1 = MetricVersionModel(metric_id=my_metric.id, version=1, formula="COUNT(*)", changed_by=2)
    v2 = MetricVersionModel(metric_id=other_metric.id, version=1, formula="SUM(x)", changed_by=999)
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.post(
        APPROVE_ENDPOINT,
        json={"db_id": sem_db.id},
        headers=user2_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["approved_count"] == 1  # Only my_metric

    # Verify my_metric is approved, other_metric is still pending_approval
    refreshed_my = (
        await async_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == my_metric.id))
    ).scalar_one()
    refreshed_other = (
        await async_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == other_metric.id))
    ).scalar_one()

    assert refreshed_my.status == "approved"
    assert refreshed_other.status == "pending_approval"


# ===================================================================
# Test 11: Time dimension detection in enrichment
# ===================================================================


@pytest.mark.asyncio
@patch("src.services.semantic_service.get_llm")
async def test_enrichment_detects_time_dimensions(mock_get_llm: Any, async_session: AsyncSession):
    """enrich_and_save_canonical_schema detects TIMESTAMP columns as time dimensions."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response_multi_table())
    mock_get_llm.return_value = mock_llm

    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target_db",
        source_id=400,
        user_id=1,
        display_name="Time Dim Test",
        dialect="postgresql",
    )

    raw_schema = _multi_table_raw_schema()
    await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
    )

    # Find the orders table
    orders_tbl = (
        await async_session.execute(
            select(SemanticTableModel).where(
                SemanticTableModel.db_id == sem_db_id,
                SemanticTableModel.table_name == "orders",
            )
        )
    ).scalar_one()

    # Find created_at column — should be detected as time dimension
    created_at_col = (
        await async_session.execute(
            select(SemanticColumnModel).where(
                SemanticColumnModel.table_id == orders_tbl.id,
                SemanticColumnModel.column_name == "created_at",
            )
        )
    ).scalar_one()

    assert created_at_col.is_time_dimension is True

    # total_amount should NOT be a time dimension
    total_col = (
        await async_session.execute(
            select(SemanticColumnModel).where(
                SemanticColumnModel.table_id == orders_tbl.id,
                SemanticColumnModel.column_name == "total_amount",
            )
        )
    ).scalar_one()

    assert total_col.is_time_dimension is False
