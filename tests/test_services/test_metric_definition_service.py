"""Persistence lifecycle tests for canonical metric definitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import SemanticColumnModel, SemanticDatabaseModel, SemanticTableModel
from src.services.semantic_service import approve_metric, create_metric, get_metric_with_history, update_metric


async def _seed(db: AsyncSession) -> int:
    database = SemanticDatabaseModel(
        created_by=1, display_name="Retail", db_type="sqlite", conn_url_enc="enc", status="draft"
    )
    db.add(database)
    await db.flush()
    table = SemanticTableModel(db_id=database.id, table_name="orders", business_name="Đơn hàng")
    db.add(table)
    await db.flush()
    db.add(SemanticColumnModel(table_id=table.id, column_name="total", data_type="NUMERIC", business_name="Tổng"))
    await db.commit()
    return database.id


def _definition(name: str = "Doanh thu") -> dict:
    return {
        "metric": {
            "name": name,
            "formula": {"function": "SUM", "expression": "total"},
            "base_entity": "orders",
            "filters": [],
            "status": "pending_approval",
            "confidence": "high",
            "excluded_notes": "",
        }
    }


@pytest.mark.asyncio
async def test_create_update_approve_and_history(async_session: AsyncSession) -> None:
    db_id = await _seed(async_session)
    metric = await create_metric(async_session, db_id, {"definition": _definition(), "source": "ai"}, 1)
    assert metric.status == "pending_approval"
    assert metric.sql_template == ""
    updated = await update_metric(async_session, metric.id, {"definition": _definition("Doanh thu thuần")}, 1)
    assert updated.version == 2
    assert updated.definition["metric"]["name"] == "Doanh thu thuần"
    approved = await approve_metric(async_session, metric.id, 1)
    assert approved.status == "approved"
    assert approved.definition["metric"]["status"] == "approved"
    loaded = await get_metric_with_history(async_session, metric.id)
    assert len(loaded.versions) == 2
    assert loaded.versions[-1].definition["metric"]["name"] == "Doanh thu thuần"


@pytest.mark.asyncio
async def test_create_rejects_unknown_column(async_session: AsyncSession) -> None:
    db_id = await _seed(async_session)
    definition = _definition()
    definition["metric"]["formula"]["expression"] = "missing"
    with pytest.raises(ValueError, match="Unknown expression columns"):
        await create_metric(async_session, db_id, {"definition": definition}, 1)
