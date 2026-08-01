"""Tests cho API routes — Flow 1 endpoints."""
import pytest


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
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "pipeline" in data


@pytest.mark.asyncio
async def test_generate_requires_db_id(client):
    """POST /semantic/generate thiếu db_id phải trả về 422 Validation Error."""
    response = await client.post("/api/v1/semantic/generate", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_invalid_format(client):
    """Export với format không hợp lệ phải trả về 400."""
    response = await client.get("/api/v1/semantic/1/export?format=csv")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_metric_requires_fields(client):
    """POST metric thiếu field phải trả về 422."""
    response = await client.post("/api/v1/semantic/1/metric", json={"name": "test"})
    assert response.status_code == 422
