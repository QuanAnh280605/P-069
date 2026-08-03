"""Tests cho API routes — Flow 1 endpoints."""

import pytest

from src.api.auth import create_access_token
from src.models.db import UserModel


def get_test_headers():
    """Generate auth headers with valid JWT token for test user."""
    dummy_user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    token = create_access_token(dummy_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health(client):
    """Health check endpoint phải trả về 200 và status=ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_status(client):
    """Status endpoint phải trả về 200 và pipeline đúng."""
    headers = get_test_headers()
    response = await client.get("/api/v1/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "pipeline" in data


@pytest.mark.asyncio
async def test_generate_requires_db_id(client):
    """POST /semantic/generate thiếu db_id phải trả về 422 Validation Error."""
    headers = get_test_headers()
    response = await client.post("/api/v1/semantic/generate", json={}, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_invalid_format(client):
    """Export với format không hợp lệ phải trả về 400."""
    headers = get_test_headers()
    response = await client.get("/api/v1/semantic/1/export?format=csv", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_metric_requires_fields(client):
    """POST metric thiếu field phải trả về 422."""
    headers = get_test_headers()
    response = await client.post("/api/v1/semantic/1/metric", json={"name": "test"}, headers=headers)
    assert response.status_code == 422
