"""Metric-request workflow and in-app notification persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    ChatMessageModel,
    ChatSessionModel,
    MetricRequestModel,
    NotificationModel,
    OrganizationMemberModel,
    SemanticDatabaseModel,
)
from src.models.metric_definition import MetricDefinition
from src.services.notification_bus import publish
from src.services.semantic_service import approve_metric, create_metric


class MetricRequestError(ValueError):
    """Raised when a metric request cannot be created or reviewed."""


async def create_metric_request(
    db: AsyncSession, db_id: int, requester_id: int, assistant_message_id: str, suggestion_index: int
) -> MetricRequestModel:
    """Create a request from one immutable assistant suggestion."""
    suggestion = await _owned_suggestion(db, db_id, requester_id, assistant_message_id, suggestion_index)
    await _reject_duplicate_pending(db, db_id, requester_id, assistant_message_id, suggestion_index)
    request = MetricRequestModel(
        db_id=db_id,
        requester_id=requester_id,
        assistant_message_id=assistant_message_id,
        suggestion_index=suggestion_index,
        definition=suggestion,
    )
    db.add(request)
    await db.flush()
    recipients = await _notify_data_leads(db, db_id, request)
    await db.commit()
    await db.refresh(request)
    publish(recipients)
    return request


async def _reject_duplicate_pending(
    db: AsyncSession, db_id: int, requester_id: int, message_id: str, index: int
) -> None:
    """Refuse a resubmission while the same suggestion is pending or approved."""
    stmt = select(MetricRequestModel.status).where(
        MetricRequestModel.db_id == db_id,
        MetricRequestModel.requester_id == requester_id,
        MetricRequestModel.assistant_message_id == message_id,
        MetricRequestModel.suggestion_index == index,
        MetricRequestModel.status.in_(["pending", "approved"]),
    )
    status = (await db.execute(stmt)).scalar_one_or_none()
    if status == "pending":
        raise MetricRequestError("Metric request already pending review")
    if status == "approved":
        raise MetricRequestError("Metric request already approved")


async def _owned_suggestion(db: AsyncSession, db_id: int, user_id: int, message_id: str, index: int) -> dict:
    """Load one suggestion only when its assistant message belongs to the requester."""
    stmt = (
        select(ChatMessageModel)
        .join(ChatSessionModel)
        .where(ChatMessageModel.id == message_id, ChatSessionModel.user_id == user_id, ChatSessionModel.db_id == db_id)
    )
    message = (await db.execute(stmt)).scalar_one_or_none()
    metadata = message.metadata_json if message and isinstance(message.metadata_json, dict) else {}
    suggestions = metadata.get("suggestions") if metadata.get("suggestion_action") == "submit_metric_request" else None
    if not isinstance(suggestions, list) or index >= len(suggestions):
        raise MetricRequestError("Metric suggestion not found")
    item = suggestions[index]
    if not isinstance(item, dict) or not isinstance(item.get("definition"), dict):
        raise MetricRequestError("Metric suggestion is invalid")
    return MetricDefinition.model_validate(item["definition"]).model_dump(mode="json")


async def list_metric_requests(
    db: AsyncSession, db_id: int, user_id: int, is_data_lead: bool
) -> list[MetricRequestModel]:
    """List workspace requests for a lead or only owned requests for a Member."""
    stmt = select(MetricRequestModel).where(MetricRequestModel.db_id == db_id)
    if not is_data_lead:
        stmt = stmt.where(MetricRequestModel.requester_id == user_id)
    stmt = stmt.order_by(MetricRequestModel.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def approve_metric_request(
    db: AsyncSession, request_id: int, reviewer_id: int, definition: MetricDefinition | None, note: str | None
) -> MetricRequestModel:
    """Create and approve the reviewed metric atomically."""
    request = await _pending_request(db, request_id)
    chosen = definition or MetricDefinition.model_validate(request.definition)
    metric = await create_metric(
        db, request.db_id, {"definition": chosen.model_dump(mode="json"), "source": "ai"}, reviewer_id
    )
    await approve_metric(db, metric.id, reviewer_id)
    request.status, request.reviewed_by, request.review_note = "approved", reviewer_id, note
    request.metric_id, request.reviewed_at = metric.id, datetime.now(UTC)
    await _notify_requester(db, request, "metric_request_approved", "Metric request đã được duyệt")
    await db.commit()
    await db.refresh(request)
    publish([request.requester_id])
    return request


async def reject_metric_request(
    db: AsyncSession, request_id: int, reviewer_id: int, note: str | None
) -> MetricRequestModel:
    """Reject a pending request and notify its requester."""
    request = await _pending_request(db, request_id)
    request.status, request.reviewed_by, request.review_note = "rejected", reviewer_id, note
    request.reviewed_at = datetime.now(UTC)
    await _notify_requester(db, request, "metric_request_rejected", "Metric request đã bị từ chối")
    await db.commit()
    await db.refresh(request)
    publish([request.requester_id])
    return request


async def _pending_request(db: AsyncSession, request_id: int) -> MetricRequestModel:
    """Load one request that is still awaiting review."""
    request = await db.get(MetricRequestModel, request_id, with_for_update=True)
    if request is None or request.status != "pending":
        raise MetricRequestError("Pending metric request not found")
    return request


async def _notify_data_leads(db: AsyncSession, db_id: int, request: MetricRequestModel) -> list[int]:
    """Create a notification for every current Data Lead in the workspace."""
    stmt = (
        select(OrganizationMemberModel.user_id)
        .join(SemanticDatabaseModel, SemanticDatabaseModel.org_id == OrganizationMemberModel.org_id)
        .where(SemanticDatabaseModel.id == db_id, OrganizationMemberModel.role == "data_lead")
    )
    recipients = list((await db.execute(stmt)).scalars())
    for recipient_id in recipients:
        db.add(
            NotificationModel(
                recipient_id=recipient_id,
                type="metric_request_submitted",
                title="Có yêu cầu metric mới",
                body=_metric_name(request),
                metric_request_id=request.id,
            )
        )
    return recipients


async def _notify_requester(db: AsyncSession, request: MetricRequestModel, kind: str, title: str) -> None:
    """Notify a Member after the Data Lead resolves their request."""
    db.add(
        NotificationModel(
            recipient_id=request.requester_id,
            type=kind,
            title=title,
            body=_metric_name(request),
            metric_request_id=request.id,
        )
    )


def _metric_name(request: MetricRequestModel) -> str:
    """Extract a safe display name from a stored metric definition."""
    return str(request.definition.get("metric", {}).get("name", "Metric"))


async def list_notifications(db: AsyncSession, user_id: int) -> tuple[list[NotificationModel], int]:
    """Return recent notifications and an unread count for one user."""
    stmt = (
        select(NotificationModel)
        .where(NotificationModel.recipient_id == user_id)
        .order_by(NotificationModel.created_at.desc())
        .limit(50)
    )
    items = list((await db.execute(stmt)).scalars().all())
    unread = await db.scalar(
        select(func.count())
        .select_from(NotificationModel)
        .where(NotificationModel.recipient_id == user_id, NotificationModel.read_at.is_(None))
    )
    return items, int(unread or 0)


async def mark_notifications_read(db: AsyncSession, user_id: int) -> None:
    """Mark all current notifications as read."""
    items = (
        await db.execute(
            select(NotificationModel).where(
                NotificationModel.recipient_id == user_id, NotificationModel.read_at.is_(None)
            )
        )
    ).scalars()
    for item in items:
        item.read_at = datetime.now(UTC)
    await db.commit()


async def mark_notification_read(db: AsyncSession, user_id: int, notification_id: int) -> NotificationModel | None:
    """Mark one owned notification as read; return None when it is not found."""
    item = (
        await db.execute(
            select(NotificationModel).where(
                NotificationModel.id == notification_id,
                NotificationModel.recipient_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if item is not None and item.read_at is None:
        item.read_at = datetime.now(UTC)
        await db.commit()
    return item
