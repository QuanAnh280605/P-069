"""Introspect Node — Flow 1 Step 1."""

from __future__ import annotations

import logging

from src.agents.state import AgentState
from src.services.introspection import (
    ConnectionIntrospectionError,
    IntrospectionError,
    InvalidCredentialError,
    LiveSchemaRequest,
    UnsupportedDatabaseTypeError,
    extract_raw_schema,
)

logger = logging.getLogger(__name__)


async def introspect_node(state: AgentState) -> dict[str, object]:
    """Read target schema metadata through the introspection interface."""
    if not state.get("conn_url_enc") or not state.get("db_type"):
        return {"error": "Database connection settings are required."}
    if not state.get("db_id") or state["db_id"] <= 0:
        return {"error": "Database connection ID is required."}
    req: LiveSchemaRequest = {
        "conn_url_enc": state["conn_url_enc"],
        "db_type": state["db_type"],
        "connection_id": state["db_id"],
    }
    try:
        result = await extract_raw_schema(req)
    except IntrospectionError as exc:
        return _error_response(state, exc)
    if not result["raw_schema"]["tables"]:
        return {"error": "The target database does not contain any tables."}
    logger.info(
        "Schema introspection completed db_id=%s db_type=%s tables=%d",
        state.get("db_id"),
        state["db_type"],
        len(result["raw_schema"]["tables"]),
    )
    return {"raw_schema": result["raw_schema"], "introspection_warnings": result["warnings"]}


def _error_response(state: AgentState, exc: IntrospectionError) -> dict[str, object]:
    logger.warning(
        "Schema introspection failed db_id=%s db_type=%s error=%s",
        state.get("db_id"),
        state.get("db_type"),
        type(exc).__name__,
    )
    if isinstance(exc, InvalidCredentialError):
        return {"error": "Invalid database credential."}
    if isinstance(exc, UnsupportedDatabaseTypeError):
        return {"error": "Unsupported database type or connection settings."}
    if isinstance(exc, ConnectionIntrospectionError):
        return {"error": "Cannot connect to the target database."}
    return {"error": "Cannot read the target database schema."}
