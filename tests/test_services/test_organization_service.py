"""Behavior tests for Workspace membership and invitation seams."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.models.db import OrganizationInvitationModel, OrganizationMemberModel, OrganizationModel, UserModel
from src.services.organization_service import (
    _MEMBERSHIP_CACHE,
    ROLE_PERMISSIONS,
    WORKSPACE_ROLES,
    accept_invitation,
    change_member_role,
    create_invitation,
    create_organization,
    get_membership,
    invalidate_membership_cache,
    list_members,
    list_organizations,
    provision_personal_workspace,
    remove_member,
    require_permission,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _add_user(async_session, user_id: int, email: str) -> UserModel:
    user = UserModel(
        id=user_id,
        email=email,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        hashed_password="hash",
        status="active",
    )
    async_session.add(user)
    await async_session.commit()
    return user


# ---------------------------------------------------------------------------
# 1. Target Permission Matrix
# ---------------------------------------------------------------------------


def test_workspace_roles_include_admin():
    assert WORKSPACE_ROLES == frozenset({"admin", "data_lead", "member"})


def test_admin_permissions_match_matrix():
    assert ROLE_PERMISSIONS["admin"] == {
        "can_manage_members": True,
        "can_manage_invitations": True,
        "can_manage_schema": False,
        "can_approve_metrics": False,
        "can_submit_metric": False,
        "can_manage_metrics": False,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": False,
        "can_view_pending_metrics": False,
    }


def test_data_lead_permissions_match_matrix():
    assert ROLE_PERMISSIONS["data_lead"] == {
        "can_manage_members": False,
        "can_manage_invitations": False,
        "can_manage_schema": True,
        "can_approve_metrics": True,
        "can_submit_metric": True,
        "can_manage_metrics": True,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": True,
        "can_view_pending_metrics": True,
    }


def test_member_permissions_match_matrix():
    assert ROLE_PERMISSIONS["member"] == {
        "can_manage_members": False,
        "can_manage_invitations": False,
        "can_manage_schema": False,
        "can_approve_metrics": False,
        "can_submit_metric": True,
        "can_manage_metrics": False,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": False,
        "can_view_pending_metrics": False,
    }


def test_can_create_metrics_removed_from_matrix():
    for role_perms in ROLE_PERMISSIONS.values():
        assert "can_create_metrics" not in role_perms


def test_each_role_has_exactly_11_permissions():
    for role, perms in ROLE_PERMISSIONS.items():
        assert len(perms) == 11, f"{role} has {len(perms)} permissions, expected 11"


# ---------------------------------------------------------------------------
# 2. Creator-as-admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workspace_makes_creator_admin(async_session):
    organization = await create_organization(async_session, 1, "Acme Analytics", None)

    membership = await get_membership(async_session, 1, organization.id)
    assert organization.slug == "acme-analytics"
    assert membership is not None
    assert membership.role == "admin"


# ---------------------------------------------------------------------------
# 3. Admin-only member/invitation management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invitation_accept_creates_scoped_membership(async_session):
    user = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(async_session, organization.id, 1, "member", "http://localhost:3000")

    raw_token = invitation.invite_url.rsplit("/", 1)[-1]
    accepted = await accept_invitation(async_session, raw_token, user)

    assert accepted.id == organization.id
    assert accepted.role == "member"
    assert await get_membership(async_session, user.id, organization.id)


async def test_admin_can_change_member_role(async_session):
    member = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    await async_session.commit()

    await change_member_role(async_session, organization.id, 1, member.id, "data_lead")

    promoted = await get_membership(async_session, member.id, organization.id)
    assert promoted is not None
    assert promoted.role == "data_lead"


@pytest.mark.asyncio
async def test_data_lead_cannot_change_member_role(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    data_lead = await _add_user(async_session, 3, "dl@company.com")
    member = await _add_user(async_session, 4, "member@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add_all(
        [
            OrganizationMemberModel(org_id=organization.id, user_id=data_lead.id, role="data_lead"),
            OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"),
        ]
    )
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await change_member_role(async_session, organization.id, data_lead.id, member.id, "data_lead")


@pytest.mark.asyncio
async def test_member_cannot_change_member_role(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    member1 = await _add_user(async_session, 3, "m1@company.com")
    member2 = await _add_user(async_session, 4, "m2@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add_all(
        [
            OrganizationMemberModel(org_id=organization.id, user_id=member1.id, role="member"),
            OrganizationMemberModel(org_id=organization.id, user_id=member2.id, role="member"),
        ]
    )
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await change_member_role(async_session, organization.id, member1.id, member2.id, "data_lead")


@pytest.mark.asyncio
async def test_admin_can_remove_member(async_session):
    member = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    await async_session.commit()

    await remove_member(async_session, organization.id, 1, member.id)

    assert await get_membership(async_session, member.id, organization.id) is None


@pytest.mark.asyncio
async def test_data_lead_cannot_remove_member(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    data_lead = await _add_user(async_session, 3, "dl@company.com")
    member = await _add_user(async_session, 4, "member@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add_all(
        [
            OrganizationMemberModel(org_id=organization.id, user_id=data_lead.id, role="data_lead"),
            OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"),
        ]
    )
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await remove_member(async_session, organization.id, data_lead.id, member.id)


@pytest.mark.asyncio
async def test_member_cannot_remove_another_member(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    member1 = await _add_user(async_session, 3, "m1@company.com")
    member2 = await _add_user(async_session, 4, "m2@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add_all(
        [
            OrganizationMemberModel(org_id=organization.id, user_id=member1.id, role="member"),
            OrganizationMemberModel(org_id=organization.id, user_id=member2.id, role="member"),
        ]
    )
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await remove_member(async_session, organization.id, member1.id, member2.id)


@pytest.mark.asyncio
async def test_admin_can_create_invitation(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(async_session, organization.id, 1, "member", "http://localhost:3000")
    assert invitation.role == "member"
    assert invitation.invite_url is not None


@pytest.mark.asyncio
async def test_data_lead_cannot_create_invitation(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    data_lead = await _add_user(async_session, 3, "dl@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=data_lead.id, role="data_lead"))
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await create_invitation(async_session, organization.id, data_lead.id, "member", "http://localhost:3000")


@pytest.mark.asyncio
async def test_member_cannot_create_invitation(async_session):
    admin_user = await _add_user(async_session, 2, "admin@company.com")
    member = await _add_user(async_session, 3, "member@company.com")
    organization = await create_organization(async_session, admin_user.id, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    await async_session.commit()

    with pytest.raises(PermissionError, match="permission"):
        await create_invitation(async_session, organization.id, member.id, "member", "http://localhost:3000")


@pytest.mark.asyncio
async def test_create_invitation_rejects_invalid_role(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="Invalid invitation role"):
        await create_invitation(async_session, organization.id, 1, "superadmin", "http://localhost:3000")


# ---------------------------------------------------------------------------
# 4. Last-admin protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_admin_cannot_be_removed(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="last Workspace Admin"):
        await remove_member(async_session, organization.id, 1, 1)


@pytest.mark.asyncio
async def test_last_admin_cannot_be_demoted(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="last Workspace Admin"):
        await change_member_role(async_session, organization.id, 1, 1, "member")


@pytest.mark.asyncio
async def test_admin_can_demote_another_admin_when_multiple_exist(async_session):
    admin2 = await _add_user(async_session, 2, "admin2@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=admin2.id, role="admin"))
    await async_session.commit()

    await change_member_role(async_session, organization.id, 1, admin2.id, "member")

    demoted = await get_membership(async_session, admin2.id, organization.id)
    assert demoted.role == "member"


@pytest.mark.asyncio
async def test_admin_can_remove_another_admin_when_multiple_exist(async_session):
    admin2 = await _add_user(async_session, 2, "admin2@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=admin2.id, role="admin"))
    await async_session.commit()

    await remove_member(async_session, organization.id, 1, admin2.id)

    assert await get_membership(async_session, admin2.id, organization.id) is None


@pytest.mark.asyncio
async def test_self_demotion_of_last_admin_is_blocked(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="last Workspace Admin"):
        await change_member_role(async_session, organization.id, 1, 1, "data_lead")


@pytest.mark.asyncio
async def test_self_removal_of_last_admin_is_blocked(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")

    with pytest.raises(ValueError, match="last Workspace Admin"):
        await remove_member(async_session, organization.id, 1, 1)


# ---------------------------------------------------------------------------
# 5. Invitation acceptance with admin role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_invitation_is_rejected(async_session):
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(async_session, organization.id, 1, "member", "http://localhost:3000")
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


# ---------------------------------------------------------------------------
# 5b. Personal Workspace provisioning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_organizations_repairs_legacy_user(async_session):
    """A legacy user with zero memberships is repaired with a personal Workspace."""
    user = await _add_user(async_session, 99, "legacy@company.com")

    result = await list_organizations(async_session, user.id)

    assert len(result) == 1
    assert result[0].name == "Personal Workspace"
    assert result[0].role == "admin"
    # Idempotent: a second listing does not create a second Workspace.
    result2 = await list_organizations(async_session, user.id)
    assert len(result2) == 1


@pytest.mark.asyncio
async def test_provision_personal_workspace_idempotent(async_session):
    """Provisioning twice for the same user yields one membership and one Workspace."""
    user = await _add_user(async_session, 77, "idem@company.com")

    first = await provision_personal_workspace(async_session, user.id)
    second = await provision_personal_workspace(async_session, user.id)

    assert first.org_id == second.org_id
    memberships = list(
        (await async_session.execute(select(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user.id))).scalars().all()
    )
    assert len(memberships) == 1
    orgs = list(
        (await async_session.execute(select(OrganizationModel).where(OrganizationModel.id == memberships[0].org_id))).scalars().all()
    )
    assert len(orgs) == 1


@pytest.mark.asyncio
async def test_provision_personal_workspace_returns_existing_membership(async_session):
    """Provisioning does not create a second Workspace when one already exists."""
    user = await _add_user(async_session, 66, "existing@company.com")
    organization = await create_organization(async_session, user.id, "Acme", "acme")

    membership = await provision_personal_workspace(async_session, user.id)

    assert membership.org_id == organization.id
    memberships = list(
        (await async_session.execute(select(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user.id))).scalars().all()
    )
    assert len(memberships) == 1


# ---------------------------------------------------------------------------
# 6. Cache invalidation after mutations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_invalidated_after_role_change(async_session):
    member = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    await async_session.commit()

    _MEMBERSHIP_CACHE[(member.id, organization.id)] = (
        organization,
        OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"),
        9999999999.0,
    )

    await change_member_role(async_session, organization.id, 1, member.id, "data_lead")

    assert (member.id, organization.id) not in _MEMBERSHIP_CACHE


@pytest.mark.asyncio
async def test_cache_invalidated_after_member_removal(async_session):
    member = await _add_user(async_session, 2, "member@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"))
    await async_session.commit()

    _MEMBERSHIP_CACHE[(member.id, organization.id)] = (
        organization,
        OrganizationMemberModel(org_id=organization.id, user_id=member.id, role="member"),
        9999999999.0,
    )

    await remove_member(async_session, organization.id, 1, member.id)

    assert (member.id, organization.id) not in _MEMBERSHIP_CACHE


@pytest.mark.asyncio
async def test_cache_invalidated_after_invitation_acceptance(async_session):
    user = await _add_user(async_session, 2, "new@company.com")
    organization = await create_organization(async_session, 1, "Acme", "acme")
    invitation = await create_invitation(async_session, organization.id, 1, "member", "http://localhost:3000")
    raw_token = invitation.invite_url.rsplit("/", 1)[-1]

    await accept_invitation(async_session, raw_token, user)

    assert (user.id, organization.id) not in _MEMBERSHIP_CACHE


@pytest.mark.asyncio
async def test_cache_invalidated_after_organization_creation(async_session):
    _MEMBERSHIP_CACHE[(1, None)] = (
        None,
        None,
        9999999999.0,
    )

    await create_organization(async_session, 1, "New Workspace", None)

    assert (1, None) not in _MEMBERSHIP_CACHE


def test_invalidate_membership_cache_evicts_target_user():
    _MEMBERSHIP_CACHE[(1, 10)] = (None, None, 9999999999.0)
    _MEMBERSHIP_CACHE[(1, 20)] = (None, None, 9999999999.0)
    _MEMBERSHIP_CACHE[(2, 10)] = (None, None, 9999999999.0)

    invalidate_membership_cache(user_id=1)

    assert (1, 10) not in _MEMBERSHIP_CACHE
    assert (1, 20) not in _MEMBERSHIP_CACHE
    assert (2, 10) in _MEMBERSHIP_CACHE

    _MEMBERSHIP_CACHE.clear()


def test_invalidate_membership_cache_clears_all_when_no_user():
    _MEMBERSHIP_CACHE[(1, 10)] = (None, None, 9999999999.0)
    _MEMBERSHIP_CACHE[(2, 10)] = (None, None, 9999999999.0)

    invalidate_membership_cache()

    assert len(_MEMBERSHIP_CACHE) == 0


# ---------------------------------------------------------------------------
# 7. require_permission with new matrix
# ---------------------------------------------------------------------------


def test_require_permission_passes_for_admin_manage_members():
    membership = OrganizationMemberModel(role="admin")
    require_permission(membership, "can_manage_members")


def test_require_permission_blocks_data_lead_manage_members():
    membership = OrganizationMemberModel(role="data_lead")
    with pytest.raises(PermissionError):
        require_permission(membership, "can_manage_members")


def test_require_permission_blocks_member_manage_members():
    membership = OrganizationMemberModel(role="member")
    with pytest.raises(PermissionError):
        require_permission(membership, "can_manage_members")


def test_require_permission_passes_for_data_lead_manage_schema():
    membership = OrganizationMemberModel(role="data_lead")
    require_permission(membership, "can_manage_schema")


def test_require_permission_blocks_admin_manage_schema():
    membership = OrganizationMemberModel(role="admin")
    with pytest.raises(PermissionError):
        require_permission(membership, "can_manage_schema")


def test_require_permission_passes_for_data_lead_approve_metrics():
    membership = OrganizationMemberModel(role="data_lead")
    require_permission(membership, "can_approve_metrics")


def test_require_permission_blocks_admin_approve_metrics():
    membership = OrganizationMemberModel(role="admin")
    with pytest.raises(PermissionError):
        require_permission(membership, "can_approve_metrics")


def test_require_permission_blocks_member_approve_metrics():
    membership = OrganizationMemberModel(role="member")
    with pytest.raises(PermissionError):
        require_permission(membership, "can_approve_metrics")


def test_all_roles_can_query():
    for role in ("admin", "data_lead", "member"):
        membership = OrganizationMemberModel(role=role)
        require_permission(membership, "can_query")
