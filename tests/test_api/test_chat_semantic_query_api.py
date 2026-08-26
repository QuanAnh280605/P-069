"""Integration/API tests for 1-Shot Natural Language to Semantic Query in Chat."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.api.auth import create_access_token
from src.models.db import UserModel
from src.models.schemas import ChatSemanticQueryResult, DimensionSelection, SemanticQuerySpec
from src.services.metric_context import MetricContextResult


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="lead@company.com", username="lead", hashed_password="hash")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def member_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def chat_mocks():
    now = datetime(2026, 8, 24, 12, 0, 0)
    session = SimpleNamespace(id="sess-nl-1", db_id=101, title="Phiên NL", created_at=now, updated_at=now)
    refreshed = SimpleNamespace(id="sess-nl-1", db_id=101, title="Phiên NL", created_at=now, updated_at=now)

    with (
        patch("src.api.routes.get_chat_database", new_callable=AsyncMock) as mock_get_db,
        patch("src.api.routes._chat_can_generate_metrics", new_callable=AsyncMock) as mock_can,
        patch("src.api.routes._resolve_chat_session", new_callable=AsyncMock) as mock_resolve,
        patch("src.api.routes.get_recent_chat_history", new_callable=AsyncMock) as mock_hist,
        patch("src.api.routes.save_chat_message", new_callable=AsyncMock) as mock_save,
        patch("src.api.routes.get_chat_session_with_messages", new_callable=AsyncMock) as mock_refresh,
        patch("src.api.routes.build_data_context", new_callable=AsyncMock) as mock_data_ctx,
        patch("src.api.routes.build_metric_context", new_callable=AsyncMock) as mock_metric_ctx,
        patch("src.api.routes._require_resource_permission", new_callable=AsyncMock),
        patch("src.api.routes._query_target", new_callable=AsyncMock) as mock_target,
        patch("src.api.routes.build_parser_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("src.api.routes.execute_natural_language_query", new_callable=AsyncMock) as mock_exec,
    ):
        mock_get_db.return_value = SimpleNamespace(id=101, org_id=1)
        mock_can.return_value = True
        mock_resolve.return_value = session
        mock_hist.return_value = []
        mock_save.side_effect = lambda *args, **kwargs: SimpleNamespace(
            id="msg-id",
            content=kwargs.get("content", ""),
            sender=kwargs.get("sender", "user"),
            intent=kwargs.get("intent"),
            metadata_json=kwargs.get("metadata_json"),
        )
        mock_refresh.return_value = refreshed
        mock_data_ctx.return_value = MetricContextResult(schema={}, diagnostic={"status": "ready"})
        mock_metric_ctx.return_value = MetricContextResult(schema={}, diagnostic={"status": "ready"})
        mock_target.return_value = (
            SimpleNamespace(id=101),
            SimpleNamespace(id=1, dialect="sqlite", conn_url_enc="enc"),
        )
        mock_catalog.return_value = {
            "metrics": [
                {
                    "id": 1,
                    "name": "revenue",
                    "business_name": "Doanh thu",
                    "formula": "SUM(amount)",
                    "base_entity": "orders",
                }
            ],
            "dimensions": [
                {
                    "column_id": 10,
                    "column_name": "customer_id",
                    "business_name": "Khách hàng",
                    "table_name": "orders",
                    "data_type": "INTEGER",
                    "is_time_dimension": False,
                }
            ],
            "filter_columns": [],
        }
        mock_exec.return_value = ChatSemanticQueryResult(
            spec=SemanticQuerySpec(
                metric_ids=[1], dimensions=[DimensionSelection(column_id=10)], filters=[], limit=100
            ),
            columns=["customer_id", "revenue"],
            rows=[[101, 1500000], [102, 2300000]],
            row_count=2,
            explanation="Số liệu được tính từ chỉ số **Doanh thu** với công thức `SUM(amount)`.",
            sql="SELECT customer_id, SUM(amount) AS revenue FROM orders GROUP BY customer_id LIMIT 100",
            metadata={"base_table": "orders"},
        )
        yield SimpleNamespace(
            mock_can=mock_can,
            mock_exec=mock_exec,
            mock_save=mock_save,
        )


@pytest.mark.asyncio
@patch("src.agents.nodes.orchestrator_node.orchestrator_node", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_resolved_nl_query_for_data_lead_includes_sql(
    mock_agent: AsyncMock,
    mock_orch: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """Data Lead receives the result table and compiled SQL preview."""
    chat_mocks.mock_can.return_value = True
    mock_orch.return_value = {"intent": "semantic_query"}
    mock_agent.ainvoke.return_value = {
        "intent": "semantic_query",
        "interpretation": {
            "status": "resolved",
            "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
            "time_ranges": [],
        },
    }

    res = await client.post(
        "/api/v1/semantic/101/chat",
        json={"message": "Tổng doanh thu theo khách hàng"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "semantic_query"
    assert body["semantic_query_result"] is not None
    assert body["semantic_query_result"]["columns"] == ["customer_id", "revenue"]
    assert body["semantic_query_result"]["row_count"] == 2
    assert body["semantic_query_result"]["sql"] is not None
    assert "SELECT customer_id" in body["semantic_query_result"]["sql"]


@pytest.mark.asyncio
@patch("src.agents.nodes.orchestrator_node.orchestrator_node", new_callable=AsyncMock)
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
async def test_resolved_nl_query_for_member_redacts_sql(
    mock_agent: AsyncMock,
    mock_orch: AsyncMock,
    client: AsyncClient,
    member_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """Member receives query result snapshot but SQL is redacted."""
    chat_mocks.mock_can.return_value = False  # Member role
    mock_orch.return_value = {"intent": "semantic_query"}
    mock_agent.ainvoke.return_value = {
        "intent": "semantic_query",
        "interpretation": {
            "status": "resolved",
            "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
            "time_ranges": [],
        },
    }

    res = await client.post(
        "/api/v1/semantic/101/chat",
        json={"message": "Tổng doanh thu theo khách hàng"},
        headers=member_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "semantic_query"
    assert body["semantic_query_result"] is not None
    assert body["semantic_query_result"]["columns"] == ["customer_id", "revenue"]
    assert body["semantic_query_result"]["sql"] is None  # REDACTED for Member!


@pytest.mark.asyncio
@patch("src.api.routes.get_chat_message", new_callable=AsyncMock)
async def test_clarification_selection_click_executes_spec(
    mock_get_msg: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """Clicking a clarification option executes the pre-validated spec without LLM parsing."""
    prev_msg = SimpleNamespace(
        id="msg-prev-clar",
        session_id="sess-nl-1",
        metadata_json={
            "clarification": {
                "prompt": "Bạn muốn xem doanh thu theo?",
                "options": [
                    {
                        "id": "opt_by_customer",
                        "label": "Theo khách hàng",
                        "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
                    }
                ],
            }
        },
    )
    mock_get_msg.return_value = prev_msg

    res = await client.post(
        "/api/v1/semantic/101/chat",
        json={
            "message": "Theo khách hàng",
            "session_id": "00000000-0000-0000-0000-000000000001",
            "clarification_selection": {
                "assistant_message_id": "msg-prev-clar",
                "option_id": "opt_by_customer",
            },
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "semantic_query"
    assert body["semantic_query_result"] is not None
    assert body["semantic_query_result"]["columns"] == ["customer_id", "revenue"]


@pytest.mark.asyncio
async def test_replay_returns_persisted_semantic_query_snapshot(
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """Idempotent retry with same client_message_id returns persisted snapshot without executing query."""
    persisted_meta = {
        "schema_version": 2,
        "status": "completed",
        "semantic_query_result": {
            "spec": {"metric_ids": [1], "dimensions": [{"column_id": 10}], "filters": [], "limit": 100},
            "columns": ["customer_id", "revenue"],
            "rows": [[101, 1500000]],
            "row_count": 1,
            "explanation": "Số liệu doanh thu",
            "sql": "SELECT 1",
            "metadata": {},
        },
    }
    user_msg = SimpleNamespace(id="msg-u-replay", client_message_id="client-123")
    asst_msg = SimpleNamespace(
        id="msg-a-replay",
        client_message_id="client-123:assistant",
        content="Số liệu doanh thu",
        intent="semantic_query",
        metadata_json=persisted_meta,
    )

    with (
        patch("src.api.routes.get_chat_message_by_client_id", new_callable=AsyncMock) as mock_find_msg,
        patch("src.api.routes.execute_natural_language_query", new_callable=AsyncMock) as mock_exec,
    ):
        mock_find_msg.side_effect = [user_msg, asst_msg]
        res = await client.post(
            "/api/v1/semantic/101/chat",
            json={"message": "Doanh thu", "client_message_id": "client-123"},
            headers=auth_headers,
        )

    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "semantic_query"
    assert body["semantic_query_result"]["columns"] == ["customer_id", "revenue"]
    assert body["semantic_query_result"]["rows"] == [[101, 1500000]]
    mock_exec.assert_not_called()


@pytest.mark.asyncio
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
@patch("src.agents.nodes.orchestrator_node.orchestrator_node", new_callable=AsyncMock)
@patch("src.api.routes.get_chat_message", new_callable=AsyncMock)
async def test_clarification_selection_for_create_metric_delegates_to_standard_chat(
    mock_get_msg: AsyncMock,
    mock_orch: AsyncMock,
    mock_agent: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """Clicking a create_metric clarification option delegates to standard chat to trigger metric generator."""
    prev_msg = SimpleNamespace(
        id="msg-prev-create",
        session_id="sess-nl-1",
        metadata_json={
            "clarification": {
                "prompt": "Chưa có metric 'Tỷ lệ giữ chân khách hàng'. Bạn có muốn tạo không?",
                "options": [
                    {
                        "id": "create_metric",
                        "label": "Tạo metric 'Tỷ lệ giữ chân khách hàng'",
                        "action": "create_metric",
                        "spec": None,
                    }
                ],
            }
        },
    )
    mock_get_msg.return_value = prev_msg
    mock_orch.return_value = {"intent": "metric_query"}
    mock_agent.ainvoke.return_value = {
        "intent": "metric_query",
        "chat_response": "Tôi đề xuất tạo metric Tỷ lệ giữ chân khách hàng.",
    }

    res = await client.post(
        "/api/v1/semantic/101/chat",
        json={
            "message": "Tạo metric 'Tỷ lệ giữ chân khách hàng'",
            "session_id": "00000000-0000-0000-0000-000000000001",
            "clarification_selection": {
                "assistant_message_id": "msg-prev-create",
                "option_id": "create_metric",
            },
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "metric_query"


@pytest.mark.asyncio
@patch("src.agents.chat_graph.chat_agent", new_callable=AsyncMock)
@patch("src.agents.nodes.orchestrator_node.orchestrator_node", new_callable=AsyncMock)
@patch("src.api.routes.get_chat_message", new_callable=AsyncMock)
async def test_clarification_selection_with_stale_metric_id_delegates_to_standard_chat(
    mock_get_msg: AsyncMock,
    mock_orch: AsyncMock,
    mock_agent: AsyncMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
    chat_mocks: SimpleNamespace,
) -> None:
    """A clarification option whose metric IDs are no longer in the approved catalog is not executed as a query."""
    prev_msg = SimpleNamespace(
        id="msg-prev-stale",
        session_id="sess-nl-1",
        metadata_json={
            "clarification": {
                "prompt": "Chọn chỉ số",
                "options": [
                    {
                        "id": "opt_stale",
                        "label": "Chỉ số đã xóa",
                        "spec": {"metric_ids": [9999], "dimensions": [], "filters": [], "limit": 100},
                    }
                ],
            }
        },
    )
    mock_get_msg.return_value = prev_msg
    mock_orch.return_value = {"intent": "data_question", "chat_response": "Không tìm thấy chỉ số phù hợp."}
    mock_agent.ainvoke.return_value = {
        "intent": "data_question",
        "chat_response": "Không tìm thấy chỉ số phù hợp.",
    }

    res = await client.post(
        "/api/v1/semantic/101/chat",
        json={
            "message": "Xem chỉ số đó",
            "session_id": "00000000-0000-0000-0000-000000000001",
            "clarification_selection": {
                "assistant_message_id": "msg-prev-stale",
                "option_id": "opt_stale",
            },
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] != "semantic_query"
    chat_mocks.mock_exec.assert_not_called()
