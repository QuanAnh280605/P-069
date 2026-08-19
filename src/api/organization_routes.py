"""REST endpoints for Workspace, membership, and invitation management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.config import get_settings
from src.models.db import UserModel
from src.models.schemas import (
    OrganizationCreateRequest,
    OrganizationInviteCreateRequest,
    OrganizationInvitePreviewResponse,
    OrganizationInviteResponse,
    OrganizationMemberResponse,
    OrganizationRoleUpdateRequest,
    OrganizationSummaryResponse,
)
from src.services.database import get_db_session
from src.services.organization_service import (
    ROLE_PERMISSIONS,
    accept_invitation,
    change_member_role,
    create_invitation,
    create_organization,
    list_invitations,
    list_members,
    list_organizations,
    preview_invitation,
    remove_member,
    require_permission,
    resolve_membership,
    revoke_invitation,
)

router = APIRouter(tags=["Organizations"])
OrgHeader = Annotated[int | None, Header(alias="X-Organization-ID")]


def _parse_org_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


def _frontend_app_url(settings: object) -> str:
    """Return the configured frontend URL and reject unsafe production fallbacks."""
    url = str(getattr(settings, "frontend_app_url", "")).strip().rstrip("/")
    if getattr(settings, "app_env", "development") == "production" and not url.startswith("https://"):
        raise ValueError("FRONTEND_APP_URL must be an HTTPS deploy domain in production")
    if not url:
        raise ValueError("FRONTEND_APP_URL is required")
    return url


async def _active_org(db: AsyncSession, user_id: int, org_id: int | None):
    try:
        return await resolve_membership(db, user_id, org_id)
    except (PermissionError, ValueError) as error:
        raise _parse_org_error(error) from error


@router.post("/org", response_model=OrganizationSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: OrganizationCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationSummaryResponse:
    """Create a Workspace and return its Data Lead membership."""
    organization = await create_organization(db, current_user.id, body.name, body.slug)
    _, membership = await resolve_membership(db, current_user.id, organization.id)
    return OrganizationSummaryResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=membership.role,
        permissions=ROLE_PERMISSIONS[membership.role],
        created_at=organization.created_at,
    )


@router.get("/org/my-orgs", response_model=list[OrganizationSummaryResponse])
async def get_my_workspaces(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationSummaryResponse]:
    """List Workspaces available to the authenticated user."""
    return await list_organizations(db, current_user.id)


@router.get("/org/current", response_model=OrganizationSummaryResponse)
async def get_current_workspace(
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationSummaryResponse:
    """Return the selected Workspace and the caller's permissions."""
    organization, membership = await _active_org(db, current_user.id, org_id)
    return OrganizationSummaryResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=membership.role,
        permissions=ROLE_PERMISSIONS[membership.role],
        created_at=organization.created_at,
    )


@router.get("/org/members", response_model=list[OrganizationMemberResponse])
async def get_workspace_members(
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationMemberResponse]:
    """List members visible to any Workspace member."""
    organization, _ = await _active_org(db, current_user.id, org_id)
    return await list_members(db, organization.id)


@router.put("/org/members/{user_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def update_workspace_member(
    user_id: int,
    body: OrganizationRoleUpdateRequest,
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Change a member role; only Data Leads may perform this action."""
    organization, _ = await _active_org(db, current_user.id, org_id)
    try:
        await change_member_role(db, organization.id, current_user.id, user_id, body.role)
    except (PermissionError, ValueError) as error:
        raise _parse_org_error(error) from error


@router.delete("/org/members/{user_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_member(
    user_id: int,
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a member while preserving Workspace protections."""
    organization, _ = await _active_org(db, current_user.id, org_id)
    try:
        await remove_member(db, organization.id, current_user.id, user_id)
    except (PermissionError, ValueError) as error:
        raise _parse_org_error(error) from error


@router.post("/org/invite", response_model=OrganizationInviteResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace_invitation(
    body: OrganizationInviteCreateRequest,
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationInviteResponse:
    """Create a seven-day invitation link."""
    organization, _ = await _active_org(db, current_user.id, org_id)
    try:
        return await create_invitation(
            db,
            organization.id,
            current_user.id,
            body.role,
            _frontend_app_url(get_settings()),
        )
    except (PermissionError, ValueError) as error:
        raise _parse_org_error(error) from error


@router.delete("/org/invite/{invitation_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def revoke_workspace_invitation(
    invitation_id: int,
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke a pending Workspace invitation immediately."""
    organization, _ = await _active_org(db, current_user.id, org_id)
    try:
        await revoke_invitation(db, organization.id, current_user.id, invitation_id)
    except (PermissionError, ValueError) as error:
        raise _parse_org_error(error) from error


@router.get("/org/invites", response_model=list[OrganizationInviteResponse])
async def get_workspace_invitations(
    org_id: OrgHeader = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationInviteResponse]:
    """List pending invitations for Workspace management UI."""
    organization, membership = await _active_org(db, current_user.id, org_id)
    try:
        require_permission(membership, "can_manage_invitations")
    except PermissionError as error:
        raise _parse_org_error(error) from error
    return await list_invitations(db, organization.id)


@router.get("/invite/{token}", response_model=OrganizationInvitePreviewResponse)
async def get_invitation_preview(
    token: str, db: AsyncSession = Depends(get_db_session)
) -> OrganizationInvitePreviewResponse:
    """Inspect an invitation before authentication."""
    try:
        return await preview_invitation(db, token)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/invite/{token}/accept", response_model=OrganizationSummaryResponse)
async def accept_workspace_invitation(
    token: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationSummaryResponse:
    """Accept an invitation for the authenticated user."""
    try:
        return await accept_invitation(db, token, current_user)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
