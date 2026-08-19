"""Workspace membership, invitation, and organization-scoped authorization services."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    OrganizationAuditLogModel,
    OrganizationInvitationModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from src.models.schemas import (
    OrganizationInvitePreviewResponse,
    OrganizationInviteResponse,
    OrganizationMemberResponse,
    OrganizationSummaryResponse,
)

ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {
        "can_manage_members": True,
        "can_manage_invitations": True,
        "can_manage_schema": False,
        "can_create_metrics": False,
        "can_approve_metrics": False,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": False,
        "can_view_pending_metrics": True,
    },
    "data_lead": {
        "can_manage_members": False,
        "can_manage_invitations": False,
        "can_manage_schema": True,
        "can_create_metrics": True,
        "can_approve_metrics": True,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": True,
        "can_view_pending_metrics": True,
    },
    "member": {
        "can_manage_members": False,
        "can_manage_invitations": False,
        "can_manage_schema": False,
        "can_create_metrics": False,
        "can_approve_metrics": False,
        "can_query": True,
        "can_use_chat": True,
        "can_use_data_assistant": True,
        "can_use_metric_studio": False,
        "can_view_pending_metrics": False,
    },
}
INVITE_ROLES = {"member", "data_lead"}


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive datetime values before comparison."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _slugify(value: str) -> str:
    """Create a URL-safe Workspace slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:120] or "workspace"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _audit(
    db: AsyncSession,
    org_id: int,
    actor_id: int | None,
    action: str,
    target_user_id: int | None = None,
    target_invitation_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        OrganizationAuditLogModel(
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            target_user_id=target_user_id,
            target_invitation_id=target_invitation_id,
            metadata_json=metadata,
        )
    )


async def get_membership(db: AsyncSession, user_id: int, org_id: int) -> OrganizationMemberModel | None:
    """Return a user's membership in one Workspace."""
    stmt = select(OrganizationMemberModel).where(
        OrganizationMemberModel.user_id == user_id,
        OrganizationMemberModel.org_id == org_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def resolve_membership(
    db: AsyncSession, user_id: int, requested_org_id: int | None
) -> tuple[OrganizationModel, OrganizationMemberModel]:
    """Resolve the active Workspace, requiring explicit selection when ambiguous."""
    if requested_org_id is not None:
        membership = await get_membership(db, user_id, requested_org_id)
        if membership is None:
            raise PermissionError("User is not a member of this Workspace")
        organization = await db.get(OrganizationModel, requested_org_id)
        if organization is None:
            raise PermissionError("Workspace not found")
        return organization, membership
    stmt = select(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user_id)
    memberships = list((await db.execute(stmt)).scalars().all())
    if not memberships:
        organization = await create_organization(db, user_id, "Personal Workspace", f"user-{user_id}")
        membership = await get_membership(db, user_id, organization.id)
        return organization, membership
    if len(memberships) != 1:
        raise ValueError("X-Organization-ID is required when user belongs to multiple Workspaces")
    organization = await db.get(OrganizationModel, memberships[0].org_id)
    if organization is None:
        raise PermissionError("Workspace not found")
    return organization, memberships[0]


def require_permission(membership: OrganizationMemberModel, permission: str) -> None:
    """Raise when a Workspace membership lacks a named permission."""
    if not ROLE_PERMISSIONS.get(membership.role, {}).get(permission, False):
        raise PermissionError("Insufficient Workspace permission")


async def create_organization(db: AsyncSession, user_id: int, name: str, slug: str | None) -> OrganizationModel:
    """Create a Workspace and make the creator its Admin."""
    base_slug = _slugify(slug or name)
    candidate = base_slug
    suffix = 2
    while await db.scalar(select(OrganizationModel.id).where(OrganizationModel.slug == candidate)):
        candidate = f"{base_slug[: max(1, 120 - len(str(suffix)) - 1)]}-{suffix}"
        suffix += 1
    organization = OrganizationModel(name=name.strip(), slug=candidate, created_by=user_id)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMemberModel(org_id=organization.id, user_id=user_id, role="admin"))
    await db.commit()
    await db.refresh(organization)
    return organization


async def list_organizations(db: AsyncSession, user_id: int) -> list[OrganizationSummaryResponse]:
    """List Workspaces and permissions available to a user."""
    stmt = (
        select(OrganizationModel, OrganizationMemberModel)
        .join(OrganizationMemberModel, OrganizationMemberModel.org_id == OrganizationModel.id)
        .where(OrganizationMemberModel.user_id == user_id)
        .order_by(OrganizationModel.created_at, OrganizationModel.id)
    )
    return [_organization_response(org, member) for org, member in (await db.execute(stmt)).all()]


def _organization_response(org: OrganizationModel, member: OrganizationMemberModel) -> OrganizationSummaryResponse:
    return OrganizationSummaryResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role=member.role,
        permissions=ROLE_PERMISSIONS[member.role],
        created_at=org.created_at,
    )


async def list_members(db: AsyncSession, org_id: int) -> list[OrganizationMemberResponse]:
    """List Workspace members with their account details."""
    stmt = (
        select(OrganizationMemberModel, UserModel)
        .join(UserModel, UserModel.id == OrganizationMemberModel.user_id)
        .where(OrganizationMemberModel.org_id == org_id)
        .order_by(UserModel.full_name, UserModel.email)
    )
    return [_member_response(member, user) for member, user in (await db.execute(stmt)).all()]


def _member_response(member: OrganizationMemberModel, user: UserModel) -> OrganizationMemberResponse:
    return OrganizationMemberResponse(
        user_id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=member.role,
        joined_at=member.joined_at,
    )


async def change_member_role(db: AsyncSession, org_id: int, actor_id: int, user_id: int, role: str) -> None:
    """Change a member role while preserving the last Admin."""
    await _lock_workspace_admins(db, org_id)
    actor = await get_membership(db, actor_id, org_id)
    if actor is None:
        raise PermissionError("Workspace membership required")
    require_permission(actor, "can_manage_members")
    target = await get_membership(db, user_id, org_id)
    if target is None:
        raise ValueError("Member not found")
    if target.role == "admin" and role != "admin" and await _admin_count(db, org_id) <= 1:
        raise ValueError("Cannot demote the last Workspace Admin")
    target.role = role
    _audit(db, org_id, actor_id, "member_role_changed", user_id, metadata={"role": role})
    await db.commit()


async def remove_member(db: AsyncSession, org_id: int, actor_id: int, user_id: int) -> None:
    """Remove a member according to Workspace role protections."""
    await _lock_workspace_admins(db, org_id)
    actor = await get_membership(db, actor_id, org_id)
    target = await get_membership(db, user_id, org_id)
    if actor is None or target is None:
        raise ValueError("Member not found")
    require_permission(actor, "can_manage_members")
    if target.role == "admin" and actor.role != "admin":
        raise PermissionError("Only Admin can remove an Admin")
    if target.role == "admin" and await _admin_count(db, org_id) <= 1:
        raise ValueError("Cannot remove the last Workspace Admin")
    await db.delete(target)
    _audit(db, org_id, actor_id, "member_removed", user_id)
    await db.commit()


async def _admin_count(db: AsyncSession, org_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(OrganizationMemberModel)
        .where(
            OrganizationMemberModel.org_id == org_id,
            OrganizationMemberModel.role == "admin",
        )
    )
    return int(await db.scalar(stmt) or 0)


async def _lock_workspace_admins(db: AsyncSession, org_id: int) -> None:
    """Serialize membership mutations that can remove the last Admin."""
    stmt = (
        select(OrganizationMemberModel.id)
        .where(OrganizationMemberModel.org_id == org_id, OrganizationMemberModel.role == "admin")
        .with_for_update()
    )
    await db.execute(stmt)


async def create_invitation(
    db: AsyncSession,
    org_id: int,
    actor_id: int,
    role: str,
    invitee_email: str | None,
    frontend_base_url: str,
) -> OrganizationInviteResponse:
    """Create a seven-day, one-time Workspace invitation."""
    actor = await get_membership(db, actor_id, org_id)
    if actor is None:
        raise PermissionError("Workspace membership required")
    require_permission(actor, "can_manage_invitations")
    if role not in INVITE_ROLES:
        raise ValueError("Invalid invitation role")
    raw_token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitationModel(
        org_id=org_id,
        inviter_id=actor_id,
        invitee_email=invitee_email.lower() if invitee_email else None,
        role=role,
        token_hash=_hash_token(raw_token),
        expires_at=_now() + timedelta(days=7),
        status="pending",
    )
    db.add(invitation)
    await db.flush()
    _audit(db, org_id, actor_id, "invitation_created", target_invitation_id=invitation.id)
    await db.commit()
    return OrganizationInviteResponse(
        id=invitation.id,
        org_id=org_id,
        role=role,
        invitee_email=invitation.invitee_email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        invite_url=f"{frontend_base_url.rstrip('/')}/invite/{raw_token}",
    )


async def preview_invitation(db: AsyncSession, raw_token: str) -> OrganizationInvitePreviewResponse:
    """Return public invitation details without exposing the token."""
    invitation = await _get_active_invitation(db, raw_token)
    organization = await db.get(OrganizationModel, invitation.org_id)
    if organization is None:
        raise ValueError("Workspace not found")
    return OrganizationInvitePreviewResponse(
        organization_name=organization.name,
        organization_slug=organization.slug,
        role=invitation.role,
        invitee_email=invitation.invitee_email,
        expires_at=invitation.expires_at,
    )


async def accept_invitation(db: AsyncSession, raw_token: str, user: UserModel) -> OrganizationSummaryResponse:
    """Accept an invitation and create the user's Workspace membership."""
    invitation = await _get_active_invitation(db, raw_token)
    if invitation.invitee_email and invitation.invitee_email.lower() != user.email.lower():
        raise PermissionError("Invitation is restricted to another email address")
    existing = await get_membership(db, user.id, invitation.org_id)
    if existing is not None:
        raise ValueError("User is already a Workspace member")
    member = OrganizationMemberModel(org_id=invitation.org_id, user_id=user.id, role=invitation.role)
    db.add(member)
    invitation.status = "accepted"
    invitation.accepted_by = user.id
    invitation.accepted_at = _now()
    _audit(db, invitation.org_id, user.id, "invitation_accepted", user.id, invitation.id)
    await db.commit()
    organization = await db.get(OrganizationModel, invitation.org_id)
    return _organization_response(organization, member)


async def revoke_invitation(db: AsyncSession, org_id: int, actor_id: int, invitation_id: int) -> None:
    """Revoke a pending Workspace invitation."""
    actor = await get_membership(db, actor_id, org_id)
    if actor is None:
        raise PermissionError("Workspace membership required")
    require_permission(actor, "can_manage_invitations")
    invitation = await db.scalar(
        select(OrganizationInvitationModel).where(
            OrganizationInvitationModel.id == invitation_id,
            OrganizationInvitationModel.org_id == org_id,
        )
    )
    if invitation is None:
        raise ValueError("Invitation not found")
    if invitation.status != "pending":
        raise ValueError("Only pending invitations can be revoked")
    invitation.status = "revoked"
    invitation.revoked_at = _now()
    _audit(db, org_id, actor_id, "invitation_revoked", target_invitation_id=invitation_id)
    await db.commit()


async def list_invitations(db: AsyncSession, org_id: int) -> list[OrganizationInviteResponse]:
    """List active Workspace invitations without exposing raw tokens."""
    stmt = select(OrganizationInvitationModel).where(
        OrganizationInvitationModel.org_id == org_id,
        OrganizationInvitationModel.status == "pending",
    )
    records = list((await db.execute(stmt)).scalars().all())
    now = _now()
    responses = []
    for invitation in records:
        if _as_utc(invitation.expires_at) < now:
            invitation.status = "expired"
            continue
        responses.append(
            OrganizationInviteResponse(
                id=invitation.id,
                org_id=invitation.org_id,
                role=invitation.role,
                invitee_email=invitation.invitee_email,
                status=invitation.status,
                expires_at=invitation.expires_at,
            )
        )
    await db.commit()
    return responses


async def _get_active_invitation(db: AsyncSession, raw_token: str) -> OrganizationInvitationModel:
    invitation = await db.scalar(
        select(OrganizationInvitationModel)
        .where(OrganizationInvitationModel.token_hash == _hash_token(raw_token))
        .with_for_update()
    )
    if invitation is None:
        raise ValueError("Invitation not found")
    if invitation.status != "pending":
        raise ValueError("Invitation is no longer active")
    if _as_utc(invitation.expires_at) < _now():
        invitation.status = "expired"
        await db.commit()
        raise ValueError("Invitation has expired")
    return invitation
