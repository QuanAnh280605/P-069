"""Integration tests for custom prompt metric generation and Metric CRUD endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.schemas import MetricSuggestionItem


@pytest.fixture
def auth_headers():
    """Create a valid JWT header for the seeded test user (id=1)."""
    user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_generate_metrics_unauthenticated(client: AsyncClient):
    """Unauthenticated request to generate metrics must return 401."""
    res = await client.post("/api/v1/semantic/1/metrics/generate", json={"prompt": "Tỷ lệ đơn hàng"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_generate_metrics_empty_prompt(client: AsyncClient, auth_headers: dict):
    """Empty prompt or whitespace-only prompt must return 422."""
    res = await client.post(
        "/api/v1/semantic/1/metrics/generate",
        json={"prompt": "   "},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_generate_metrics_prompt_too_long(client: AsyncClient, auth_headers: dict):
    """Prompt exceeding 2000 characters must return 422."""
    res = await client.post(
        "/api/v1/semantic/1/metrics/generate",
        json={"prompt": "a" * 2001},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_generate_metrics_db_not_found(client: AsyncClient, auth_headers: dict):
    """Generating metrics on non-existent database must return 404."""
    res = await client.post(
        "/api/v1/semantic/9999/metrics/generate",
        json={"prompt": "Tính doanh thu"},
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
@patch("src.api.routes.generate_metrics_from_prompt")
async def test_generate_metrics_success_does_not_persist(
    mock_gen,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict,
):
    """Generate endpoint returns suggestions and does NOT write records to semantic_metrics."""
    db_model = SemanticDatabaseModel(
        id=10,
        created_by=1,
        display_name="Test Retail DB",
        db_type="postgres",
        conn_url_enc="dummy_enc",
        status="saved",
    )
    tbl = SemanticTableModel(
        id=10,
        db_id=10,
        table_name="orders",
        business_name="Đơn hàng",
        description="Lịch sử đơn hàng",
    )
    col = SemanticColumnModel(
        id=10,
        table_id=10,
        column_name="total_amount",
        data_type="NUMERIC",
        business_name="Tổng tiền",
        description="Tổng giá trị đơn",
    )
    async_session.add(db_model)
    async_session.add(tbl)
    async_session.add(col)
    await async_session.commit()

    mock_gen.return_value = [
        MetricSuggestionItem(
            name="Tổng doanh thu",
            description="Tổng giá trị các đơn hàng",
            sql_template="SELECT SUM(total_amount) FROM orders",
            source="ai",
        )
    ]

    res = await client.post(
        "/api/v1/semantic/10/metrics/generate",
        json={"prompt": "Tính tổng doanh thu từ bảng đơn hàng"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["name"] == "Tổng doanh thu"

    # Verify no records written to semantic_metrics
    m_check = await async_session.get(SemanticMetricModel, 1)
    assert m_check is None


@pytest.mark.asyncio
async def test_create_and_manage_metric_lifecycle(
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict,
):
    """Full lifecycle: Create metric with source='ai', update, and delete."""
    db_model = SemanticDatabaseModel(
        id=20,
        created_by=1,
        display_name="Lifecycle DB",
        db_type="postgres",
        conn_url_enc="dummy_enc",
        status="saved",
    )
    async_session.add(db_model)
    await async_session.commit()

    # 1. Create metric
    payload = {
        "name": "Tỷ lệ quay lại",
        "description": "Tỷ lệ % khách hàng quay lại mua hàng",
        "sql_template": "SELECT COUNT(*) FROM orders",
        "source": "ai",
    }
    res_create = await client.post("/api/v1/semantic/20/metric", json=payload, headers=auth_headers)
    assert res_create.status_code == 201
    created_data = res_create.json()
    assert created_data["metric_id"] > 0
    assert created_data["source"] == "ai"

    # Verify DB status updated to 'draft'
    await async_session.refresh(db_model)
    assert db_model.status == "draft"

    metric_id = created_data["metric_id"]

    # 2. Update metric
    update_payload = {
        "name": "Tỷ lệ khách hàng quay lại (Đã cập nhật)",
        "description": "Mô tả mới",
    }
    res_update = await client.put(
        f"/api/v1/semantic/20/metric/{metric_id}",
        json=update_payload,
        headers=auth_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Tỷ lệ khách hàng quay lại (Đã cập nhật)"

    # 3. Delete metric
    res_del = await client.delete(f"/api/v1/semantic/20/metric/{metric_id}", headers=auth_headers)
    assert res_del.status_code == 204

    # Verify metric deleted
    deleted_metric = await async_session.get(SemanticMetricModel, metric_id)
    assert deleted_metric is None
