"""Behavior tests for Workspace membership and invitation seams."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.models.db import OrganizationInvitationModel, OrganizationMemberModel, UserModel
from src.services.organization_service import (
    ROLE_PERMISSIONS,
    accept_invitation,
    create_invitation,
    create_organization,
    get_membership,
    list_members,
    remove_member,
)


def test_admin_is_not_a_semantic_data_approver():
    assert ROLE_PERMISSIONS["admin"]["can_manage_members"] is True
    assert ROLE_PERMISSIONS["admin"]["can_manage_invitations"] is True
    assert ROLE_PERMISSIONS["admin"]["can_manage_schema"] is False
    assert ROLE_PERMISSIONS["admin"]["can_create_metrics"] is False
    assert ROLE_PERMISSIONS["admin"]["can_approve_metrics"] is False
    assert ROLE_PERMISSIONS["admin"]["can_use_chat"] is True
    assert ROLE_PERMISSIONS["admin"]["can_use_data_assistant"] is True
    assert ROLE_PERMISSIONS["admin"]["can_use_metric_studio"] is False
    assert ROLE_PERMISSIONS["data_lead"]["can_approve_metrics"] is True
    assert ROLE_PERMISSIONS["data_lead"]["can_manage_invitations"] is False
    assert ROLE_PERMISSIONS["data_lead"]["can_use_metric_studio"] is True
    assert ROLE_PERMISSIONS["member"]["can_use_data_assistant"] is True
    assert ROLE_PERMISSIONS["member"]["can_use_metric_studio"] is False


async def _add_user(async_session, user_id: int, email: str) -> UserModel:
    user = UserModel(
        id=user_id,
        email=email,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(user)
    await async_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_workspace_makes_creator_admin(async_session):
    organization = await create_organization(async_session, 1, "Acme Analytics", None)

    membership = await get_membership(async_session, 1, organization.id)
    assert organization.slug == "acme-analytics"
    assert membership is not None
    assert membership.role == "admin"


@pytest.mark.asyncio
async def test_invitation_accept_creates_scoped_membership(async_session):
    user = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(
        async_session, organization.id, 1, "member", user.email, "http://localhost:3000"
    )

    raw_token = invitation.invite_url.rsplit("/", 1)[-1]
    accepted = await accept_invitation(async_session, raw_token, user)

    assert accepted.id == organization.id
    assert accepted.role == "member"
    assert await get_membership(async_session, user.id, organization.id)


@pytest.mark.asyncio
async def test_invitation_rejects_wrong_email(async_session):
    user = await _add_user(async_session, 2, "wrong@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(
        async_session, organization.id, 1, "member", "expected@company.com", "http://localhost:3000"
    )

    with pytest.raises(PermissionError, match="another email"):
        await accept_invitation(async_session, invitation.invite_url.rsplit("/", 1)[-1], user)


@pytest.mark.asyncio
async def test_last_admin_cannot_be_removed(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="last Workspace Admin"):
        await remove_member(async_session, organization.id, 1, 1)


@pytest.mark.asyncio
async def test_member_cannot_remove_another_member(async_session):
    member = await _add_user(async_session, 2, "member@company.com")
    target = await _add_user(async_session, 3, "target@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add_all(
        [
            OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"),
            OrganizationMemberModel(org_id=organization.id, user_id=target.id, role="member"),
        ]
    )
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await remove_member(async_session, organization.id, member.id, target.id)


@pytest.mark.asyncio
async def test_expired_invitation_is_rejected(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(async_session, organization.id, 1, "member", None, "http://localhost:3000")
    record = await async_session.scalar(
        select(OrganizationInvitationModel).where(OrganizationInvitationModel.id == invitation.id)
    )
    record.expires_at = datetime.now(UTC) - timedelta(days=1)
    await async_session.commit()

    with pytest.raises(ValueError, match="expired"):
        await accept_invitation(
            async_session, invitation.invite_url.rsplit("/", 1)[-1], await async_session.get(UserModel, 1)
        )


@pytest.mark.asyncio
async def test_list_members_returns_workspace_members(async_session):
    user = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=user.id, role="member"))
    await async_session.commit()

    members = await list_members(async_session, organization.id)
    assert {member.user_id for member in members} == {1, 2}
