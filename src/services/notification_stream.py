"""Server-sent events streaming notification snapshots to open clients."""

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.schemas import NotificationListResponse, NotificationResponse
from src.services.metric_request_service import list_notifications
from src.services.notification_bus import subscribe, unsubscribe

KEEPALIVE_SECONDS = 15


async def _snapshot_event(user_id: int, session_factory: async_sessionmaker[AsyncSession]) -> str:
    """Render the user's current notifications as one SSE data event."""
    async with session_factory() as db:
        items, unread_count = await list_notifications(db, user_id)
    payload = NotificationListResponse(
        items=[NotificationResponse.model_validate(item) for item in items], unread_count=unread_count
    )
    return f"data: {payload.model_dump_json()}\n\n"


async def notification_event_stream(
    user_id: int, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[str]:
    """Yield the caller's snapshot now and after every published wake-up."""
    queue = subscribe(user_id)
    try:
        yield await _snapshot_event(user_id, session_factory)
        while True:
            try:
                await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield await _snapshot_event(user_id, session_factory)
    finally:
        unsubscribe(user_id, queue)
