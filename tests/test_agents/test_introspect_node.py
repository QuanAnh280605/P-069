"""Unit tests for the Flow 1 introspection node."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.introspect_node import introspect_node
from src.models.raw_schema import RawSchema
from src.services.introspection import InvalidCredentialError

RAW_SCHEMA: RawSchema = {
    "source": {
        "type": "live_connection",
        "db_engine": "sqlite",
        "connection_id": 1,
        "extracted_at": "2026-08-05T00:00:00Z",
    },
    "tables": [],
    "relationships": [],
}


@pytest.mark.asyncio
async def test_introspect_node_passes_persisted_connection_id() -> None:
    """Build the live request from typed graph state."""
    response = {"raw_schema": {**RAW_SCHEMA, "tables": [{"table_name": "orders"}]}, "warnings": ["partial"]}
    state = {"db_id": 9, "conn_url_enc": "ciphertext", "db_type": "sqlite"}
    with patch(
        "src.agents.nodes.introspect_node.extract_raw_schema",
        new_callable=AsyncMock,
        return_value=response,
    ) as extract:
        result = await introspect_node(state)
    request = {"conn_url_enc": "ciphertext", "db_type": "sqlite", "connection_id": 9}
    extract.assert_awaited_once_with(request)
    assert result["introspection_warnings"] == ["partial"]


@pytest.mark.asyncio
async def test_introspect_node_rejects_missing_connection_id() -> None:
    """Do not synthesize connection_id=0 when graph state is incomplete."""
    with patch(
        "src.agents.nodes.introspect_node.extract_raw_schema",
        new_callable=AsyncMock,
    ) as extract:
        result = await introspect_node({"conn_url_enc": "ciphertext", "db_type": "sqlite"})
    extract.assert_not_awaited()
    assert result == {"error": "Database connection ID is required."}


@pytest.mark.asyncio
async def test_introspect_node_rejects_empty_table_list() -> None:
    """Stop the graph when live extraction finds no base tables."""
    response = {"raw_schema": RAW_SCHEMA, "warnings": []}
    with patch(
        "src.agents.nodes.introspect_node.extract_raw_schema",
        new_callable=AsyncMock,
        return_value=response,
    ):
        result = await introspect_node({"db_id": 1, "conn_url_enc": "ciphertext", "db_type": "sqlite"})
    assert result == {"error": "The target database does not contain any tables."}


@pytest.mark.asyncio
async def test_introspect_node_hides_plaintext_credentials() -> None:
    """Map internal failures without leaking their messages."""
    secret_url = "sqlite:///password-is-secret.db"
    with patch(
        "src.agents.nodes.introspect_node.extract_raw_schema",
        new_callable=AsyncMock,
        side_effect=InvalidCredentialError(secret_url),
    ):
        result = await introspect_node({"db_id": 1, "conn_url_enc": "ciphertext", "db_type": "sqlite"})
    assert result["error"] == "Invalid database credential."
    assert secret_url not in result["error"]
