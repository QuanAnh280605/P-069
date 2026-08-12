"""API tests for YAML preview and JSON metric persistence."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import SemanticColumnModel, SemanticDatabaseModel, SemanticMetricModel, SemanticTableModel, UserModel
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash", role="analyst")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _definition(name: str = "Doanh thu") -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "order_items",
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "Chưa trừ hoàn tiền",
            }
        }
    )


async def _seed(async_session: AsyncSession, db_id: int) -> None:
    database = SemanticDatabaseModel(
        id=db_id, created_by=1, display_name="Retail", db_type="postgresql", conn_url_enc="enc", status="saved"
    )
    table = SemanticTableModel(
        id=db_id, db_id=db_id, table_name="order_items", business_name="Chi tiết đơn", description=""
    )
    async_session.add_all([database, table])
    await async_session.flush()
    async_session.add_all(
        [
            SemanticColumnModel(
                table_id=table.id, column_name="quantity", data_type="INTEGER", business_name="Số lượng"
            ),
            SemanticColumnModel(
                table_id=table.id, column_name="unit_price", data_type="NUMERIC", business_name="Đơn giá"
            ),
        ]
    )
    await async_session.commit()


@pytest.mark.asyncio
@patch("src.api.routes.generate_metrics_from_prompt")
async def test_generate_returns_yaml_without_persisting(
    mock_generate: object, client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    await _seed(async_session, 10)
    definition = _definition()
    mock_generate.return_value = [MetricSuggestionItem(definition=definition, yaml_preview=definition.to_yaml())]
    response = await client.post(
        "/api/v1/semantic/10/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestions"][0]
    assert suggestion["definition"]["metric"]["name"] == "Doanh thu"
    assert "metric:" in suggestion["yaml_preview"]
    assert (await async_session.get(SemanticMetricModel, 1)) is None


@pytest.mark.asyncio
async def test_create_update_and_delete_definition(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    await _seed(async_session, 20)
    payload = {"definition": _definition().model_dump(mode="json"), "source": "ai"}
    created = await client.post("/api/v1/semantic/20/metric", json=payload, headers=auth_headers)
    assert created.status_code == 201
    metric_id = created.json()["metric_id"]
    stored = await async_session.get(SemanticMetricModel, metric_id)
    assert stored.definition["metric"]["formula"]["expression"] == "quantity * unit_price"
    assert stored.sql_template == ""
    updated_payload = {"definition": _definition("Doanh thu thuần").model_dump(mode="json")}
    updated = await client.put(f"/api/v1/semantic/20/metric/{metric_id}", json=updated_payload, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["definition"]["metric"]["name"] == "Doanh thu thuần"
    deleted = await client.delete(f"/api/v1/semantic/20/metric/{metric_id}", headers=auth_headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_create_rejects_sql_contract(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/semantic/1/metric",
        json={"name": "Bad", "sql_template": "SELECT 1", "source": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 422
