"""API tests for dedupe wiring in the AI chat orchestrator route."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.api.auth import create_access_token
from src.models.db import UserModel
from src.services.metric_context import MetricContextResult


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def chat_session_mocks():
    """Patch main's RBAC/session persistence layer around the chat orchestrator."""
    now = datetime(2026, 8, 19, 12, 0, 0)
    session = SimpleNamespace(id="sess-1", db_id=101, title="Phiên test", created_at=now, updated_at=now)
    refreshed = SimpleNamespace(id="sess-1", db_id=101, title="Phiên test", created_at=now, updated_at=now)
    with (
        patch("src.api.routes.get_chat_database", new_callable=AsyncMock),
        patch("src.api.routes._chat_can_generate_metrics", new_callable=AsyncMock) as mock_can,
        patch("src.api.routes._resolve_chat_session", new_callable=AsyncMock) as mock_resolve,
        patch("src.api.routes._replay_chat_response", new_callable=AsyncMock) as mock_replay,
        patch("src.api.routes.get_recent_chat_history", new_callable=AsyncMock) as mock_history,
        patch("src.api.routes.save_chat_message", new_callable=AsyncMock) as mock_save,
        patch("src.api.routes.get_chat_session_with_messages", new_callable=AsyncMock) as mock_refresh,
        patch("src.api.routes.build_metric_context", new_callable=AsyncMock) as mock_context,
    ):
        mock_can.return_value = True
        mock_resolve.return_value = session
        mock_replay.return_value = None
        mock_history.return_value = []
        mock_save.side_effect = [SimpleNamespace(id="msg-u"), SimpleNamespace(id="msg-a")]
        mock_refresh.return_value = refreshed
        mock_context.return_value = MetricContextResult(schema={}, diagnostic={"status": "ready"})
        yield SimpleNamespace(resolve=mock_resolve, save=mock_save)


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
    "proposed_metric_name": "Tổng doanh thu",
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
    mock_agent: AsyncMock,
    mock_load: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_session_mocks: SimpleNamespace,
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
    assert body["session_id"] == "sess-1"
    state = mock_agent.ainvoke.call_args.args[0]
    assert state["existing_metrics"]
    assert state["dedupe_performed"] is True
    # The duplicate notice is persisted on the assistant message for replay.
    metadata = chat_session_mocks.save.call_args_list[-1].kwargs["metadata_json"]
    assert metadata["duplicates"] == [_DUPLICATE_NOTICE]


@pytest.mark.asyncio
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_chat_loads_existing_for_numeric_db(
    mock_agent: AsyncMock,
    mock_load: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_session_mocks: SimpleNamespace,
) -> None:
    mock_load.return_value = ([], True)
    mock_agent.ainvoke.return_value = {
        "intent": "metric_query",
        "suggested_metrics": [],
        "duplicate_notices": [],
        "dedupe_performed": True,
    }
    response = await client.post("/api/v1/semantic/101/chat", json={"message": "tính doanh thu"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["dedupe_performed"] is True
    mock_load.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_chat_dedupe_unavailable_still_200(
    mock_agent: AsyncMock,
    mock_load: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_session_mocks: SimpleNamespace,
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
