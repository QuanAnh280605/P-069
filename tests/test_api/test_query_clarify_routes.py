"""Integration tests for Guided Wizard AI Query Assistant API endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
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


async def _seed_live_db(db: AsyncSession) -> int:
    """Seed a semantic database backed by a LiveTargetDbModel."""
    stmt = select(UserModel).where(UserModel.id == 1)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = UserModel(
            email="tester@company.com",
            username="tester_user",
            full_name="Tester User",
            hashed_password="hash",
            role="admin",
            status="active",
        )
        db.add(user)
        await db.flush()

    sem_db = SemanticDatabaseModel(
        created_by=user.id,
        display_name="Live Test DB",
        db_type="sqlite",
        conn_url_enc="enc_url",
        status="approved",
    )
    db.add(sem_db)
    await db.flush()

    live_db = LiveTargetDbModel(
        created_by=user.id,
        display_name="Live Test DB",
        dialect="sqlite",
        conn_url_enc="enc_url",
        schema_metadata={},
        semantic_db_id=sem_db.id,
    )
    db.add(live_db)

    table = SemanticTableModel(
        db_id=sem_db.id,
        table_name="sales",
        business_name="Doanh số",
    )
    db.add(table)
    await db.flush()

    col = SemanticColumnModel(
        table_id=table.id,
        column_name="sale_date",
        business_name="Ngày bán",
        data_type="DATE",
    )
    db.add(col)

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Doanh Thu",
        description="Total Revenue",
        sql_template="SELECT SUM(amount) FROM sales",
        status="approved",
        created_by=user.id,
        definition={
            "metric": {
                "name": "Doanh Thu",
                "base_entity": "sales",
                "expression": {"type": "aggregate", "operator": "sum", "column": "amount"},
            }
        },
    )
    db.add(metric)
    await db.commit()
    return sem_db.id


async def _seed_sql_dump_db(db: AsyncSession) -> int:
    """Seed a semantic database backed by an ImportedSchemaModel (SQL Dump)."""
    stmt = select(UserModel).where(UserModel.id == 1)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = UserModel(
            email="dump@company.com",
            username="dump_user",
            full_name="Dump User",
            hashed_password="hash",
            role="admin",
            status="active",
        )
        db.add(user)
        await db.flush()

    sem_db = SemanticDatabaseModel(
        created_by=user.id,
        display_name="Dump DB",
        db_type="postgresql",
        conn_url_enc="enc",
        status="approved",
    )
    db.add(sem_db)
    await db.flush()

    dump = ImportedSchemaModel(
        created_by=user.id,
        display_name="Dump DB",
        dialect="postgresql",
        schema_metadata={},
        semantic_db_id=sem_db.id,
    )
    db.add(dump)
    await db.commit()
    return sem_db.id


@pytest.mark.asyncio
async def test_wizard_start_live_db_success(client: Any, async_session: AsyncSession):
    """Test POST /semantic/{db_id}/query/wizard/start on Live DB."""
    db_id = await _seed_live_db(async_session)
    response = await client.post(
        f"/api/v1/semantic/{db_id}/query/wizard/start",
        headers=_token_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["step"] == 1
    assert len(data["options"]) >= 1
    assert data["options"][0]["label"] == "Doanh Thu"


@pytest.mark.asyncio
async def test_wizard_start_rejects_sql_dump(client: Any, async_session: AsyncSession):
    """Test POST /semantic/{db_id}/query/wizard/start rejects SQL Dump database."""
    db_id = await _seed_sql_dump_db(async_session)
    response = await client.post(
        f"/api/v1/semantic/{db_id}/query/wizard/start",
        headers=_token_headers(),
    )
    assert response.status_code == 400
    assert "Live DB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_wizard_full_flow(client: Any, async_session: AsyncSession):
    """Test full wizard flow (Start -> Step 1 -> Step 2 -> Resolve)."""
    db_id = await _seed_live_db(async_session)
    start_resp = await client.post(
        f"/api/v1/semantic/{db_id}/query/wizard/start",
        headers=_token_headers(),
    )
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    session_id = start_data["session_id"]
    option_id = start_data["options"][0]["id"]

    step_resp = await client.post(
        f"/api/v1/semantic/{db_id}/query/wizard/step",
        json={"session_id": session_id, "option_id": option_id},
        headers=_token_headers(),
    )
    assert step_resp.status_code == 200
    step_data = step_resp.json()
    assert step_data["step"] == 2
    assert len(step_data["options"]) >= 1

    dim_option_id = step_data["options"][0]["id"]
    mock_compiled = CompiledQuery(sql="SELECT SUM(amount) FROM sales", parameters={}, metadata={})
    with patch("src.services.query_clarifier_service.SemanticQueryCompiler.compile", new_callable=AsyncMock, return_value=mock_compiled):
        resolve_resp = await client.post(
            f"/api/v1/semantic/{db_id}/query/wizard/step",
            json={"session_id": session_id, "option_id": dim_option_id},
            headers=_token_headers(),
        )
        assert resolve_resp.status_code == 200
        resolve_data = resolve_resp.json()
        assert resolve_data["step"] == 3
        assert resolve_data["is_completed"] is True
        assert resolve_data["resolved_spec"] is not None
        assert resolve_data["sql_preview"] == "SELECT SUM(amount) FROM sales"
