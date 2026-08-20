"""Tests for the notification SSE endpoint wiring."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.routes import stream_notifications
from src.models.db import NotificationModel, UserModel


def _user() -> UserModel:
    """Build the seeded test user (id=1) the route authenticates."""
    return UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="analyst",
        status="active",
    )


@pytest.mark.asyncio
async def test_stream_endpoint_serves_sse_snapshot(async_session: AsyncSession, monkeypatch) -> None:
    """The route returns an SSE response wired to the real event generator."""
    async_session.add(NotificationModel(recipient_id=1, type="metric_request_submitted", title="T1", body="Doanh thu"))
    await async_session.commit()
    factory = async_sessionmaker(bind=async_session.bind, expire_on_commit=False)
    monkeypatch.setattr("src.api.routes.get_session_factory", lambda: factory)

    response = await stream_notifications(current_user=_user())

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    first = await anext(response.body_iterator)
    assert first.startswith("data: ")
    assert "T1" in first
    await response.body_iterator.aclose()
