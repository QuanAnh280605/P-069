"""Tests cho Flow 1 LangGraph pipeline.

LLM và DB đều được mock — không gọi OpenAI API thật,
không kết nối database thật.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.state import AgentState

# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_state_has_required_fields():
    """AgentState TypedDict phải có đủ fields cho Flow 1."""
    state: AgentState = {
        "db_id": 1,
        "conn_url_enc": "encrypted-url",
        "db_type": "sqlite",
        "raw_schema": {
            "source": {
                "type": "live_connection",
                "db_engine": "sqlite",
                "connection_id": 1,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        },
        "introspection_warnings": [],
        "enriched_schema": {},
        "suggested_metrics": [],
        "hitl_approved": False,
        "semantic_layer_id": 0,
        "error": "",
        "user_id": 1,
    }
    assert "conn_url_enc" in state
    assert "raw_schema" in state
    assert "enriched_schema" in state
    assert "suggested_metrics" in state
    assert "semantic_layer_id" in state
    assert "user_id" in state


# ---------------------------------------------------------------------------
# Enrich node (existing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.services.llm.get_llm")
async def test_enrich_node_skipped_when_raw_schema_empty(mock_get_llm):
    """Enrich node phải trả về error khi raw_schema rỗng."""
    from src.agents.nodes.enrich_node import enrich_node

    mock_get_llm.return_value = AsyncMock()
    result = await enrich_node({"raw_schema": {}})
    assert "error" in result
    assert result["error"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_schema_dict() -> dict:
    """Return a minimal valid RawSchema TypedDict for tests."""
    return {
        "source": {
            "type": "live_connection",
            "db_engine": "postgresql",
            "connection_id": 1,
            "extracted_at": "2026-08-05T00:00:00Z",
        },
        "tables": [
            {
                "table_name": "users",
                "schema_name": "public",
                "table_type": "BASE TABLE",
                "row_count_estimate": None,
                "columns": [
                    {
                        "column_name": "id",
                        "data_type": "INTEGER",
                        "is_nullable": False,
                        "is_primary_key": True,
                        "is_foreign_key": False,
                        "default_value": None,
                        "sample_values": None,
                        "references": None,
                    },
                    {
                        "column_name": "name",
                        "data_type": "VARCHAR",
                        "is_nullable": True,
                        "is_primary_key": False,
                        "is_foreign_key": False,
                        "default_value": None,
                        "sample_values": None,
                        "references": None,
                    },
                ],
                "primary_keys": ["id"],
                "foreign_keys": [],
                "indexes": [],
            },
            {
                "table_name": "orders",
                "schema_name": "public",
                "table_type": "BASE TABLE",
                "row_count_estimate": None,
                "columns": [
                    {
                        "column_name": "id",
                        "data_type": "INTEGER",
                        "is_nullable": False,
                        "is_primary_key": True,
                        "is_foreign_key": False,
                        "default_value": None,
                        "sample_values": None,
                        "references": None,
                    },
                    {
                        "column_name": "user_id",
                        "data_type": "INTEGER",
                        "is_nullable": False,
                        "is_primary_key": False,
                        "is_foreign_key": True,
                        "default_value": None,
                        "sample_values": None,
                        "references": {"table": "users", "column": "id", "schema": "public"},
                    },
                    {
                        "column_name": "total",
                        "data_type": "NUMERIC",
                        "is_nullable": True,
                        "is_primary_key": False,
                        "is_foreign_key": False,
                        "default_value": None,
                        "sample_values": None,
                        "references": None,
                    },
                ],
                "primary_keys": ["id"],
                "foreign_keys": [
                    {
                        "constraint_name": "fk_orders_user",
                        "constrained_columns": ["user_id"],
                        "referred_schema": "public",
                        "referred_table": "users",
                        "referred_columns": ["id"],
                    }
                ],
                "indexes": [],
            },
        ],
        "relationships": [
            {
                "from_table": "orders",
                "from_column": "user_id",
                "to_table": "users",
                "to_column": "id",
                "relationship_type": "many_to_one",
            }
        ],
    }


def _make_approved_state() -> dict:
    """Return a minimal approved AgentState for save_node tests."""
    return {
        "db_id": 1,
        "user_id": 1,
        "conn_url_enc": "encrypted-url",
        "db_type": "postgresql",
        "raw_schema": _make_raw_schema_dict(),
        "enriched_schema": {"tables": []},
        "suggested_metrics": [],
        "hitl_approved": True,
        "semantic_layer_id": 0,
        "error": "",
    }


# ---------------------------------------------------------------------------
# save_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_node_returns_error_when_not_approved():
    """save_node phải trả về error nếu hitl_approved=False."""
    from src.agents.nodes.save_node import save_node

    state = _make_approved_state()
    state["hitl_approved"] = False
    result = await save_node(state)
    assert "error" in result
    assert "HITL not approved" in result["error"]


@pytest.mark.asyncio
@patch("src.agents.nodes.save_node.get_db_session")
@patch("src.agents.nodes.save_node.enrich_and_save_canonical_schema")
async def test_save_node_calls_enrichment_when_approved(mock_enrich: AsyncMock, mock_get_db: MagicMock):
    """save_node phải gọi enrich_and_save_canonical_schema khi HITL approved."""
    from src.agents.nodes.save_node import save_node

    mock_session = AsyncMock()
    mock_get_db.return_value = _async_gen(mock_session)
    mock_enrich.return_value = {
        "tables": [{"table_name": "users", "table_id": 1}],
        "relationships": [],
        "status": "draft",
    }

    result = await save_node(_make_approved_state())

    mock_enrich.assert_awaited_once()
    call_kwargs = mock_enrich.call_args
    assert call_kwargs.kwargs["user_id"] == 1
    assert call_kwargs.kwargs["connection_id"] == 1
    assert call_kwargs.kwargs["dialect"] == "postgresql"
    assert result["semantic_layer_id"] == 1
    assert "error" not in result


@pytest.mark.asyncio
@patch("src.agents.nodes.save_node.get_db_session")
@patch("src.agents.nodes.save_node.enrich_and_save_canonical_schema")
async def test_save_node_handles_enrichment_error(mock_enrich: AsyncMock, mock_get_db: MagicMock):
    """save_node phải trả về error nếu enrichment service raise exception."""
    from src.agents.nodes.save_node import save_node

    mock_session = AsyncMock()
    mock_get_db.return_value = _async_gen(mock_session)
    mock_enrich.side_effect = RuntimeError("LLM service unavailable")

    result = await save_node(_make_approved_state())

    assert "error" in result
    assert "LLM service unavailable" in result["error"]


# ---------------------------------------------------------------------------
# raw_schema_to_canonical conversion
# ---------------------------------------------------------------------------


def test_raw_schema_to_canonical_converts_table_names():
    """raw_schema_to_canonical phải convert table_name từ str sang Identifier."""
    from src.agents.nodes.save_node import raw_schema_to_canonical

    raw = _make_raw_schema_dict()
    result = raw_schema_to_canonical(raw, "postgresql")

    assert result.dialect.value == "postgresql"
    assert len(result.tables) == 2
    table_names = {t.table_name.raw_name for t in result.tables}
    assert table_names == {"users", "orders"}


def test_raw_schema_to_canonical_converts_columns():
    """raw_schema_to_canonical phải convert columns từ TypedDict sang Pydantic ColumnMetadata."""
    from src.agents.nodes.save_node import raw_schema_to_canonical

    raw = _make_raw_schema_dict()
    result = raw_schema_to_canonical(raw, "postgresql")

    users_table = [t for t in result.tables if t.table_name.raw_name == "users"][0]
    col_names = {c.column_name.raw_name for c in users_table.columns}
    assert col_names == {"id", "name"}

    id_col = [c for c in users_table.columns if c.column_name.raw_name == "id"][0]
    assert id_col.primary_key is True
    assert id_col.nullable is False


def test_raw_schema_to_canonical_converts_foreign_keys():
    """raw_schema_to_canonical phải convert foreign_keys từ TypedDict sang Pydantic ForeignKeyMetadata."""
    from src.agents.nodes.save_node import raw_schema_to_canonical

    raw = _make_raw_schema_dict()
    result = raw_schema_to_canonical(raw, "postgresql")

    orders_table = [t for t in result.tables if t.table_name.raw_name == "orders"][0]
    assert len(orders_table.foreign_keys) == 1
    fk = orders_table.foreign_keys[0]
    assert fk.referred_table.raw_name == "users"
    assert fk.constrained_columns[0].raw_name == "user_id"
    assert fk.referred_columns[0].raw_name == "id"


def test_raw_schema_to_canonical_converts_primary_key():
    """raw_schema_to_canonical phải convert primary_keys từ list[str] sang PrimaryKeyMetadata."""
    from src.agents.nodes.save_node import raw_schema_to_canonical

    raw = _make_raw_schema_dict()
    result = raw_schema_to_canonical(raw, "postgresql")

    users_table = [t for t in result.tables if t.table_name.raw_name == "users"][0]
    assert users_table.primary_key is not None
    assert users_table.primary_key.constrained_columns[0].raw_name == "id"


# ---------------------------------------------------------------------------
# Graph interrupt & routing
# ---------------------------------------------------------------------------


def test_graph_compiled_with_interrupt_before_save():
    """Graph phải compile với interrupt_before=['save']."""
    from src.agents.graph import build_graph

    graph = build_graph()
    # CompiledGraph stores interrupt config as interrupt_before_nodes
    assert "save" in graph.interrupt_before_nodes


@pytest.mark.asyncio
async def test_route_after_save_routes_to_end_when_saved():
    """route_after_save phải trả về END khi semantic_layer_id > 0."""
    from src.agents.graph import END, route_after_save

    state: AgentState = {"semantic_layer_id": 42}  # type: ignore[typeddict-item]
    assert route_after_save(state) == END


@pytest.mark.asyncio
async def test_route_after_save_routes_to_enrich_when_rejected():
    """route_after_save phải trả về 'enrich' khi semantic_layer_id chưa set."""
    from src.agents.graph import route_after_save

    state: AgentState = {"semantic_layer_id": 0}  # type: ignore[typeddict-item]
    assert route_after_save(state) == "enrich"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_gen(val):
    """Yield a single value — helper for mocking get_db_session()."""
    yield val
