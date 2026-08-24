"""API tests for the per-notification read endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import NotificationModel, UserModel


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


async def _seed(async_session: AsyncSession, recipient_id: int, title: str) -> NotificationModel:
    notification = NotificationModel(
        recipient_id=recipient_id, type="metric_request_approved", title=title, body="Doanh thu"
    )
    async_session.add(notification)
    await async_session.commit()
    return notification


@pytest.mark.asyncio
async def test_read_single_notification_clears_only_that_item(
    client: AsyncClient, auth_headers: dict[str, str], async_session: AsyncSession
) -> None:
    first = await _seed(async_session, 1, "Đã duyệt")
    await _seed(async_session, 1, "Đã gửi")

    response = await client.post(f"/api/v1/notifications/{first.id}/read", headers=auth_headers)

    assert response.status_code == 204
    listed = await client.get("/api/v1/notifications", headers=auth_headers)
    assert listed.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_read_notification_of_another_user_returns_404(
    client: AsyncClient, auth_headers: dict[str, str], async_session: AsyncSession
) -> None:
    foreign = await _seed(async_session, 2, "Yêu cầu mới")

    response = await client.post(f"/api/v1/notifications/{foreign.id}/read", headers=auth_headers)

    assert response.status_code == 404
