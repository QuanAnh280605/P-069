"""API tests for the HITL review router: schema review gate + metric version decisions."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    MetricVersionModel,
    OrganizationMemberModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.services.organization_service import create_organization


def _headers(user: UserModel) -> dict[str, str]:
    """Build a bearer header for *user*."""
    return {"Authorization": f"Bearer {create_access_token(user)}"}


async def _seed_pending_schema(session: AsyncSession, owner_id: int = 1) -> SemanticDatabaseModel:
    """Seed a personal semantic DB whose tables/columns await BA/DA review."""
    sem_db = SemanticDatabaseModel(
        created_by=owner_id,
        display_name="Review DB",
        db_type="postgresql",
        conn_url_enc="encrypted",
        status="draft",
    )
    session.add(sem_db)
    await session.flush()
    table = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng đơn hàng",
        ai_business_name="Đơn hàng",
        ai_description="Bảng đơn hàng",
        review_status="pending_review",
        created_by=owner_id,
    )
    session.add(table)
    await session.flush()
    session.add(
        SemanticColumnModel(
            table_id=table.id,
            column_name="total_amount",
            data_type="NUMERIC",
            business_name="Tổng tiền",
            description="Tổng giá trị",
            ai_business_name="Tổng tiền",
            ai_description="Tổng giá trị",
            review_status="pending_review",
        )
    )
    await session.commit()
    return sem_db


# ---------------------------------------------------------------------------
# GET /semantic/{db_id}/schema/review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_review_lists_pending_tables_and_columns(client: AsyncClient, async_session: AsyncSession):
    """The review queue reports pending counts and the AI proposal per row."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)

    response = await client.get(f"/api/v1/semantic/{sem_db.id}/schema/review", headers=_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_review"
    assert body["pending_tables"] == 1
    assert body["pending_columns"] == 1
    table = body["tables"][0]
    assert table["table_name"] == "orders"
    assert table["ai_business_name"] == "Đơn hàng"
    assert table["reviewed_by"] is None
    assert table["columns"][0]["column_name"] == "total_amount"


@pytest.mark.asyncio
async def test_schema_review_returns_404_for_unknown_database(client: AsyncClient, async_session: AsyncSession):
    """An unknown semantic database is a 404, not an empty queue."""
    user = await async_session.get(UserModel, 1)

    response = await client.get("/api/v1/semantic/98765/schema/review", headers=_headers(user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_schema_review_hides_other_users_database(client: AsyncClient, async_session: AsyncSession):
    """A personal semantic database is invisible to a different user."""
    sem_db = await _seed_pending_schema(async_session)
    intruder = UserModel(
        id=2,
        email="intruder@company.com",
        username="intruder",
        full_name="Intruder",
        hashed_password="hash",
        status="active",
    )
    async_session.add(intruder)
    await async_session.commit()

    response = await client.get(f"/api/v1/semantic/{sem_db.id}/schema/review", headers=_headers(intruder))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT inline edit → POST /semantic/{db_id}/schema/approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inline_edit_then_approve_promotes_rows(client: AsyncClient, async_session: AsyncSession):
    """Editing inline keeps the row pending; approving publishes it with a stamp."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)

    edited = await client.put(
        f"/api/v1/semantic/{sem_db.id}/table/orders",
        json={"business_name": "Đơn đặt hàng", "description": "Đã review"},
        headers=_headers(user),
    )
    assert edited.status_code == 200
    assert edited.json()["review_status"] == "pending_review"

    approved = await client.post(f"/api/v1/semantic/{sem_db.id}/schema/approve", json={}, headers=_headers(user))

    assert approved.status_code == 200
    body = approved.json()
    assert body["approved_tables"] == 1
    assert body["approved_columns"] == 1
    assert body["pending_tables"] == 0
    assert body["pending_columns"] == 0
    assert body["status"] == "approved"

    queue = await client.get(f"/api/v1/semantic/{sem_db.id}/schema/review", headers=_headers(user))
    table = queue.json()["tables"][0]
    assert table["business_name"] == "Đơn đặt hàng"
    assert table["review_status"] == "approved"
    assert table["reviewed_by"] == 1
    assert table["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_approve_unknown_table_subset_is_404(client: AsyncClient, async_session: AsyncSession):
    """Approving a table name that does not exist reports 404 instead of silently passing."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)

    response = await client.post(
        f"/api/v1/semantic/{sem_db.id}/schema/approve",
        json={"table_names": ["ghost"]},
        headers=_headers(user),
    )

    assert response.status_code == 404
    assert "ghost" in response.json()["detail"]


@pytest.mark.asyncio
async def test_approve_subset_leaves_other_tables_pending(client: AsyncClient, async_session: AsyncSession):
    """Reviewers can publish incrementally, one table at a time."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    async_session.add(
        SemanticTableModel(
            db_id=sem_db.id,
            table_name="customers",
            business_name="Khách hàng",
            description="",
            review_status="pending_review",
            created_by=1,
        )
    )
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{sem_db.id}/schema/approve",
        json={"table_names": ["orders"]},
        headers=_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved_tables"] == 1
    assert body["pending_tables"] == 1
    assert body["status"] == "pending_review"


@pytest.mark.asyncio
async def test_member_without_approve_permission_gets_403(client: AsyncClient, async_session: AsyncSession):
    """Schema approval is gated on can_approve_metrics inside a Workspace."""
    owner = await async_session.get(UserModel, 1)
    member = UserModel(
        id=3,
        email="viewer@company.com",
        username="viewer",
        full_name="Viewer",
        hashed_password="hash",
        status="active",
    )
    async_session.add(member)
    organization = await create_organization(async_session, owner.id, "Review Workspace", "review-ws")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    sem_db = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=owner.id,
        display_name="Shared DB",
        db_type="postgresql",
        conn_url_enc="encrypted",
    )
    async_session.add(sem_db)
    await async_session.commit()

    response = await client.post(
        f"/api/v1/semantic/{sem_db.id}/schema/approve",
        json={},
        headers={**_headers(member), "X-Organization-ID": str(organization.id)},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Metric version decisions: pending-version + reject
# ---------------------------------------------------------------------------


def _metric_definition(name: str, expression: str = "total_amount") -> dict:
    """Build a minimal canonical metric definition payload."""
    return {
        "metric": {
            "name": name,
            "formula": {"function": "SUM", "expression": expression},
            "base_entity": "orders",
            "filters": [],
            "status": "approved",
            "confidence": "high",
            "excluded_notes": "",
        }
    }


async def _seed_published_metric_with_draft(
    session: AsyncSession, sem_db: SemanticDatabaseModel
) -> tuple[SemanticMetricModel, MetricVersionModel]:
    """Seed an approved metric plus a copy-on-write draft awaiting approval."""
    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Doanh thu",
        description="Tổng doanh thu",
        sql_template="",
        source="manual",
        formula="SUM(total_amount)",
        aggregation_type="SUM",
        definition=_metric_definition("Doanh thu"),
        status="approved",
        created_by=1,
        version=1,
    )
    session.add(metric)
    await session.flush()
    session.add(
        MetricVersionModel(
            metric_id=metric.id,
            version=1,
            name="Doanh thu",
            formula="SUM(total_amount)",
            definition=_metric_definition("Doanh thu"),
            status="approved",
            changed_by=1,
            approved_by=1,
        )
    )
    draft = MetricVersionModel(
        metric_id=metric.id,
        version=2,
        name="Doanh thu thuần",
        formula="SUM(net_amount)",
        definition=_metric_definition("Doanh thu thuần", "net_amount"),
        status="pending_approval",
        parent_version=1,
        changed_by=1,
        change_reason="Đổi sang doanh thu thuần",
    )
    session.add(draft)
    await session.commit()
    return metric, draft


@pytest.mark.asyncio
async def test_pending_version_returns_open_draft(client: AsyncClient, async_session: AsyncSession):
    """The pending-version endpoint exposes the copy-on-write draft, not the live row."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    metric, _ = await _seed_published_metric_with_draft(async_session, sem_db)

    response = await client.get(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/pending-version",
        headers=_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["status"] == "pending_approval"
    assert body["parent_version"] == 1
    assert body["name"] == "Doanh thu thuần"


@pytest.mark.asyncio
async def test_pending_version_404_when_nothing_awaits_approval(client: AsyncClient, async_session: AsyncSession):
    """A metric with no open draft returns 404 rather than the approved version."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Số đơn",
        description="",
        sql_template="",
        source="manual",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        definition=_metric_definition("Số đơn"),
        status="approved",
        created_by=1,
        version=1,
    )
    async_session.add(metric)
    await async_session.commit()

    response = await client.get(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/pending-version",
        headers=_headers(user),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pending_version_rejects_metric_from_another_database(client: AsyncClient, async_session: AsyncSession):
    """Metric ids are scoped to the semantic database in the path."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    other_db = await _seed_pending_schema(async_session)
    metric, _ = await _seed_published_metric_with_draft(async_session, other_db)

    response = await client.get(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/pending-version",
        headers=_headers(user),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_draft_leaves_published_definition_intact(client: AsyncClient, async_session: AsyncSession):
    """Rejecting a draft records the decision without touching the live metric."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    metric, _ = await _seed_published_metric_with_draft(async_session, sem_db)

    response = await client.post(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/reject",
        json={"reason": "Chưa khớp định nghĩa tài chính"},
        headers=_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["status"] == "rejected"
    assert "Chưa khớp định nghĩa tài chính" in body["change_reason"]

    await async_session.refresh(metric)
    assert metric.status == "approved"
    assert metric.version == 1
    assert metric.definition["metric"]["formula"]["expression"] == "total_amount"


@pytest.mark.asyncio
async def test_reject_without_pending_draft_is_422(client: AsyncClient, async_session: AsyncSession):
    """Rejecting twice reports a 422 instead of mutating an already-closed version."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    metric, _ = await _seed_published_metric_with_draft(async_session, sem_db)
    url = f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}/reject"

    first = await client.post(url, json={"reason": "Không đúng"}, headers=_headers(user))
    second = await client.post(url, json={"reason": "Không đúng"}, headers=_headers(user))

    assert first.status_code == 200
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_put_published_metric_returns_pending_version(client: AsyncClient, async_session: AsyncSession):
    """Editing a published metric answers with the queued draft, live definition unchanged."""
    user = await async_session.get(UserModel, 1)
    sem_db = await _seed_pending_schema(async_session)
    orders = await async_session.scalar(select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db.id))
    async_session.add(
        SemanticColumnModel(
            table_id=orders.id,
            column_name="net_amount",
            data_type="NUMERIC",
            business_name="Doanh thu thuần",
            description="",
            review_status="approved",
        )
    )
    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Doanh thu",
        description="",
        sql_template="",
        source="manual",
        formula="SUM(total_amount)",
        aggregation_type="SUM",
        definition=_metric_definition("Doanh thu"),
        status="approved",
        created_by=1,
        version=1,
    )
    async_session.add(metric)
    await async_session.flush()
    async_session.add(
        MetricVersionModel(
            metric_id=metric.id,
            version=1,
            name="Doanh thu",
            formula="SUM(total_amount)",
            definition=_metric_definition("Doanh thu"),
            status="approved",
            changed_by=1,
            approved_by=1,
        )
    )
    await async_session.commit()

    response = await client.put(
        f"/api/v1/semantic/{sem_db.id}/metric/{metric.id}",
        json={
            "definition": _metric_definition("Doanh thu", "net_amount"),
            "change_reason": "Chuyển sang doanh thu thuần",
        },
        headers=_headers(user),
    )

    print(response.json())
    assert response.status_code == 200
    body = response.json()
    assert body["definition"]["metric"]["formula"]["expression"] == "total_amount"
    assert body["version"] == 1
    draft = body["pending_version"]
    assert draft is not None
    assert draft["version"] == 2
    assert draft["status"] in {"pending_approval", "needs_review"}
    assert draft["definition"]["metric"]["formula"]["expression"] == "net_amount"
