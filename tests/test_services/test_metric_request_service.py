"""Tests for server-verified metric request suggestions and notifications."""

import pytest
from sqlalchemy import select

from src.models.db import (
    ChatMessageModel,
    ChatSessionModel,
    MetricRequestModel,
    NotificationModel,
    SemanticDatabaseModel,
)
from src.services.metric_request_service import (
    MetricRequestError,
    create_metric_request,
    list_notifications,
    mark_notifications_read,
    reject_metric_request,
)


def _suggestion_metadata() -> dict:
    """Return one canonical suggestion stored in an assistant chat message."""
    return {
        "suggestion_action": "submit_metric_request",
        "suggestions": [
            {
                "definition": {
                    "metric": {
                        "name": "Doanh thu trước thuế",
                        "formula": {"function": "SUM", "expression": "amount"},
                        "base_entity": "orders",
                        "filters": [],
                        "status": "pending_approval",
                        "confidence": "high",
                        "excluded_notes": "",
                    }
                }
            }
        ],
    }


@pytest.mark.asyncio
async def test_request_uses_only_owned_assistant_suggestion(async_session) -> None:
    """Member requests are reconstructed from persisted chat metadata."""
    database = SemanticDatabaseModel(created_by=1, display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_session.add(database)
    await async_session.flush()
    session = ChatSessionModel(id="session-1", user_id=1, db_id=database.id)
    message = ChatMessageModel(
        id="message-1",
        session_id=session.id,
        sequence_no=1,
        sender="assistant",
        content="Proposal",
        metadata_json=_suggestion_metadata(),
    )
    async_session.add_all([session, message])
    await async_session.commit()

    request = await create_metric_request(async_session, database.id, 1, message.id, 0)

    assert request.definition["metric"]["name"] == "Doanh thu trước thuế"
    assert request.status == "pending"


@pytest.mark.asyncio
async def test_request_rejects_message_without_member_action(async_session) -> None:
    """A Member cannot submit arbitrary definitions or Data Lead suggestions."""
    database = SemanticDatabaseModel(created_by=1, display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_session.add(database)
    await async_session.flush()
    session = ChatSessionModel(id="session-2", user_id=1, db_id=database.id)
    message = ChatMessageModel(
        id="message-2",
        session_id=session.id,
        sequence_no=1,
        sender="assistant",
        content="Proposal",
        metadata_json={"suggestions": []},
    )
    async_session.add_all([session, message])
    await async_session.commit()

    with pytest.raises(MetricRequestError, match="Metric suggestion not found"):
        await create_metric_request(async_session, database.id, 1, message.id, 0)


@pytest.mark.asyncio
async def test_duplicate_pending_request_is_rejected(async_session) -> None:
    """Resubmitting the same suggestion while pending sends no duplicate."""
    database = SemanticDatabaseModel(created_by=1, display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_session.add(database)
    await async_session.flush()
    session = ChatSessionModel(id="session-3", user_id=1, db_id=database.id)
    message = ChatMessageModel(
        id="message-3",
        session_id=session.id,
        sequence_no=1,
        sender="assistant",
        content="Proposal",
        metadata_json=_suggestion_metadata(),
    )
    async_session.add_all([session, message])
    await async_session.commit()

    await create_metric_request(async_session, database.id, 1, message.id, 0)
    with pytest.raises(MetricRequestError):
        await create_metric_request(async_session, database.id, 1, message.id, 0)

    stored = (
        (
            await async_session.execute(
                select(MetricRequestModel).where(MetricRequestModel.assistant_message_id == message.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_resubmission_allowed_after_rejection(async_session) -> None:
    """A rejected proposal can be submitted again for another review round."""
    database = SemanticDatabaseModel(created_by=1, display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_session.add(database)
    await async_session.flush()
    session = ChatSessionModel(id="session-4", user_id=1, db_id=database.id)
    message = ChatMessageModel(
        id="message-4",
        session_id=session.id,
        sequence_no=1,
        sender="assistant",
        content="Proposal",
        metadata_json=_suggestion_metadata(),
    )
    async_session.add_all([session, message])
    await async_session.commit()

    first = await create_metric_request(async_session, database.id, 1, message.id, 0)
    first.status = "rejected"
    await async_session.commit()
    second = await create_metric_request(async_session, database.id, 1, message.id, 0)

    assert second.status == "pending"
    assert second.id != first.id


@pytest.mark.asyncio
async def test_reject_notifies_requester_of_rejection(async_session) -> None:
    """Rejecting a request tells the Member the metric was rejected."""
    database = SemanticDatabaseModel(created_by=1, display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_session.add(database)
    await async_session.flush()
    session = ChatSessionModel(id="session-5", user_id=1, db_id=database.id)
    message = ChatMessageModel(
        id="message-5",
        session_id=session.id,
        sequence_no=1,
        sender="assistant",
        content="Proposal",
        metadata_json=_suggestion_metadata(),
    )
    async_session.add_all([session, message])
    await async_session.commit()

    request = await create_metric_request(async_session, database.id, 1, message.id, 0)
    await reject_metric_request(async_session, request.id, 2, "Thiếu điều kiện lọc")

    notification = (
        await async_session.execute(
            select(NotificationModel).where(
                NotificationModel.recipient_id == 1,
                NotificationModel.type == "metric_request_rejected",
            )
        )
    ).scalar_one()
    assert notification.title == "Metric request đã bị từ chối"
    assert notification.body == "Doanh thu trước thuế"


@pytest.mark.asyncio
async def test_notifications_become_read(async_session) -> None:
    """The unread count is cleared by the notification center action."""
    async_session.add(
        NotificationModel(recipient_id=1, type="metric_request_approved", title="Đã duyệt", body="Doanh thu")
    )
    await async_session.commit()

    _, unread = await list_notifications(async_session, 1)
    assert unread == 1
    await mark_notifications_read(async_session, 1)
    _, unread = await list_notifications(async_session, 1)
    assert unread == 0
