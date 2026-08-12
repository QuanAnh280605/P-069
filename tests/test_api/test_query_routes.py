"""Tests for POST /semantic/{db_id}/query endpoint — Flow 2 (Live DB Only)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import (
    ImportedSchemaModel,
    LiveTargetDbModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.services.query_compiler import CompiledQuery

QUERY_ENDPOINT = "/api/v1/semantic/{db_id}/query"


def _token_headers(user: UserModel | None = None) -> dict[str, str]:
    active_user = user or UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    return {"Authorization": f"Bearer {create_access_token(active_user)}"}


async def _seed_live_db_with_semantic(db: AsyncSession) -> dict[str, Any]:
    """Seed a semantic database linked to a LiveTargetDbModel for query tests."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Test Live DB",
        db_type="sqlite",
        conn_url_enc="encrypted-url",
        status="approved",
    )
    db.add(sem_db)
    await db.flush()

    live_db = LiveTargetDbModel(
        created_by=1,
        display_name="Test Live DB",
        dialect="sqlite",
        conn_url_enc="encrypted-url",
        schema_metadata={},
        semantic_db_id=sem_db.id,
    )
    db.add(live_db)
    await db.flush()

    tbl = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Don hang",
        primary_key_column="order_id",
        created_by=1,
    )
    db.add(tbl)
    await db.flush()

    col_total = SemanticColumnModel(
        table_id=tbl.id,
        column_name="total_amount",
        data_type="DECIMAL",
        business_name="Tong tien",
    )
    col_created = SemanticColumnModel(
        table_id=tbl.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Ngay tao",
        is_time_dimension=True,
    )
    db.add_all([col_total, col_created])
    await db.flush()

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Total Revenue",
        description="Revenue",
        sql_template="SELECT SUM(total_amount) FROM orders",
        formula="SUM(orders.total_amount)",
        aggregation_type="SUM",
        status="approved",
        base_entity_id=tbl.id,
        created_by=1,
        definition={
            "metric": {
                "name": "Total Revenue",
                "formula": {"function": "SUM", "expression": "total_amount"},
                "base_entity": "orders",
                "filters": [],
                "status": "approved",
                "confidence": "high",
                "excluded_notes": "",
            }
        },
    )
    db.add(metric)
    await db.flush()
    await db.commit()

    return {
        "sem_db_id": sem_db.id,
        "live_db_id": live_db.id,
        "metric_id": metric.id,
        "col_created_id": col_created.id,
        "col_total_id": col_total.id,
    }


async def _seed_imported_schema_only(db: AsyncSession) -> dict[str, Any]:
    """Seed a semantic database linked to ImportedSchemaModel (no LiveTargetDbModel)."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Imported DB",
        db_type="sqlite",
        conn_url_enc="encrypted-url",
        status="approved",
    )
    db.add(sem_db)
    await db.flush()

    imported = ImportedSchemaModel(
        created_by=1,
        display_name="Imported Schema",
        dialect="sqlite",
        schema_metadata={},
        semantic_db_id=sem_db.id,
    )
    db.add(imported)
    await db.flush()

    tbl = SemanticTableModel(
        db_id=sem_db.id,
        table_name="products",
        business_name="San pham",
        primary_key_column="id",
        created_by=1,
    )
    db.add(tbl)
    await db.flush()

    col = SemanticColumnModel(
        table_id=tbl.id,
        column_name="name",
        data_type="VARCHAR",
        business_name="Ten SP",
    )
    db.add(col)
    await db.flush()

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Product Count",
        description="Count",
        sql_template="SELECT COUNT(*) FROM products",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="approved",
        base_entity_id=tbl.id,
        created_by=1,
        definition={
            "metric": {
                "name": "Product Count",
                "formula": {"function": "COUNT", "expression": "*"},
                "base_entity": "products",
                "filters": [],
                "status": "approved",
                "confidence": "high",
                "excluded_notes": "",
            }
        },
    )
    db.add(metric)
    await db.flush()
    await db.commit()

    return {
        "sem_db_id": sem_db.id,
        "metric_id": metric.id,
        "col_id": col.id,
    }


# ===================================================================
# Success case
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.decrypt_conn_url")
@patch("src.api.routes._execute_sql_on_live_db")
@patch("src.api.routes.SemanticQueryCompiler")
async def test_query_success(
    mock_compiler_cls: Any,
    mock_execute: Any,
    mock_decrypt: Any,
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns compiled SQL and results."""
    data = await _seed_live_db_with_semantic(async_session)

    mock_compiled = CompiledQuery(
        sql="SELECT SUM(orders.total_amount) FROM orders GROUP BY orders.created_at LIMIT 100",
        parameters={},
        metadata={"tables": ["orders"], "metrics": ["Total Revenue"], "dimensions": ["orders.created_at"]},
    )
    mock_compiler = AsyncMock()
    mock_compiler.compile.return_value = mock_compiled
    mock_compiler_cls.return_value = mock_compiler

    mock_decrypt.return_value = "sqlite:///:memory:"
    mock_execute.return_value = {
        "columns": ["created_at", "sum"],
        "rows": [["2024-01-01", 1000], ["2024-02-01", 2000]],
        "row_count": 2,
    }

    payload = {
        "metric_ids": [data["metric_id"]],
        "dimension_ids": [data["col_created_id"]],
        "limit": 100,
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 200
    resp_data = response.json()
    assert "sql" in resp_data
    assert resp_data["columns"] == ["created_at", "sum"]
    assert resp_data["row_count"] == 2
    assert len(resp_data["rows"]) == 2


# ===================================================================
# Reject SQL Dump (no linked LiveTargetDbModel)
# ===================================================================


@pytest.mark.asyncio
async def test_query_rejects_sql_dump(
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 400 for SQL Dump databases."""
    data = await _seed_imported_schema_only(async_session)

    payload = {
        "metric_ids": [data["metric_id"]],
        "dimension_ids": [],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 400
    assert "Live DB" in response.json()["detail"]


# ===================================================================
# Reject non-existent db_id
# ===================================================================


@pytest.mark.asyncio
async def test_query_rejects_nonexistent_db(
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 404 for non-existent db_id."""
    payload = {
        "metric_ids": [1],
        "dimension_ids": [],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=99999),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 404


# ===================================================================
# Reject non-SELECT via guardrail
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.SemanticQueryCompiler")
async def test_query_rejects_non_select(
    mock_compiler_cls: Any,
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query rejects non-SELECT compiled SQL."""
    data = await _seed_live_db_with_semantic(async_session)

    mock_compiler = AsyncMock()
    mock_compiler.compile.side_effect = ValueError("Only SELECT statements are allowed")
    mock_compiler_cls.return_value = mock_compiler

    payload = {
        "metric_ids": [data["metric_id"]],
        "dimension_ids": [],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 400
    assert "SELECT" in response.json()["detail"]


# ===================================================================
# Compiler error (e.g. draft metric, missing metric)
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.SemanticQueryCompiler")
async def test_query_compiler_error_returns_400(
    mock_compiler_cls: Any,
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 400 when compiler raises ValueError."""
    data = await _seed_live_db_with_semantic(async_session)

    mock_compiler = AsyncMock()
    mock_compiler.compile.side_effect = ValueError("Metric 'Draft' (id=5) is not approved")
    mock_compiler_cls.return_value = mock_compiler

    payload = {
        "metric_ids": [999],
        "dimension_ids": [],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 400


# ===================================================================
# Execution timeout
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.decrypt_conn_url")
@patch("src.api.routes._execute_sql_on_live_db")
@patch("src.api.routes.SemanticQueryCompiler")
async def test_query_timeout_returns_504(
    mock_compiler_cls: Any,
    mock_execute: Any,
    mock_decrypt: Any,
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 504 on execution timeout."""
    data = await _seed_live_db_with_semantic(async_session)

    mock_compiled = CompiledQuery(
        sql="SELECT SUM(orders.total_amount) FROM orders GROUP BY orders.created_at LIMIT 100",
    )
    mock_compiler = AsyncMock()
    mock_compiler.compile.return_value = mock_compiled
    mock_compiler_cls.return_value = mock_compiler

    mock_decrypt.return_value = "sqlite:///:memory:"
    mock_execute.side_effect = TimeoutError("Query execution timed out")

    payload = {
        "metric_ids": [data["metric_id"]],
        "dimension_ids": [data["col_created_id"]],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 504


# ===================================================================
# Validation: missing metric_ids
# ===================================================================


@pytest.mark.asyncio
async def test_query_validation_missing_metric_ids(
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 422 when metric_ids is missing."""
    data = await _seed_live_db_with_semantic(async_session)

    payload = {"dimension_ids": []}

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 422


# ===================================================================
# Validation: empty metric_ids
# ===================================================================


@pytest.mark.asyncio
async def test_query_validation_empty_metric_ids(
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 422 when metric_ids is empty."""
    data = await _seed_live_db_with_semantic(async_session)

    payload = {"metric_ids": [], "dimension_ids": []}

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 422


# ===================================================================
# Execution error (non-timeout)
# ===================================================================


@pytest.mark.asyncio
@patch("src.api.routes.decrypt_conn_url")
@patch("src.api.routes._execute_sql_on_live_db")
@patch("src.api.routes.SemanticQueryCompiler")
async def test_query_execution_error_returns_500(
    mock_compiler_cls: Any,
    mock_execute: Any,
    mock_decrypt: Any,
    client: Any,
    async_session: AsyncSession,
):
    """POST /semantic/{db_id}/query returns 500 on unexpected execution error."""
    data = await _seed_live_db_with_semantic(async_session)

    mock_compiled = CompiledQuery(
        sql="SELECT SUM(orders.total_amount) FROM orders GROUP BY orders.created_at LIMIT 100",
    )
    mock_compiler = AsyncMock()
    mock_compiler.compile.return_value = mock_compiled
    mock_compiler_cls.return_value = mock_compiler

    mock_decrypt.return_value = "sqlite:///:memory:"
    mock_execute.side_effect = RuntimeError("Connection refused")

    payload = {
        "metric_ids": [data["metric_id"]],
        "dimension_ids": [data["col_created_id"]],
    }

    response = await client.post(
        QUERY_ENDPOINT.format(db_id=data["sem_db_id"]),
        json=payload,
        headers=_token_headers(),
    )

    assert response.status_code == 500
