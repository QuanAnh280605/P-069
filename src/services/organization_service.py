"""Workspace membership, invitation, and organization-scoped authorization services."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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

WORKSPACE_ROLES = frozenset({"admin", "data_lead", "member"})
INVITE_ROLES = WORKSPACE_ROLES

ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {
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
    },
    "data_lead": {
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
    },
    "member": {
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
    },
}


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


_MEMBERSHIP_CACHE: dict[tuple[int, int | None], tuple[OrganizationModel, OrganizationMemberModel, float]] = {}
_MEMBERSHIP_CACHE_TTL = 60.0


def _is_testing() -> bool:
    import os

    from src.config import get_settings

    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or get_settings().app_env == "test"


def invalidate_membership_cache(user_id: int | None = None) -> None:
    """Evict cached workspace membership entries."""
    if user_id is not None:
        keys_to_del = [k for k in _MEMBERSHIP_CACHE if k[0] == user_id]
        for k in keys_to_del:
            _MEMBERSHIP_CACHE.pop(k, None)
    else:
        _MEMBERSHIP_CACHE.clear()


async def resolve_membership(
    db: AsyncSession, user_id: int, requested_org_id: int | None
) -> tuple[OrganizationModel, OrganizationMemberModel]:
    """Resolve the active Workspace with in-memory caching."""
    now = time.time()
    cache_key = (user_id, requested_org_id)
    if not _is_testing():
        cached = _MEMBERSHIP_CACHE.get(cache_key)
        if cached is not None and now - cached[2] < _MEMBERSHIP_CACHE_TTL:
            return cached[0], cached[1]

    org, member = await _resolve_membership_uncached(db, user_id, requested_org_id)
    if not _is_testing():
        _MEMBERSHIP_CACHE[cache_key] = (org, member, now)
    return org, member


async def _resolve_membership_uncached(
    db: AsyncSession, user_id: int, requested_org_id: int | None
) -> tuple[OrganizationModel, OrganizationMemberModel]:
    """Resolve the active Workspace from database."""
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
        membership = await provision_personal_workspace(db, user_id)
        organization = await db.get(OrganizationModel, membership.org_id)
        if organization is None:
            raise PermissionError("Workspace not found")
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


async def _create_organization_flush(db: AsyncSession, user_id: int, name: str, slug: str | None) -> OrganizationModel:
    """Create a Workspace and admin membership, flushing but not committing."""
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
    await db.flush()
    await db.refresh(organization)
    return organization


async def create_organization(db: AsyncSession, user_id: int, name: str, slug: str | None) -> OrganizationModel:
    """Create a Workspace and make the creator its Admin."""
    organization = await _create_organization_flush(db, user_id, name, slug)
    await db.commit()
    invalidate_membership_cache(user_id)
    return organization


async def _get_any_membership(db: AsyncSession, user_id: int) -> OrganizationMemberModel | None:
    """Return any one Workspace membership for the user, or None."""
    stmt = select(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user_id)
    return (await db.execute(stmt)).scalars().first()


async def provision_personal_workspace(db: AsyncSession, user_id: int) -> OrganizationMemberModel:
    """Idempotently ensure a user has exactly one personal Workspace as Admin.

    Returns the user's existing membership when present. Otherwise creates a
    personal Workspace named "Personal Workspace" with an admin membership and
    commits it within the current transaction. Concurrent calls are serialized
    by the unique (org_id, user_id) membership constraint: a loser raises
    IntegrityError, is rolled back, and reloads the winner's membership instead
    of creating a second Workspace.
    """
    existing = await _get_any_membership(db, user_id)
    if existing is not None:
        return existing
    try:
        organization = await _create_organization_flush(db, user_id, "Personal Workspace", f"user-{user_id}")
        membership = await get_membership(db, user_id, organization.id)
        if membership is None:
            raise RuntimeError("Failed to provision personal Workspace membership")
        await db.commit()
        invalidate_membership_cache(user_id)
        return membership
    except IntegrityError:
        await db.rollback()
        existing = await _get_any_membership(db, user_id)
        if existing is not None:
            return existing
        raise


async def list_organizations(db: AsyncSession, user_id: int) -> list[OrganizationSummaryResponse]:
    """List Workspaces and permissions available to a user.

    A legacy user with zero memberships is repaired by provisioning a personal
    Workspace so the listing is never empty for an authenticated account.
    """
    stmt = (
        select(OrganizationModel, OrganizationMemberModel)
        .join(OrganizationMemberModel, OrganizationMemberModel.org_id == OrganizationModel.id)
        .where(OrganizationMemberModel.user_id == user_id)
        .order_by(OrganizationModel.created_at, OrganizationModel.id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        await provision_personal_workspace(db, user_id)
        rows = (await db.execute(stmt)).all()
    return [_organization_response(org, member) for org, member in rows]


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
    if role not in WORKSPACE_ROLES:
        raise ValueError("Invalid Workspace role")
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
    invalidate_membership_cache(user_id)


async def remove_member(db: AsyncSession, org_id: int, actor_id: int, user_id: int) -> None:
    """Remove a member according to Workspace role protections."""
    await _lock_workspace_admins(db, org_id)
    actor = await get_membership(db, actor_id, org_id)
    target = await get_membership(db, user_id, org_id)
    if actor is None or target is None:
        raise ValueError("Member not found")
    require_permission(actor, "can_manage_members")
    if target.role == "admin" and await _admin_count(db, org_id) <= 1:
        raise ValueError("Cannot remove the last Workspace Admin")
    await db.delete(target)
    _audit(db, org_id, actor_id, "member_removed", user_id)
    await db.commit()
    invalidate_membership_cache(user_id)


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
        expires_at=invitation.expires_at,
    )


async def accept_invitation(db: AsyncSession, raw_token: str, user: UserModel) -> OrganizationSummaryResponse:
    """Accept an invitation and create the user's Workspace membership."""
    invitation = await _get_active_invitation(db, raw_token)
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
    invalidate_membership_cache(user.id)
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
