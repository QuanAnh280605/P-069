"""Tests for the server-sent notification event stream."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.db import NotificationModel
from src.services.notification_bus import clear_subscribers, publish
from src.services.notification_stream import notification_event_stream


def _factory(async_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to the test session's engine."""
    return async_sessionmaker(bind=async_session.bind, expire_on_commit=False)


@pytest.mark.asyncio
async def test_stream_sends_snapshot_then_pushes_updates(async_session) -> None:
    """Connecting yields the current snapshot; publishes push fresh ones."""
    async_session.add(NotificationModel(recipient_id=1, type="metric_request_submitted", title="T1", body="Doanh thu"))
    await async_session.commit()

    clear_subscribers()
    stream = notification_event_stream(1, _factory(async_session))
    try:
        first = await anext(stream)
        assert first.startswith("data: ")
        assert "T1" in first
        assert '"unread_count":1' in first

        async_session.add(NotificationModel(recipient_id=1, type="metric_request_rejected", title="T2", body="AOV"))
        await async_session.commit()
        publish([1])

        second = await anext(stream)
        assert "T2" in second
        assert '"unread_count":2' in second
    finally:
        await stream.aclose()
        clear_subscribers()
