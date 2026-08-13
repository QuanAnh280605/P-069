"""Tests for canonical semantic layer endpoints: generate, approve, metrics list, metric history."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
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
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)


@pytest.fixture
def auth_headers():
    """Create a valid JWT header for the seeded test user (id=1)."""
    user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def _seed_semantic_db(async_session: AsyncSession, db_id: int = 100) -> SemanticDatabaseModel:
    """Seed a semantic database with tables and columns for testing."""
    sem_db = SemanticDatabaseModel(
        id=db_id,
        created_by=1,
        display_name="Test DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    table = SemanticTableModel(
        id=db_id,
        db_id=db_id,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng đơn hàng",
    )
    col = SemanticColumnModel(
        id=db_id,
        table_id=db_id,
        column_name="total_amount",
        data_type="NUMERIC",
        business_name="Tổng tiền",
        description="Tổng giá trị",
    )
    async_session.add_all([sem_db, table, col])
    return sem_db


def _raw_schema_metadata() -> RawSchemaMetadata:
    """Build a minimal RawSchemaMetadata for testing."""
    dialect = SchemaDialect.POSTGRESQL
    cols = (
        ColumnMetadata(
            column_name=Identifier.from_raw("id", dialect),
            ordinal_position=1,
            raw_data_type="INTEGER",
            data_type="INTEGER",
            nullable=False,
            primary_key=True,
        ),
        ColumnMetadata(
            column_name=Identifier.from_raw("total_amount", dialect),
            ordinal_position=2,
            raw_data_type="NUMERIC",
            data_type="NUMERIC",
            nullable=True,
            primary_key=False,
        ),
    )
    table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("orders", dialect),
        columns=cols,
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("id", dialect),)),
    )
    schema_meta = SchemaMetadata(schema_name=Identifier.from_raw("public", dialect))
    return RawSchemaMetadata(dialect=dialect, schemas=(schema_meta,), tables=(table,))


def _llm_enrichment_response() -> str:
    """Return a valid JSON string simulating LLM enrichment output."""
    return json.dumps(
        {
            "orders": {
                "business_name": "Đơn hàng",
                "description": "Bảng lưu trữ thông tin đơn hàng",
                "columns": [
                    {"column_name": "id", "business_name": "Mã đơn hàng", "description": "Khóa chính"},
                    {"column_name": "total_amount", "business_name": "Tổng tiền", "description": "Tổng giá trị"},
                ],
            },
        }
    )


# ---------------------------------------------------------------------------
# POST /semantic/generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_semantic_layer_not_found(client: AsyncClient, auth_headers: dict):
    """POST /semantic/generate returns 404 for non-existent semantic database."""
    res = await client.post("/api/v1/semantic/generate", json={"db_id": 9999}, headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_generate_semantic_layer_no_source(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """POST /semantic/generate returns 404 when no source (live DB/imported schema) is linked."""
    sem_db = SemanticDatabaseModel(
        id=200,
        created_by=1,
        display_name="Orphan DB",
        db_type="postgresql",
        conn_url_enc="semantic:live_target_db:999",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.commit()

    res = await client.post("/api/v1/semantic/generate", json={"db_id": 200}, headers=auth_headers)
    assert res.status_code == 404
    assert "No source" in res.json()["detail"]


@pytest.mark.asyncio
@patch("src.api.routes.enrich_and_save_canonical_schema")
async def test_generate_semantic_layer_from_live_db(
    mock_enrich: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict,
):
    """POST /semantic/generate re-runs enrichment from live DB source."""
    sem_db = SemanticDatabaseModel(
        id=201,
        created_by=1,
        display_name="Live DB",
        db_type="postgresql",
        conn_url_enc="semantic:live_target_db:50",
        status="draft",
    )
    live_db = LiveTargetDbModel(
        id=50,
        created_by=1,
        display_name="Live DB",
        dialect="postgresql",
        conn_url_enc="encrypted_url",
        semantic_db_id=201,
        schema_metadata=_raw_schema_metadata().model_dump(mode="json"),
    )
    async_session.add_all([sem_db, live_db])
    await async_session.commit()

    mock_enrich.return_value = {
        "tables": [{"table_name": "orders", "table_id": 1}],
        "relationships": [],
        "status": "draft",
    }

    res = await client.post("/api/v1/semantic/generate", json={"db_id": 201}, headers=auth_headers)
    assert res.status_code == 202
    data = res.json()
    assert data["db_id"] == 201
    assert data["status"] == "draft"
    assert len(data["tables"]) == 1


@pytest.mark.asyncio
@patch("src.api.routes.enrich_and_save_canonical_schema")
async def test_generate_semantic_layer_from_imported_schema(
    mock_enrich: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict,
):
    """POST /semantic/generate re-runs enrichment from imported schema source."""
    sem_db = SemanticDatabaseModel(
        id=202,
        created_by=1,
        display_name="Imported DB",
        db_type="postgresql",
        conn_url_enc="semantic:imported_schema:60",
        status="draft",
    )
    imported = ImportedSchemaModel(
        id=60,
        created_by=1,
        display_name="Imported DB",
        dialect="postgresql",
        semantic_db_id=202,
        schema_metadata=_raw_schema_metadata().model_dump(mode="json"),
    )
    async_session.add_all([sem_db, imported])
    await async_session.commit()

    mock_enrich.return_value = {
        "tables": [{"table_name": "orders", "table_id": 1}],
        "relationships": [],
        "status": "draft",
    }

    res = await client.post("/api/v1/semantic/generate", json={"db_id": 202}, headers=auth_headers)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "draft"


# ---------------------------------------------------------------------------
# POST /semantic/approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_semantic_layer_not_found(client: AsyncClient, auth_headers: dict):
    """POST /semantic/approve returns 404 for non-existent semantic database."""
    res = await client.post("/api/v1/semantic/approve", json={"db_id": 9999}, headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_approve_semantic_layer_no_draft_metrics(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict
):
    """POST /semantic/approve returns 404 when no draft metrics exist."""
    sem_db = SemanticDatabaseModel(
        id=210,
        created_by=1,
        display_name="No Drafts DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.commit()

    res = await client.post("/api/v1/semantic/approve", json={"db_id": 210}, headers=auth_headers)
    assert res.status_code == 404
    assert "No draft metrics" in res.json()["detail"]


def _make_route_def(
    name: str = "Total Orders", function: str = "COUNT", expression: str = "total_amount", base_entity: str = "orders"
) -> dict:
    return {
        "metric": {
            "name": name,
            "formula": {"function": function, "expression": expression},
            "base_entity": base_entity,
            "filters": [],
            "status": "pending_approval",
            "confidence": "high",
            "excluded_notes": "",
        }
    }


@pytest.mark.asyncio
async def test_approve_semantic_layer_success(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """POST /semantic/approve approves all draft metrics for the semantic database."""
    sem_db = SemanticDatabaseModel(
        id=211,
        created_by=1,
        display_name="Approve DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    tbl = SemanticTableModel(id=911, db_id=211, table_name="orders", business_name="Đơn hàng")
    metric1 = SemanticMetricModel(
        db_id=211,
        name="Total Orders",
        description="Count of orders",
        sql_template="SELECT COUNT(*) FROM orders",
        source="manual",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_make_route_def("Total Orders", "COUNT", "total_amount", "orders"),
        status="pending_approval",
        created_by=1,
        version=1,
    )
    metric2 = SemanticMetricModel(
        db_id=211,
        name="Total Revenue",
        description="Sum of revenue",
        sql_template="SELECT SUM(total) FROM orders",
        source="manual",
        formula="SUM(orders.total)",
        aggregation_type="SUM",
        definition=_make_route_def("Total Revenue", "SUM", "total_amount", "orders"),
        status="pending_approval",
        created_by=1,
        version=1,
    )
    async_session.add_all([sem_db, tbl, metric1, metric2])
    await async_session.commit()

    # Create initial version records for metric creation via semantic_service
    v1 = MetricVersionModel(metric_id=metric1.id, version=1, formula="COUNT(*)", changed_by=1)
    v2 = MetricVersionModel(metric_id=metric2.id, version=1, formula="SUM(orders.total)", changed_by=1)
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.post("/api/v1/semantic/approve", json={"db_id": 211}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["db_id"] == 211
    assert data["approved_count"] == 2
    assert "2" in data["message"]


@pytest.mark.asyncio
async def test_approve_skips_other_users_metrics(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """POST /semantic/approve skips metrics created by other users for non-admin users."""
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
        id=212,
        created_by=2,
        display_name="Ownership DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    tbl2 = SemanticTableModel(id=912, db_id=212, table_name="orders", business_name="Đơn hàng")
    my_metric = SemanticMetricModel(
        db_id=212,
        name="My Metric",
        description="Mine",
        sql_template="SELECT 1",
        source="manual",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_make_route_def("My Metric", "COUNT", "total_amount", "orders"),
        status="pending_approval",
        created_by=2,
        version=1,
    )
    other_metric = SemanticMetricModel(
        db_id=212,
        name="Other Metric",
        description="Not mine",
        sql_template="SELECT 1",
        source="manual",
        formula="SUM(x)",
        aggregation_type="SUM",
        definition=_make_route_def("Other Metric", "SUM", "total_amount", "orders"),
        status="pending_approval",
        created_by=999,
        version=1,
    )
    async_session.add_all([sem_db, tbl2, my_metric, other_metric])
    await async_session.commit()

    v1 = MetricVersionModel(metric_id=my_metric.id, version=1, formula="COUNT(*)", changed_by=2)
    v2 = MetricVersionModel(metric_id=other_metric.id, version=1, formula="SUM(x)", changed_by=999)
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.post("/api/v1/semantic/approve", json={"db_id": 212}, headers=user2_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["approved_count"] == 1


# ---------------------------------------------------------------------------
# GET /semantic/{db_id}/metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_metrics_empty(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """GET /semantic/{db_id}/metrics returns empty list when no metrics exist."""
    sem_db = SemanticDatabaseModel(
        id=220,
        created_by=1,
        display_name="Empty DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.commit()

    res = await client.get("/api/v1/semantic/220/metrics", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_metrics_with_version_info(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """GET /semantic/{db_id}/metrics returns metrics with version, status, approved_by."""
    sem_db = SemanticDatabaseModel(
        id=221,
        created_by=1,
        display_name="Metrics DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    metric = SemanticMetricModel(
        db_id=221,
        name="AOV",
        description="Average order value",
        sql_template="SELECT AVG(total) FROM orders",
        source="ai",
        formula="SUM(total)/COUNT(*)",
        aggregation_type="AVG",
        definition=_make_route_def("AOV", "AVG", "total_amount", "orders"),
        status="approved",
        created_by=1,
        version=2,
        approved_by=1,
    )
    async_session.add_all([sem_db, metric])
    await async_session.commit()

    res = await client.get("/api/v1/semantic/221/metrics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["metric_id"] == metric.id
    assert data[0]["name"] == "AOV"
    assert data[0]["version"] == 2
    assert data[0]["status"] == "approved"
    assert data[0]["approved_by"] == 1


# ---------------------------------------------------------------------------
# POST /semantic/{db_id}/metric (refactored to use semantic_service.create_metric)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_metric_creates_version_record(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict
):
    """POST /semantic/{db_id}/metric creates metric_versions record automatically."""
    sem_db = SemanticDatabaseModel(
        id=230,
        created_by=1,
        display_name="Metric Create DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="saved",
    )
    tbl = SemanticTableModel(id=230, db_id=230, table_name="orders", business_name="Đơn hàng")
    col = SemanticColumnModel(
        id=230, table_id=230, column_name="total_amount", data_type="NUMERIC", business_name="Tổng"
    )
    async_session.add_all([sem_db, tbl, col])
    await async_session.commit()

    payload = {
        "definition": _make_route_def("Total Orders", "COUNT", "total_amount", "orders"),
        "source": "manual",
    }
    res = await client.post("/api/v1/semantic/230/metric", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    metric_id = data["metric_id"]
    assert metric_id > 0

    # Verify metric_versions record was created
    from sqlalchemy import select

    versions_stmt = select(MetricVersionModel).where(MetricVersionModel.metric_id == metric_id)
    versions_result = await async_session.execute(versions_stmt)
    versions = versions_result.scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1


@pytest.mark.asyncio
async def test_create_metric_db_not_found(client: AsyncClient, auth_headers: dict):
    """POST /semantic/{db_id}/metric returns 404 for non-existent semantic database."""
    payload = {
        "definition": _make_route_def("Test", "COUNT", "total_amount", "orders"),
        "source": "manual",
    }
    res = await client.post("/api/v1/semantic/9999/metric", json=payload, headers=auth_headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /semantic/{db_id}/metric/{metric_id}/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_metric_history(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """GET /semantic/{db_id}/metric/{metric_id}/history returns version history."""
    sem_db = SemanticDatabaseModel(
        id=240,
        created_by=1,
        display_name="History DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    metric = SemanticMetricModel(
        db_id=240,
        name="Revenue",
        description="Total revenue",
        sql_template="SELECT SUM(total) FROM orders",
        source="manual",
        formula="SUM(orders.total)",
        aggregation_type="SUM",
        status="draft",
        created_by=1,
        version=2,
    )
    async_session.add_all([sem_db, metric])
    await async_session.commit()

    v1 = MetricVersionModel(metric_id=metric.id, version=1, formula="SUM(orders.total)", changed_by=1)
    v2 = MetricVersionModel(
        metric_id=metric.id,
        version=2,
        formula="SUM(orders.total) - SUM(orders.discount)",
        changed_by=1,
        change_reason="Added discount",
    )
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.get(f"/api/v1/semantic/240/metric/{metric.id}/history", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["metric_id"] == metric.id
    assert data["metric_name"] == "Revenue"
    assert len(data["versions"]) == 2
    assert data["versions"][0]["version"] == 1
    assert data["versions"][1]["version"] == 2
    assert data["versions"][1]["change_reason"] == "Added discount"


@pytest.mark.asyncio
async def test_get_metric_history_not_found(client: AsyncClient, auth_headers: dict):
    """GET /semantic/{db_id}/metric/{metric_id}/history returns 404 for non-existent metric."""
    res = await client.get("/api/v1/semantic/240/metric/9999/history", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_metric_history_wrong_db(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """GET /semantic/{db_id}/metric/{metric_id}/history returns 404 when metric belongs to different db."""
    sem_db = SemanticDatabaseModel(
        id=241,
        created_by=1,
        display_name="DB A",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    metric = SemanticMetricModel(
        db_id=241,
        name="Metric A",
        description="In DB A",
        sql_template="SELECT 1",
        source="manual",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="draft",
        created_by=1,
        version=1,
    )
    async_session.add_all([sem_db, metric])
    await async_session.commit()

    # Query with wrong db_id (241 vs 999)
    res = await client.get(f"/api/v1/semantic/999/metric/{metric.id}/history", headers=auth_headers)
    assert res.status_code == 404
