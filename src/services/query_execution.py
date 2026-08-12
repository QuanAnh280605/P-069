"""Execute compiled SELECT statements through async read-only adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.services.query_compiler import CompiledQuery, validate_read_only


@dataclass
class QueryResult:
    """Serializable result returned by the semantic query engine."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int


async def execute_compiled_query(
    conn_url: str,
    dialect: str,
    compiled: CompiledQuery,
    timeout_seconds: int = 15,
) -> QueryResult:
    """Execute one validated SELECT using an async connection and hard timeout."""
    validate_read_only(compiled.sql)
    engine = create_async_engine(_async_url(conn_url, dialect), pool_pre_ping=True)
    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    await _set_read_only(connection, dialect, timeout_seconds)
                    result = await connection.execute(text(compiled.sql), compiled.parameters)
                    rows = [list(row) for row in result.fetchall()]
                    await transaction.rollback()
                    return QueryResult(list(result.keys()), rows, len(rows))
                except Exception:
                    await transaction.rollback()
                    raise
    finally:
        await engine.dispose()


def _async_url(conn_url: str, dialect: str) -> str:
    if "+" in conn_url.split("://", maxsplit=1)[0]:
        return conn_url
    replacements = {
        "postgresql": "postgresql+asyncpg",
        "postgres": "postgresql+asyncpg",
        "mysql": "mysql+asyncmy",
        "sqlite": "sqlite+aiosqlite",
    }
    scheme, rest = conn_url.split("://", maxsplit=1)
    return f"{replacements.get(dialect, replacements.get(scheme, scheme))}://{rest}"


async def _set_read_only(connection: Any, dialect: str, timeout_seconds: int) -> None:
    if dialect in {"postgres", "postgresql"}:
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        await connection.execute(text(f"SET LOCAL statement_timeout = {timeout_seconds * 1000}"))
    elif dialect == "mysql":
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        await connection.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {timeout_seconds * 1000}"))
