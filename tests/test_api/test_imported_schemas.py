"""API tests for persisted user-owned SQL dump schemas."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import OrganizationMemberModel, UserModel
from src.services.organization_service import create_organization

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sql_dumps" / "postgresql_schema.sql"
PREVIEW_ENDPOINT = "/api/v1/semantic/import/preview"
SAVED_ENDPOINT = "/api/v1/semantic/import/saved"


def _token_headers(user: UserModel | None = None, org_id: int | None = None) -> dict[str, str]:
    active_user = user or UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        status="active",
    )
    headers = {"Authorization": f"Bearer {create_access_token(active_user)}"}
    if org_id is not None:
        headers["X-Organization-ID"] = str(org_id)
    return headers


async def _preview_schema(client, org_id: int) -> dict:
    headers = _token_headers(org_id=org_id) | {
        "Content-Type": "application/sql",
        "X-Filename": "schema.sql",
    }
    response = await client.post(PREVIEW_ENDPOINT, content=FIXTURE.read_bytes(), headers=headers)
    assert response.status_code == 200
    return response.json()["raw_schema"]


async def _data_lead_workspace(async_session: AsyncSession) -> int:
    """Create the test Workspace with the semantic-data role under test."""
    organization = await create_organization(async_session, 1, "Data Workspace", "data-workspace")
    membership = await async_session.scalar(
        select(OrganizationMemberModel).where(
            OrganizationMemberModel.org_id == organization.id,
            OrganizationMemberModel.user_id == 1,
        )
    )
    membership.role = "data_lead"
    await async_session.commit()
    return organization.id


@pytest.mark.asyncio
async def test_saved_schema_lifecycle(client, async_session: AsyncSession) -> None:
    org_id = await _data_lead_workspace(async_session)
    raw_schema = await _preview_schema(client, org_id)
    create = await client.post(
        SAVED_ENDPOINT,
        json={"display_name": "  Sales schema  ", "raw_schema": raw_schema},
        headers=_token_headers(org_id=org_id),
    )

    assert create.status_code == 201
    saved = create.json()
    assert saved["display_name"] == "Sales schema"
    assert saved["dialect"] == "postgresql"
    assert saved["table_count"] == 3

    listing = await client.get(SAVED_ENDPOINT, headers=_token_headers(org_id=org_id))
    detail = await client.get(f"{SAVED_ENDPOINT}/{saved['id']}", headers=_token_headers(org_id=org_id))
    assert [item["display_name"] for item in listing.json()] == ["Sales schema"]
    assert detail.json()["raw_schema"] == raw_schema

    deleted = await client.delete(f"{SAVED_ENDPOINT}/{saved['id']}", headers=_token_headers(org_id=org_id))
    assert deleted.status_code == 204
    assert (await client.get(SAVED_ENDPOINT, headers=_token_headers(org_id=org_id))).json() == []


@pytest.mark.asyncio
async def test_saved_schema_is_private_to_owner(client, async_session: AsyncSession) -> None:
    org_id = await _data_lead_workspace(async_session)
    raw_schema = await _preview_schema(client, org_id)
    create = await client.post(
        SAVED_ENDPOINT,
        json={"display_name": "Private schema", "raw_schema": raw_schema},
        headers=_token_headers(org_id=org_id),
    )
    second_user = await _create_second_user(async_session)
    schema_id = create.json()["id"]

    detail = await client.get(f"{SAVED_ENDPOINT}/{schema_id}", headers=_token_headers(second_user))
    deleted = await client.delete(f"{SAVED_ENDPOINT}/{schema_id}", headers=_token_headers(second_user))

    assert detail.status_code == 404
    assert deleted.status_code in {403, 404}


@pytest.mark.asyncio
async def test_saved_schema_rejects_blank_display_name(client, async_session: AsyncSession) -> None:
    org_id = await _data_lead_workspace(async_session)
    response = await client.post(
        SAVED_ENDPOINT,
        json={"display_name": "   ", "raw_schema": await _preview_schema(client, org_id)},
        headers=_token_headers(org_id=org_id),
    )

    assert response.status_code == 422


async def _create_second_user(session: AsyncSession) -> UserModel:
    user = UserModel(
        id=2,
        email="second@company.com",
        username="second",
        full_name="Second",
        hashed_password="hash",
        status="active",
    )
    session.add(user)
    await session.commit()
    return user
