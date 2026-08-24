"""API tests for the singleton dashboard endpoints under /semantic/{db_id}/dashboard."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    ImportedSchemaModel,
    OrganizationMemberModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.services.organization_service import create_organization

DASHBOARD_ENDPOINT = "/api/v1/semantic/{db_id}/dashboard"
CONFLICT_CODE = "dashboard_version_conflict"
INVALID_LAYOUT_CODE = "dashboard_invalid_layout"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(user_id: int) -> UserModel:
    """Build an in-memory user matching the seeded rows for token minting."""
    return UserModel(
        id=user_id,
        email=f"user-{user_id}@company.com",
        username=f"user-{user_id}",
        full_name=f"User {user_id}",
        hashed_password="hash",
        status="active",
    )


def _headers_for(user_id: int, org_id: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {create_access_token(_user(user_id))}"}
    if org_id is not None:
        headers["X-Organization-ID"] = str(org_id)
    return headers


async def _create_user(async_session: AsyncSession, user_id: int, username: str) -> None:
    async_session.add(
        UserModel(
            id=user_id,
            email=f"{username}@company.com",
            username=username,
            full_name=username.title(),
            hashed_password="hash",
            status="active",
        )
    )
    await async_session.commit()


async def _add_membership(async_session: AsyncSession, org_id: int, user_id: int, role: str) -> None:
    async_session.add(OrganizationMemberModel(org_id=org_id, user_id=user_id, role=role))
    await async_session.commit()


async def _seed_workspace_db(async_session: AsyncSession, slug: str) -> dict[str, Any]:
    """Seed a workspace semantic database with a table, columns, and an approved metric."""
    organization = await create_organization(async_session, 1, "Acme", slug)
    database = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=1,
        display_name=f"Dash DB {slug}",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    table = SemanticTableModel(db_id=database.id, table_name="orders", business_name="Don hang")
    async_session.add(table)
    await async_session.flush()
    date_col = SemanticColumnModel(
        table_id=table.id,
        column_name="order_date",
        data_type="date",
        business_name="Ngay dat",
        is_time_dimension=True,
    )
    region_col = SemanticColumnModel(
        table_id=table.id,
        column_name="region",
        data_type="varchar",
        business_name="Khu vuc",
    )
    async_session.add_all([date_col, region_col])
    metric = SemanticMetricModel(
        db_id=database.id,
        created_by=1,
        name="doanh_thu",
        description="Tong doanh thu",
        sql_template="SELECT amount FROM orders",
        status="approved",
    )
    async_session.add(metric)
    await async_session.commit()
    return {
        "org_id": organization.id,
        "db_id": database.id,
        "metric_id": metric.id,
        "region_col_id": region_col.id,
        "date_col_id": date_col.id,
    }


async def _seed_sql_dump_db(async_session: AsyncSession) -> dict[str, Any]:
    """Seed a personal semantic database backed only by an imported SQL dump."""
    database = SemanticDatabaseModel(
        created_by=1,
        display_name="Dump DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    async_session.add(
        ImportedSchemaModel(
            created_by=1,
            display_name="Dump Schema",
            dialect="sqlite",
            schema_metadata={},
            semantic_db_id=database.id,
        )
    )
    await async_session.flush()
    table = SemanticTableModel(db_id=database.id, table_name="products", business_name="San pham")
    async_session.add(table)
    await async_session.flush()
    col = SemanticColumnModel(table_id=table.id, column_name="name", data_type="varchar", business_name="Ten SP")
    async_session.add(col)
    metric = SemanticMetricModel(
        db_id=database.id,
        created_by=1,
        name="so_luong",
        description="Dem san pham",
        sql_template="SELECT COUNT(*) FROM products",
        status="approved",
    )
    async_session.add(metric)
    await async_session.commit()
    return {
        "db_id": database.id,
        "metric_id": metric.id,
        "col_id": col.id,
    }


async def _seed_personal_db(async_session: AsyncSession) -> dict[str, Any]:
    """Seed a creator-only semantic database without a Workspace."""
    database = SemanticDatabaseModel(
        created_by=1,
        display_name="Personal Dash DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    table = SemanticTableModel(db_id=database.id, table_name="products", business_name="San pham")
    async_session.add(table)
    await async_session.flush()
    col = SemanticColumnModel(table_id=table.id, column_name="name", data_type="varchar", business_name="Ten SP")
    async_session.add(col)
    metric = SemanticMetricModel(
        db_id=database.id,
        created_by=1,
        name="so_luong",
        description="Dem san pham",
        sql_template="SELECT COUNT(*) FROM products",
        status="approved",
    )
    async_session.add(metric)
    await async_session.commit()
    return {
        "db_id": database.id,
        "metric_id": metric.id,
        "col_id": col.id,
    }


def _widget_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "widget-1",
        "metric_id": data["metric_id"],
        "dimension_col_id": data["region_col_id"],
        "date_filter_column_id": data["date_col_id"],
        "time_grain": "month",
        "chart_type": "line",
        "width": "half",
        "height": "normal",
        "col_span": None,
        "row_span": None,
        "custom_title": None,
    }


def _save_payload(data: dict[str, Any], expected_version: int) -> dict[str, Any]:
    return {"layout": {"widgets": [_widget_payload(data)]}, "expected_version": expected_version}


def _dump_save_payload(data: dict[str, Any], expected_version: int) -> dict[str, Any]:
    widget = {
        "id": "widget-1",
        "metric_id": data["metric_id"],
        "dimension_col_id": data["col_id"],
        "date_filter_column_id": None,
        "time_grain": None,
        "chart_type": "bar",
        "width": "half",
        "height": "normal",
        "col_span": None,
        "row_span": None,
        "custom_title": None,
    }
    return {"layout": {"widgets": [widget]}, "expected_version": expected_version}


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_uninitialized_dashboard_returns_empty_singleton(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-empty")

    response = await client.get(
        DASHBOARD_ENDPOINT.format(db_id=data["db_id"]),
        headers=_headers_for(1, data["org_id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "db_id": data["db_id"],
        "layout": None,
        "version": 0,
        "updated_at": None,
        "updated_by": None,
    }


@pytest.mark.asyncio
async def test_put_create_stores_singleton_at_version_one(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-create")

    response = await client.put(
        DASHBOARD_ENDPOINT.format(db_id=data["db_id"]),
        json=_save_payload(data, 0),
        headers=_headers_for(1, data["org_id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["db_id"] == data["db_id"]
    assert body["version"] == 1
    assert body["updated_by"] == 1
    assert body["updated_at"] is not None
    assert body["layout"]["widgets"][0]["metric_id"] == data["metric_id"]


@pytest.mark.asyncio
async def test_get_returns_persisted_layout_after_save(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-persist")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    headers = _headers_for(1, data["org_id"])
    await client.put(endpoint, json=_save_payload(data, 0), headers=headers)

    response = await client.get(endpoint, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["updated_by"] == 1
    assert body["layout"]["widgets"] == [_widget_payload(data)]


@pytest.mark.asyncio
async def test_put_update_increments_version_and_sets_updater(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-update")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    await client.put(endpoint, json=_save_payload(data, 0), headers=_headers_for(1, data["org_id"]))
    await _create_user(async_session, 2, "editor")
    await _add_membership(async_session, data["org_id"], 2, "data_lead")

    updated = await client.put(endpoint, json=_save_payload(data, 1), headers=_headers_for(2, data["org_id"]))

    assert updated.status_code == 200
    body = updated.json()
    assert body["version"] == 2
    assert body["updated_by"] == 2
    assert body["layout"]["widgets"][0]["id"] == "widget-1"


# ---------------------------------------------------------------------------
# Optimistic concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_expected_version_returns_conflict_payload(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-conflict")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    headers = _headers_for(1, data["org_id"])
    created = await client.put(endpoint, json=_save_payload(data, 0), headers=headers)
    assert created.status_code == 200

    stale_create = await client.put(endpoint, json=_save_payload(data, 0), headers=headers)
    stale_update = await client.put(endpoint, json=_save_payload(data, 5), headers=headers)

    assert stale_create.status_code == 409
    assert stale_update.status_code == 409
    for response in (stale_create, stale_update):
        detail = response.json()["detail"]
        assert detail["code"] == CONFLICT_CODE
        assert detail["current_version"] == 1


# ---------------------------------------------------------------------------
# Layout validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_approved_metric_reference_returns_422(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-draft")
    draft = SemanticMetricModel(
        db_id=data["db_id"],
        created_by=1,
        name="nhap",
        description="Metric nhap",
        sql_template="SELECT 1",
        status="draft",
    )
    async_session.add(draft)
    await async_session.commit()
    payload = _save_payload(data, 0)
    payload["layout"]["widgets"][0]["metric_id"] = draft.id

    response = await client.put(
        DASHBOARD_ENDPOINT.format(db_id=data["db_id"]),
        json=payload,
        headers=_headers_for(1, data["org_id"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == INVALID_LAYOUT_CODE


@pytest.mark.asyncio
async def test_cross_database_metric_reference_returns_422(client: Any, async_session: AsyncSession) -> None:
    owned = await _seed_workspace_db(async_session, "dash-cross-metric")
    other = await _seed_workspace_db(async_session, "dash-cross-metric-other")
    payload = _save_payload(owned, 0)
    payload["layout"]["widgets"][0]["metric_id"] = other["metric_id"]

    response = await client.put(
        DASHBOARD_ENDPOINT.format(db_id=owned["db_id"]),
        json=payload,
        headers=_headers_for(1, owned["org_id"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == INVALID_LAYOUT_CODE


@pytest.mark.asyncio
async def test_cross_database_column_reference_returns_422(client: Any, async_session: AsyncSession) -> None:
    owned = await _seed_workspace_db(async_session, "dash-cross-column")
    other = await _seed_workspace_db(async_session, "dash-cross-column-other")
    payload = _save_payload(owned, 0)
    payload["layout"]["widgets"][0]["dimension_col_id"] = other["region_col_id"]

    response = await client.put(
        DASHBOARD_ENDPOINT.format(db_id=owned["db_id"]),
        json=payload,
        headers=_headers_for(1, owned["org_id"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == INVALID_LAYOUT_CODE


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["admin", "data_lead", "member"])
@pytest.mark.asyncio
async def test_every_workspace_role_can_mutate_shared_dashboard(
    client: Any, async_session: AsyncSession, role: str
) -> None:
    data = await _seed_workspace_db(async_session, f"dash-role-{role}")
    await _create_user(async_session, 2, f"{role}-user")
    await _add_membership(async_session, data["org_id"], 2, role)

    created = await client.put(
        DASHBOARD_ENDPOINT.format(db_id=data["db_id"]),
        json=_save_payload(data, 0),
        headers=_headers_for(2, data["org_id"]),
    )

    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert created.json()["updated_by"] == 2


@pytest.mark.asyncio
async def test_wrong_workspace_is_masked_as_missing(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-owned")
    foreign_org = await create_organization(async_session, 1, "Foreign", "foreign-org")
    await _create_user(async_session, 2, "outsider")
    await _add_membership(async_session, foreign_org.id, 2, "member")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    outsider = _headers_for(2, foreign_org.id)

    got = await client.get(endpoint, headers=outsider)
    saved = await client.put(endpoint, json=_save_payload(data, 0), headers=outsider)
    missing = await client.get(DASHBOARD_ENDPOINT.format(db_id=99999), headers=outsider)

    assert got.status_code == 404
    assert saved.status_code == 404
    assert got.json()["detail"] == "Semantic database not found"
    assert got.json()["detail"] == missing.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_requests_are_rejected(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-anon")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])

    got = await client.get(endpoint)
    saved = await client.put(endpoint, json=_save_payload(data, 0))

    assert got.status_code == 401
    assert saved.status_code == 401


# ---------------------------------------------------------------------------
# Canonical scoping semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personal_db_with_org_header_stays_creator_only(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_personal_db(async_session)
    organization = await create_organization(async_session, 1, "Acme", "dash-personal-header")
    await _create_user(async_session, 2, "colleague")
    await _add_membership(async_session, organization.id, 2, "member")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    creator = _headers_for(1, organization.id)
    colleague = _headers_for(2, organization.id)

    created = await client.put(endpoint, json=_dump_save_payload(data, 0), headers=creator)
    fetched = await client.get(endpoint, headers=creator)
    denied_get = await client.get(endpoint, headers=colleague)
    denied_put = await client.put(endpoint, json=_dump_save_payload(data, 1), headers=colleague)
    missing = await client.get(DASHBOARD_ENDPOINT.format(db_id=99999), headers=colleague)

    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 1
    assert denied_get.status_code == 404
    assert denied_put.status_code == 404
    assert denied_get.json()["detail"] == "Semantic database not found"
    assert denied_get.json()["detail"] == missing.json()["detail"]


@pytest.mark.asyncio
async def test_workspace_db_without_header_uses_membership_fallback(client: Any, async_session: AsyncSession) -> None:
    data = await _seed_workspace_db(async_session, "dash-fallback")
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    await _create_user(async_session, 2, "teammate")
    await _add_membership(async_session, data["org_id"], 2, "member")

    empty = await client.get(endpoint, headers=_headers_for(2))
    created = await client.put(endpoint, json=_save_payload(data, 0), headers=_headers_for(2))
    fetched = await client.get(endpoint, headers=_headers_for(2))

    assert empty.status_code == 200
    assert empty.json()["version"] == 0
    assert created.status_code == 200
    assert created.json()["updated_by"] == 2
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 1


# ---------------------------------------------------------------------------
# SQL Dump support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_dump_database_persists_dashboard_without_query_execution(
    client: Any, async_session: AsyncSession
) -> None:
    data = await _seed_sql_dump_db(async_session)
    endpoint = DASHBOARD_ENDPOINT.format(db_id=data["db_id"])
    headers = _headers_for(1)

    with (
        patch(
            "src.services.query_execution.execute_compiled_query",
            side_effect=AssertionError("dashboard must not execute queries"),
        ),
        patch(
            "src.services.query_compiler.SemanticQueryCompiler.compile",
            side_effect=AssertionError("dashboard must not compile queries"),
        ),
    ):
        created = await client.put(endpoint, json=_dump_save_payload(data, 0), headers=headers)
        fetched = await client.get(endpoint, headers=headers)

    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert fetched.status_code == 200
    assert fetched.json()["layout"]["widgets"][0]["metric_id"] == data["metric_id"]
