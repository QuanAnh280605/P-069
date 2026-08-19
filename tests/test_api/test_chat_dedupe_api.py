"""API tests for dedupe wiring in the AI chat orchestrator route."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.api.auth import create_access_token
from src.models.db import UserModel


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash", role="analyst")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


_MINIMAL_METRIC: dict = {
    "definition": {
        "metric": {
            "name": "Doanh thu",
            "formula": {"function": "SUM", "expression": "quantity * unit_price"},
            "base_entity": "order_items",
            "filters": [],
            "status": "pending_approval",
            "confidence": "high",
        }
    },
    "yaml_preview": "metric:\n  name: Doanh thu\n",
}

_EXISTING_SUMMARY: dict = {
    "id": 12,
    "name": "Doanh thu",
    "status": "approved",
    "function": "SUM",
    "expression": "quantity * unit_price",
    "base_entity": "order_items",
    "filters": [],
}

_DUPLICATE_NOTICE: dict = {
    "existing_metric_id": 12,
    "existing_metric_name": "Doanh thu",
    "existing_metric_status": "approved",
    "user_message": "Đã có metric chuẩn",
    "similarity_reason": "",
}


@pytest.mark.asyncio
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_chat_returns_duplicates(
    mock_agent: AsyncMock, mock_load: AsyncMock, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    mock_load.return_value = ([_EXISTING_SUMMARY], True)
    mock_agent.ainvoke.return_value = {
        "intent": "metric_query",
        "suggested_metrics": [_MINIMAL_METRIC],
        "duplicate_notices": [_DUPLICATE_NOTICE],
        "dedupe_performed": True,
    }
    response = await client.post("/api/v1/semantic/101/chat", json={"message": "tính doanh thu"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "metric_query"
    assert body["duplicates"][0]["existing_metric_name"] == "Doanh thu"
    assert body["dedupe_performed"] is True
    state = mock_agent.ainvoke.call_args.args[0]
    assert state["existing_metrics"]
    assert state["dedupe_performed"] is True


@pytest.mark.asyncio
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_chat_demo_id_skips_real_load(
    mock_agent: AsyncMock, mock_load: AsyncMock, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    mock_load.return_value = ([], True)
    mock_agent.ainvoke.return_value = {
        "intent": "metric_query",
        "suggested_metrics": [],
        "duplicate_notices": [],
        "dedupe_performed": True,
    }
    response = await client.post(
        "/api/v1/semantic/demo-retail/chat", json={"message": "tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["dedupe_performed"] is True
    mock_load.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_chat_dedupe_unavailable_still_200(
    mock_agent: AsyncMock, mock_load: AsyncMock, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    mock_load.return_value = ([], False)
    mock_agent.ainvoke.return_value = {
        "intent": "metric_query",
        "suggested_metrics": [],
        "duplicate_notices": [],
        "dedupe_performed": False,
    }
    response = await client.post("/api/v1/semantic/101/chat", json={"message": "tính doanh thu"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["dedupe_performed"] is False
