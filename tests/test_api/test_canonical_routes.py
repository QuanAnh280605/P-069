"""Tests for canonical semantic layer endpoints: generate, approve, metrics list, metric history."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    ImportedSchemaModel,
    LiveTargetDbModel,
    MetricVersionModel,
    OrganizationMemberModel,
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
from src.services.organization_service import create_organization


@pytest.fixture
def auth_headers():
    """Create a valid JWT header for the seeded test user (id=1)."""
    user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
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


async def _seed_workspace_actor(async_session: AsyncSession, role: str) -> tuple[UserModel, int, UserModel]:
    owner = await async_session.get(UserModel, 1)
    organization = await create_organization(async_session, owner.id, f"{role} Workspace", f"metric-{role}")
    actor = owner
    if role != "admin":
        actor = UserModel(
            id=2,
            email=f"{role}@company.com",
            username=role,
            full_name=role.replace("_", " ").title(),
            hashed_password="hash",
            status="active",
        )
        async_session.add(actor)
        async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=actor.id, role=role))
    return owner, organization.id, actor


async def _seed_metric_database(async_session: AsyncSession, owner_id: int, org_id: int) -> SemanticDatabaseModel:
    sem_db = SemanticDatabaseModel(
        org_id=org_id,
        created_by=owner_id,
        display_name="Metric RBAC DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="saved",
    )
    async_session.add(sem_db)
    await async_session.flush()
    table = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Orders",
        primary_key_column="id",
    )
    async_session.add(table)
    await async_session.flush()
    async_session.add_all(
        [
            SemanticColumnModel(
                table_id=table.id,
                column_name="id",
                data_type="INTEGER",
                business_name="ID",
                is_primary_key=True,
            ),
            SemanticColumnModel(
                table_id=table.id,
                column_name="total_amount",
                data_type="NUMERIC",
                business_name="Total",
            ),
        ]
    )
    return sem_db


async def _seed_unverified_metric(async_session: AsyncSession, db_id: int) -> SemanticMetricModel:
    metric = SemanticMetricModel(
        db_id=db_id,
        name="Member Submission",
        description="Submitted metric",
        sql_template="",
        source="manual",
        formula="",
        aggregation_type="SUM",
        definition=_make_route_def("Member Submission", "SUM", "total_amount", "orders"),
        status="unverified",
        created_by=3,
        version=1,
    )
    async_session.add(metric)
    await async_session.flush()
    async_session.add(MetricVersionModel(metric_id=metric.id, version=1, formula="", changed_by=3))
    return metric


async def _seed_metric_workspace(async_session: AsyncSession, role: str) -> tuple[UserModel, int, int, int]:
    owner, org_id, actor = await _seed_workspace_actor(async_session, role)
    sem_db = await _seed_metric_database(async_session, owner.id, org_id)
    metric = await _seed_unverified_metric(async_session, sem_db.id)
    await async_session.commit()
    return actor, org_id, sem_db.id, metric.id


async def _seed_metric_with_versions(async_session: AsyncSession, role: str) -> tuple[UserModel, int, int, int]:
    """Seed a workspace metric whose approved current row is v3 of a v1/v2/v3 history."""
    actor, org_id, db_id, metric_id = await _seed_metric_workspace(async_session, role)
    metric = await async_session.get(SemanticMetricModel, metric_id)
    metric.version = 3
    metric.status = "approved"
    async_session.add_all(
        [
            MetricVersionModel(
                metric_id=metric_id,
                version=2,
                formula="total_amount",
                definition=_make_route_def("Member Submission", "AVG", "total_amount", "orders"),
                changed_by=3,
            ),
            MetricVersionModel(
                metric_id=metric_id,
                version=3,
                formula="id",
                definition=_make_route_def("Member Submission", "COUNT", "id", "orders"),
                changed_by=3,
            ),
        ]
    )
    await async_session.commit()
    return actor, org_id, db_id, metric_id


def _workspace_headers(user: UserModel, org_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(user)}",
        "X-Organization-ID": str(org_id),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "operation", "expected_status"),
    [
        ("admin", "create", 403),
        ("admin", "update", 403),
        ("admin", "delete", 403),
        ("admin", "bulk_approve", 403),
        ("admin", "single_approve", 403),
        ("data_lead", "create", 201),
        ("data_lead", "update", 200),
        ("data_lead", "delete", 204),
        ("data_lead", "bulk_approve", 200),
        ("data_lead", "single_approve", 200),
        ("member", "create", 201),
        ("member", "update", 403),
        ("member", "delete", 403),
        ("member", "bulk_approve", 403),
        ("member", "single_approve", 403),
    ],
)
async def test_metric_mutation_role_matrix(
    client: AsyncClient,
    async_session: AsyncSession,
    role: str,
    operation: str,
    expected_status: int,
):
    actor, org_id, db_id, metric_id = await _seed_metric_workspace(async_session, role)
    headers = _workspace_headers(actor, org_id)
    definition = _make_route_def("Changed Metric", "SUM", "total_amount", "orders")
    requests = {
        "create": ("post", f"/api/v1/semantic/{db_id}/metric", {"definition": definition, "source": "manual"}),
        "update": ("put", f"/api/v1/semantic/{db_id}/metric/{metric_id}", {"definition": definition}),
        "delete": ("delete", f"/api/v1/semantic/{db_id}/metric/{metric_id}", None),
        "bulk_approve": ("post", "/api/v1/semantic/approve", {"db_id": db_id}),
        "single_approve": ("post", f"/api/v1/semantic/{db_id}/metric/{metric_id}/approve", None),
    }
    method, url, payload = requests[operation]

    response = await client.request(method, url, json=payload, headers=headers)

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_member_create_forces_unverified_status_and_authenticated_creator(client, async_session):
    actor, org_id, db_id, _ = await _seed_metric_workspace(async_session, "member")
    definition = _make_route_def("Escalation Attempt", "SUM", "total_amount", "orders")
    definition["metric"]["status"] = "approved"

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric",
        json={"definition": definition, "source": "manual"},
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "unverified"
    metric = await async_session.get(SemanticMetricModel, response.json()["metric_id"])
    assert metric.created_by == actor.id
    assert metric.status == "unverified"
    assert metric.definition["metric"]["status"] == "unverified"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected_names"),
    [
        ("admin", {"Approved"}),
        ("data_lead", {"Approved", "Pending", "Review", "Own Unverified", "Other Unverified"}),
        ("member", {"Approved", "Own Unverified"}),
    ],
)
async def test_metric_list_visibility_by_role(client, async_session, role, expected_names):
    actor, org_id, db_id, seeded_metric_id = await _seed_metric_workspace(async_session, role)
    seeded = await async_session.get(SemanticMetricModel, seeded_metric_id)
    seeded.name = "Other Unverified"
    seeded.created_by = 999
    records = [
        ("Approved", "approved", 999),
        ("Pending", "pending_approval", 999),
        ("Review", "needs_review", 999),
        ("Own Unverified", "unverified", actor.id),
    ]
    for name, status_name, creator in records:
        async_session.add(
            SemanticMetricModel(
                db_id=db_id,
                name=name,
                description="",
                sql_template="",
                source="manual",
                aggregation_type="COUNT",
                status=status_name,
                created_by=creator,
                version=1,
            )
        )
    await async_session.commit()

    response = await client.get(
        f"/api/v1/semantic/{db_id}/metrics",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == expected_names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "owner", "expected_status"),
    [("admin", "other", 404), ("member", "other", 404), ("member", "self", 200), ("data_lead", "other", 200)],
)
async def test_unverified_metric_history_visibility(client, async_session, role, owner, expected_status):
    actor, org_id, db_id, metric_id = await _seed_metric_workspace(async_session, role)
    metric = await async_session.get(SemanticMetricModel, metric_id)
    metric.created_by = actor.id if owner == "self" else 999
    await async_session.commit()

    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/history",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["dimensions", "filter-columns"])
async def test_metric_metadata_rejects_cross_workspace_database(client, async_session, suffix):
    actor, actor_org_id, _, _ = await _seed_metric_workspace(async_session, "member")
    other_owner = UserModel(
        id=10,
        email="other-owner@company.com",
        username="other-owner",
        full_name="Other Owner",
        hashed_password="hash",
        status="active",
    )
    async_session.add(other_owner)
    await async_session.flush()
    other_org = await create_organization(async_session, other_owner.id, "Other Workspace", "other-workspace")
    other_db = await _seed_metric_database(async_session, other_owner.id, other_org.id)
    other_metric = await _seed_unverified_metric(async_session, other_db.id)
    await async_session.commit()

    response = await client.get(
        f"/api/v1/semantic/{other_db.id}/metric/{other_metric.id}/{suffix}",
        headers=_workspace_headers(actor, actor_org_id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["dimensions", "filter-columns"])
async def test_metric_metadata_hides_another_members_unverified_metric(client, async_session, suffix):
    actor, org_id, db_id, metric_id = await _seed_metric_workspace(async_session, "member")
    metric = await async_session.get(SemanticMetricModel, metric_id)
    metric.created_by = 999
    await async_session.commit()

    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/{suffix}",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 404


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
    tbl = SemanticTableModel(id=911, db_id=211, table_name="orders", business_name="Đơn hàng", primary_key_column="id")
    col1 = SemanticColumnModel(
        id=9011, table_id=911, column_name="total_amount", data_type="NUMERIC", business_name="Tổng tiền"
    )
    col2 = SemanticColumnModel(
        id=9012, table_id=911, column_name="id", data_type="INTEGER", business_name="ID", is_primary_key=True
    )
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
    async_session.add_all([sem_db, tbl, col1, col2, metric1, metric2])
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
    tbl2 = SemanticTableModel(id=912, db_id=212, table_name="orders", business_name="Đơn hàng", primary_key_column="id")
    col21 = SemanticColumnModel(
        id=9021, table_id=912, column_name="total_amount", data_type="NUMERIC", business_name="Tổng tiền"
    )
    col22 = SemanticColumnModel(
        id=9022, table_id=912, column_name="id", data_type="INTEGER", business_name="ID", is_primary_key=True
    )
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
    async_session.add_all([sem_db, tbl2, col21, col22, my_metric, other_metric])
    await async_session.commit()

    v1 = MetricVersionModel(metric_id=my_metric.id, version=1, formula="COUNT(*)", changed_by=2)
    v2 = MetricVersionModel(metric_id=other_metric.id, version=1, formula="SUM(x)", changed_by=999)
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.post("/api/v1/semantic/approve", json={"db_id": 212}, headers=user2_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["approved_count"] == 1


@pytest.mark.asyncio
async def test_approve_semantic_layer_all_need_review_returns_422(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict
):
    """POST /semantic/approve returns 422 and leaves db status unchanged when every candidate needs review."""
    sem_db = SemanticDatabaseModel(
        id=213,
        created_by=1,
        display_name="All Review DB",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    # Table WITHOUT a primary key → MISSING_GRAIN diagnostic on resolve
    tbl = SemanticTableModel(id=913, db_id=213, table_name="orders", business_name="Đơn hàng")
    col = SemanticColumnModel(
        id=9031, table_id=913, column_name="total_amount", data_type="NUMERIC", business_name="Tổng tiền"
    )
    metric = SemanticMetricModel(
        db_id=213,
        name="Broken Metric",
        description="Needs review",
        sql_template="SELECT SUM(total_amount) FROM orders",
        source="manual",
        formula="SUM(orders.total)",
        aggregation_type="SUM",
        definition=_make_route_def("Broken Metric", "SUM", "total_amount", "orders"),
        status="pending_approval",
        created_by=1,
        version=1,
    )
    async_session.add_all([sem_db, tbl, col, metric])
    await async_session.commit()

    res = await client.post("/api/v1/semantic/approve", json={"db_id": 213}, headers=auth_headers)

    assert res.status_code == 422
    await async_session.refresh(sem_db)
    assert sem_db.status != "saved"


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


@pytest.mark.asyncio
async def test_update_metric_cross_db_returns_404(client: AsyncClient, async_session: AsyncSession, auth_headers: dict):
    """PUT /semantic/{db_id}/metric/{metric_id} returns 404 when the metric belongs to another database."""
    sem_db_a = SemanticDatabaseModel(
        id=242,
        created_by=1,
        display_name="DB A",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    sem_db_b = SemanticDatabaseModel(
        id=243,
        created_by=1,
        display_name="DB B",
        db_type="postgresql",
        conn_url_enc="dummy",
        status="draft",
    )
    metric_b = SemanticMetricModel(
        db_id=243,
        name="Metric B",
        description="In DB B",
        sql_template="SELECT 1",
        source="manual",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="pending_approval",
        created_by=1,
        version=1,
    )
    async_session.add_all([sem_db_a, sem_db_b, metric_b])
    await async_session.commit()

    res = await client.put(
        f"/api/v1/semantic/242/metric/{metric_b.id}",
        json={"definition": _make_route_def("Hijack Attempt", "COUNT", "total_amount", "orders")},
        headers=auth_headers,
    )

    assert res.status_code == 404
    assert res.json()["detail"] == f"Metric {metric_b.id} not found"


# ---------------------------------------------------------------------------
# POST /semantic/{db_id}/metric/{metric_id}/rollback/{target_version}
# ---------------------------------------------------------------------------


async def _fetch_rollback_versions(async_session: AsyncSession, metric_id: int) -> list[MetricVersionModel]:
    result = await async_session.execute(
        select(MetricVersionModel).where(MetricVersionModel.metric_id == metric_id).order_by(MetricVersionModel.version)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
@pytest.mark.parametrize(("role", "expected_status"), [("admin", 403), ("data_lead", 200), ("member", 403)])
async def test_metric_rollback_role_matrix(client, async_session, role, expected_status):
    """Only Data Leads may roll back metrics, including another member's metric."""
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, role)

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_rollback_requires_authentication(client):
    response = await client.post("/api/v1/semantic/1/metric/1/rollback/2")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rollback_missing_database_returns_404(client, async_session):
    actor, org_id, _, _ = await _seed_metric_with_versions(async_session, "data_lead")

    response = await client.post(
        "/api/v1/semantic/9999/metric/1/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_missing_metric_returns_404(client, async_session):
    actor, org_id, db_id, _ = await _seed_metric_with_versions(async_session, "data_lead")

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/9999/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_wrong_database_returns_404(client, async_session):
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, "data_lead")
    owner = await async_session.get(UserModel, 1)
    other_db = await _seed_metric_database(async_session, owner.id, org_id)
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{other_db.id}/metric/{metric_id}/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_cross_workspace_database_returns_404(client, async_session):
    actor, actor_org_id, _, _ = await _seed_metric_with_versions(async_session, "member")
    other_owner = UserModel(
        id=10,
        email="other-owner@company.com",
        username="other-owner",
        full_name="Other Owner",
        hashed_password="hash",
        status="active",
    )
    async_session.add(other_owner)
    await async_session.flush()
    other_org = await create_organization(async_session, other_owner.id, "Other Workspace", "other-workspace")
    other_db = await _seed_metric_database(async_session, other_owner.id, other_org.id)
    other_metric = await _seed_unverified_metric(async_session, other_db.id)
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{other_db.id}/metric/{other_metric.id}/rollback/2",
        headers=_workspace_headers(actor, actor_org_id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_non_integer_target_version_returns_422(client, async_session):
    """A non-integer path segment fails FastAPI path validation before the handler runs."""
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, "data_lead")

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/rollback/not-an-int",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("target_version", [0, -1, 3, 99])
async def test_rollback_rejects_invalid_target_versions(client, async_session, target_version):
    """Zero/negative targets fail ge=1 validation; current/future targets fail the service range check."""
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, "data_lead")

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/rollback/{target_version}",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rollback_missing_snapshot_returns_422(client, async_session):
    """A target within range whose version row is absent maps to 422."""
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, "data_lead")
    snapshot = (
        await async_session.execute(
            select(MetricVersionModel).where(
                MetricVersionModel.metric_id == metric_id,
                MetricVersionModel.version == 2,
            )
        )
    ).scalar_one()
    await async_session.delete(snapshot)
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rollback_restores_v2_deletes_v3_and_approves(client, async_session):
    """v3→v2 deletes v3 and leaves the current row as approved v2 content."""
    actor, org_id, db_id, metric_id = await _seed_metric_with_versions(async_session, "data_lead")
    before = await _fetch_rollback_versions(async_session, metric_id)
    assert [v.version for v in before] == [1, 2, 3]

    response = await client.post(
        f"/api/v1/semantic/{db_id}/metric/{metric_id}/rollback/2",
        headers=_workspace_headers(actor, org_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metric_id"] == metric_id
    assert body["status"] == "approved"

    metric = await async_session.get(SemanticMetricModel, metric_id)
    assert metric.version == 2
    assert metric.status == "approved"
    assert metric.aggregation_type == "AVG"
    assert metric.definition["metric"]["formula"]["function"] == "AVG"
    assert metric.definition["metric"]["formula"]["expression"] == "total_amount"
    assert metric.definition["metric"]["status"] == "approved"

    remaining = await _fetch_rollback_versions(async_session, metric_id)
    assert [v.version for v in remaining] == [1, 2]


@pytest.mark.asyncio
async def test_rollback_personal_db_requires_creator_ownership(client, async_session, auth_headers):
    """Personal databases require the requester to own the metric itself."""
    sem_db = _seed_semantic_db(async_session, db_id=250)
    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Foreign Metric",
        description="",
        sql_template="",
        source="manual",
        formula="total_amount",
        aggregation_type="SUM",
        definition=_make_route_def("Foreign Metric", "SUM", "total_amount", "orders"),
        status="approved",
        created_by=99,
        version=2,
    )
    async_session.add(metric)
    await async_session.flush()
    async_session.add_all(
        [
            MetricVersionModel(
                metric_id=metric.id,
                version=1,
                formula="total_amount",
                definition=_make_route_def("Foreign Metric", "SUM", "total_amount", "orders"),
                changed_by=99,
            ),
            MetricVersionModel(
                metric_id=metric.id,
                version=2,
                formula="id",
                definition=_make_route_def("Foreign Metric", "COUNT", "id", "orders"),
                changed_by=99,
            ),
        ]
    )
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/rollback/1",
        headers=auth_headers,
    )

    assert response.status_code == 422
