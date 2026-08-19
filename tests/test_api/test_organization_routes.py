"""API behavior tests for Workspace and invitation endpoints."""

import pytest

from src.api.auth import create_access_token
from src.models.db import OrganizationMemberModel, SemanticDatabaseModel, SemanticTableModel, UserModel
from src.services.organization_service import create_organization


def _headers(user: UserModel) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.mark.asyncio
async def test_create_and_list_workspace(client, async_session):
    user = await async_session.get(UserModel, 1)
    response = await client.post("/api/v1/org", json={"name": "Acme Analytics"}, headers=_headers(user))

    assert response.status_code == 201
    assert response.json()["role"] == "admin"

    listed = await client.get("/api/v1/org/my-orgs", headers=_headers(user))
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Acme Analytics"


@pytest.mark.asyncio
async def test_member_can_preview_invitation_and_accept(client, async_session):
    owner = await async_session.get(UserModel, 1)
    created = await client.post("/api/v1/org", json={"name": "Acme"}, headers=_headers(owner))
    org_id = created.json()["id"]
    invite = await client.post(
        "/api/v1/org/invite",
        json={"role": "member"},
        headers={**_headers(owner), "X-Organization-ID": str(org_id)},
    )
    assert invite.status_code == 201
    token = invite.json()["invite_url"].rsplit("/", 1)[-1]

    preview = await client.get(f"/api/v1/invite/{token}")
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Acme"

    member = UserModel(
        id=2,
        email="new@company.com",
        username="newmember",
        full_name="New Member",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(member)
    await async_session.commit()
    accepted = await client.post(f"/api/v1/invite/{token}/accept", headers=_headers(member))

    assert accepted.status_code == 200
    assert accepted.json()["role"] == "member"


@pytest.mark.asyncio
async def test_invitation_uses_deployed_frontend_url(client, async_session, monkeypatch):
    owner = await async_session.get(UserModel, 1)
    created = await client.post("/api/v1/org", json={"name": "Acme"}, headers=_headers(owner))
    monkeypatch.setattr(
        "src.api.organization_routes.get_settings",
        lambda: type("Settings", (), {"frontend_app_url": "https://app.example.com"})(),
    )

    response = await client.post(
        "/api/v1/org/invite",
        json={"role": "member"},
        headers={**_headers(owner), "X-Organization-ID": str(created.json()["id"])},
    )

    assert response.status_code == 201
    assert response.json()["invite_url"].startswith("https://app.example.com/invite/")


@pytest.mark.asyncio
async def test_missing_org_header_is_rejected_for_multiple_workspaces(client, async_session):
    user = await async_session.get(UserModel, 1)
    for name in ("Workspace A", "Workspace B"):
        response = await client.post("/api/v1/org", json={"name": name}, headers=_headers(user))
        assert response.status_code == 201

    response = await client.get("/api/v1/org/current", headers=_headers(user))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_member_cannot_mutate_workspace_resource_without_header(client, async_session):
    owner = await async_session.get(UserModel, 1)
    member = UserModel(
        id=2,
        email="member@example.com",
        username="member",
        full_name="Member",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(member)
    organization = await create_organization(async_session, owner.id, "Secure Workspace", "secure")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    semantic_db = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=owner.id,
        display_name="Owned DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(semantic_db)
    await async_session.flush()
    async_session.add(
        SemanticTableModel(
            db_id=semantic_db.id,
            table_name="orders",
            business_name="Orders",
            description="",
            created_by=owner.id,
        )
    )
    await async_session.commit()

    response = await client.put(
        f"/api/v1/semantic/{semantic_db.id}/table/orders",
        json={"business_name": "Changed", "description": "Changed"},
        headers=_headers(member),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_workspace_header_blocks_cross_workspace_resource_access(client, async_session):
    owner = await async_session.get(UserModel, 1)
    first = await create_organization(async_session, owner.id, "First Workspace", "first")
    second = await create_organization(async_session, owner.id, "Second Workspace", "second")
    semantic_db = SemanticDatabaseModel(
        org_id=first.id,
        created_by=owner.id,
        display_name="First DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(semantic_db)
    await async_session.flush()
    async_session.add(
        SemanticTableModel(
            db_id=semantic_db.id,
            table_name="orders",
            business_name="Orders",
            description="",
            created_by=owner.id,
        )
    )
    await async_session.commit()

    response = await client.put(
        f"/api/v1/semantic/{semantic_db.id}/table/orders",
        json={"business_name": "Changed", "description": "Changed"},
        headers={**_headers(owner), "X-Organization-ID": str(second.id)},
    )

    assert response.status_code == 404
