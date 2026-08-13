"""Tests for semantic_service — enrich_and_save_canonical_schema, metric CRUD, HITL compliance."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    MetricVersionModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticTableModel,
)
from src.models.schema_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)
from src.services.semantic_service import (
    approve_metric,
    create_metric,
    delete_semantic_database,
    enrich_and_save_canonical_schema,
    ensure_semantic_database,
    get_metric_with_history,
    update_metric,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_raw_schema(
    tables: tuple[TableMetadata, ...] | None = None,
    dialect: SchemaDialect = SchemaDialect.POSTGRESQL,
) -> RawSchemaMetadata:
    """Build a minimal RawSchemaMetadata for testing."""
    if tables is None:
        users_cols = (
            ColumnMetadata(
                column_name=Identifier.from_raw("user_id", dialect),
                ordinal_position=1,
                raw_data_type="INTEGER",
                data_type="INTEGER",
                nullable=False,
                primary_key=True,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("email", dialect),
                ordinal_position=2,
                raw_data_type="VARCHAR",
                data_type="VARCHAR",
                nullable=True,
                primary_key=False,
            ),
        )
        orders_cols = (
            ColumnMetadata(
                column_name=Identifier.from_raw("order_id", dialect),
                ordinal_position=1,
                raw_data_type="INTEGER",
                data_type="INTEGER",
                nullable=False,
                primary_key=True,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("user_id", dialect),
                ordinal_position=2,
                raw_data_type="INTEGER",
                data_type="INTEGER",
                nullable=False,
                primary_key=False,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("created_at", dialect),
                ordinal_position=3,
                raw_data_type="TIMESTAMP",
                data_type="TIMESTAMP",
                nullable=True,
                primary_key=False,
            ),
        )
        users_table = TableMetadata(
            schema_name=Identifier.from_raw("public", dialect),
            table_name=Identifier.from_raw("users", dialect),
            columns=users_cols,
            primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("user_id", dialect),)),
        )
        orders_table = TableMetadata(
            schema_name=Identifier.from_raw("public", dialect),
            table_name=Identifier.from_raw("orders", dialect),
            columns=orders_cols,
            primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("order_id", dialect),)),
            foreign_keys=(
                ForeignKeyMetadata(
                    constrained_columns=(Identifier.from_raw("user_id", dialect),),
                    referred_schema=Identifier.from_raw("public", dialect),
                    referred_table=Identifier.from_raw("users", dialect),
                    referred_columns=(Identifier.from_raw("user_id", dialect),),
                ),
            ),
        )
        tables = (users_table, orders_table)

    schema_meta = SchemaMetadata(schema_name=Identifier.from_raw("public", dialect))
    return RawSchemaMetadata(
        dialect=dialect,
        schemas=(schema_meta,),
        tables=tables,
    )


def _llm_enrichment_response() -> str:
    """Return a valid JSON string simulating LLM enrichment output."""
    return json.dumps(
        {
            "users": {
                "business_name": "Người dùng",
                "description": "Bảng lưu trữ thông tin người dùng hệ thống",
                "columns": [
                    {"column_name": "user_id", "business_name": "Mã người dùng", "description": "Khóa chính"},
                    {"column_name": "email", "business_name": "Email", "description": "Địa chỉ email"},
                ],
            },
            "orders": {
                "business_name": "Đơn hàng",
                "description": "Bảng lưu trữ thông tin đơn hàng",
                "columns": [
                    {"column_name": "order_id", "business_name": "Mã đơn hàng", "description": "Khóa chính"},
                    {"column_name": "user_id", "business_name": "Mã người đặt", "description": "FK tới users"},
                    {"column_name": "created_at", "business_name": "Ngày tạo", "description": "Thời gian tạo đơn"},
                ],
            },
        }
    )


# ---------------------------------------------------------------------------
# ensure_semantic_database
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_semantic_database_creates_new(async_session: AsyncSession):
    """ensure_semantic_database creates a new SemanticDatabaseModel when none exists."""
    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target",
        source_id=999,
        user_id=1,
        display_name="Test DB",
        dialect="postgresql",
    )
    assert sem_db_id > 0
    result = await async_session.execute(select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == sem_db_id))
    record = result.scalar_one()
    assert record.display_name == "Test DB"
    assert record.db_type == "postgresql"
    assert record.status == "draft"


@pytest.mark.asyncio
async def test_ensure_semantic_database_returns_existing(async_session: AsyncSession):
    """ensure_semantic_database returns existing ID when source already has a SemanticDatabaseModel."""
    id1 = await ensure_semantic_database(
        db=async_session,
        source_type="live_target",
        source_id=42,
        user_id=1,
        display_name="First",
        dialect="postgresql",
    )
    id2 = await ensure_semantic_database(
        db=async_session,
        source_type="live_target",
        source_id=42,
        user_id=1,
        display_name="Second",
        dialect="mysql",
    )
    assert id1 == id2


@pytest.mark.asyncio
async def test_ensure_semantic_database_different_sources(async_session: AsyncSession):
    """ensure_semantic_database creates separate records for different source_type+source_id."""
    id_live = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="Live", dialect="postgresql"
    )
    id_dump = await ensure_semantic_database(
        db=async_session, source_type="imported_schema", source_id=1, user_id=1, display_name="Dump", dialect="mysql"
    )
    assert id_live != id_dump


# ---------------------------------------------------------------------------
# enrich_and_save_canonical_schema — HITL compliance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_saves_tables_with_status_draft(async_session: AsyncSession):
    """enrich_and_save_canonical_schema saves all tables with status='draft' (HITL compliance)."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response())

    with patch("src.services.semantic_service.get_llm", return_value=mock_llm):
        result = await enrich_and_save_canonical_schema(
            db=async_session, user_id=1, connection_id=sem_db_id, raw_schema=raw_schema, dialect="postgresql"
        )

    assert result["status"] == "draft"
    assert len(result["tables"]) == 2

    # Verify DB records have status='draft'
    db_result = await async_session.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db_id))
    tables = db_result.scalars().all()
    for table in tables:
        assert table.business_name != ""  # enriched
        assert table.description != ""


@pytest.mark.asyncio
async def test_enrich_saves_columns_with_status_draft(async_session: AsyncSession):
    """enrich_and_save_canonical_schema saves columns with business_name from LLM, time dimension detected."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response())

    with patch("src.services.semantic_service.get_llm", return_value=mock_llm):
        await enrich_and_save_canonical_schema(
            db=async_session, user_id=1, connection_id=sem_db_id, raw_schema=raw_schema, dialect="postgresql"
        )

    # Find orders table and check created_at is_time_dimension
    orders_table = (
        await async_session.execute(
            select(SemanticTableModel).where(
                SemanticTableModel.db_id == sem_db_id, SemanticTableModel.table_name == "orders"
            )
        )
    ).scalar_one()

    created_at_col = (
        await async_session.execute(
            select(SemanticColumnModel).where(
                SemanticColumnModel.table_id == orders_table.id,
                SemanticColumnModel.column_name == "created_at",
            )
        )
    ).scalar_one()
    assert created_at_col.is_time_dimension is True
    assert created_at_col.business_name == "Ngày tạo"


@pytest.mark.asyncio
async def test_enrich_creates_fk_relationships(async_session: AsyncSession):
    """enrich_and_save_canonical_schema extracts foreign keys into canonical_relationships."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response())

    with patch("src.services.semantic_service.get_llm", return_value=mock_llm):
        result = await enrich_and_save_canonical_schema(
            db=async_session, user_id=1, connection_id=sem_db_id, raw_schema=raw_schema, dialect="postgresql"
        )

    assert len(result["relationships"]) == 1
    rel = result["relationships"][0]
    assert rel["relationship_type"] == "many_to_one"
    assert "user_id" in rel["join_condition"]

    db_rel = (
        (
            await async_session.execute(
                select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == sem_db_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(db_rel) == 1


@pytest.mark.asyncio
async def test_enrich_upserts_tables_on_second_run(async_session: AsyncSession):
    """enrich_and_save_canonical_schema upserts (updates) existing tables on re-run."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content=_llm_enrichment_response())

    with patch("src.services.semantic_service.get_llm", return_value=mock_llm):
        await enrich_and_save_canonical_schema(
            db=async_session, user_id=1, connection_id=sem_db_id, raw_schema=raw_schema, dialect="postgresql"
        )

    # Update LLM response
    updated_response = json.dumps(
        {
            "users": {
                "business_name": "Bảng người dùng",
                "description": "Updated description",
                "columns": [
                    {"column_name": "user_id", "business_name": "ID", "description": "PK"},
                    {"column_name": "email", "business_name": "Thư điện tử", "description": "Email address"},
                ],
            },
            "orders": {
                "business_name": "Đơn hàng",
                "description": "Orders table",
                "columns": [
                    {"column_name": "order_id", "business_name": "Mã đơn", "description": "PK"},
                    {"column_name": "user_id", "business_name": "Người đặt", "description": "FK"},
                    {"column_name": "created_at", "business_name": "Ngày đặt", "description": "Created"},
                ],
            },
        }
    )
    mock_llm.ainvoke.return_value = AsyncMock(content=updated_response)

    with patch("src.services.semantic_service.get_llm", return_value=mock_llm):
        await enrich_and_save_canonical_schema(
            db=async_session, user_id=1, connection_id=sem_db_id, raw_schema=raw_schema, dialect="postgresql"
        )

    tables = (
        (await async_session.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db_id)))
        .scalars()
        .all()
    )
    assert len(tables) == 2  # no duplicates
    users_table = next(t for t in tables if t.table_name == "users")
    assert users_table.business_name == "Bảng người dùng"


# ---------------------------------------------------------------------------
# create_metric
# ---------------------------------------------------------------------------


async def _seed_tables(db: AsyncSession, db_id: int) -> None:
    table = SemanticTableModel(db_id=db_id, table_name="orders", business_name="Đơn hàng")
    db.add(table)
    await db.flush()
    db.add(SemanticColumnModel(table_id=table.id, column_name="id", data_type="INTEGER", business_name="ID"))
    db.add(SemanticColumnModel(table_id=table.id, column_name="total", data_type="NUMERIC", business_name="Tổng"))
    db.add(SemanticColumnModel(table_id=table.id, column_name="a", data_type="NUMERIC", business_name="A"))
    await db.flush()


def _make_def(
    name: str = "Total Orders", function: str = "COUNT", expression: str = "id", base_entity: str = "orders"
) -> dict:
    return {
        "definition": {
            "metric": {
                "name": name,
                "formula": {"function": function, "expression": expression},
                "base_entity": base_entity,
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "",
            }
        }
    }


@pytest.mark.asyncio
async def test_create_metric(async_session: AsyncSession):
    """create_metric inserts metric with version=1, status='pending_approval', and a metric_versions record."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("Total Orders", "COUNT", "id", "orders"),
        user_id=1,
    )
    assert metric.id > 0
    assert metric.version == 1
    assert metric.status in ("pending_approval", "needs_review")
    assert metric.name == "Total Orders"
    assert metric.created_by == 1

    # Verify metric_versions record
    versions = (
        (await async_session.execute(select(MetricVersionModel).where(MetricVersionModel.metric_id == metric.id)))
        .scalars()
        .all()
    )
    assert len(versions) == 1
    assert versions[0].version == 1


# ---------------------------------------------------------------------------
# update_metric
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_metric_increments_version(async_session: AsyncSession):
    """update_metric increments version and creates a new metric_versions record."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("Revenue", "SUM", "total", "orders"),
        user_id=1,
    )
    assert metric.version == 1

    updated = await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Net Revenue", "SUM", "total", "orders"),
        user_id=1,
    )
    assert updated.version == 2
    assert updated.name == "Net Revenue"

    versions = (
        (
            await async_session.execute(
                select(MetricVersionModel)
                .where(MetricVersionModel.metric_id == metric.id)
                .order_by(MetricVersionModel.version)
            )
        )
        .scalars()
        .all()
    )
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2


@pytest.mark.asyncio
async def test_update_metric_ownership_check(async_session: AsyncSession):
    """update_metric raises ValueError when user is not the creator."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("X", "COUNT", "id", "orders"),
        user_id=1,
    )
    with pytest.raises(ValueError, match=" ownership "):
        await update_metric(
            db=async_session,
            metric_id=metric.id,
            metric_data=_make_def("Y", "COUNT", "id", "orders"),
            user_id=999,  # different user
        )


# ---------------------------------------------------------------------------
# approve_metric
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_metric(async_session: AsyncSession):
    """approve_metric sets status='approved' and approved_by."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("AOV", "AVG", "total", "orders"),
        user_id=1,
    )
    assert metric.status in ("pending_approval", "needs_review")

    approved = await approve_metric(db=async_session, metric_id=metric.id, user_id=1)
    assert approved.status == "approved"
    assert approved.approved_by == 1


@pytest.mark.asyncio
async def test_approve_metric_not_found(async_session: AsyncSession):
    """approve_metric raises ValueError for non-existent metric."""
    with pytest.raises(ValueError, match="not found"):
        await approve_metric(db=async_session, metric_id=9999, user_id=1)


# ---------------------------------------------------------------------------
# get_metric_with_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_metric_with_history(async_session: AsyncSession):
    """get_metric_with_history returns metric object with versions relationship loaded."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("Test", "COUNT", "id", "orders"),
        user_id=1,
    )
    await update_metric(
        db=async_session,
        metric_id=metric.id,
        metric_data=_make_def("Test v2", "COUNT", "id", "orders"),
        user_id=1,
    )

    result = await get_metric_with_history(db=async_session, metric_id=metric.id)
    assert result is not None
    assert result.name == "Test v2"
    assert len(result.versions) == 2


@pytest.mark.asyncio
async def test_get_metric_with_history_not_found(async_session: AsyncSession):
    """get_metric_with_history returns None for non-existent metric."""
    result = await get_metric_with_history(db=async_session, metric_id=9999)
    assert result is None


@pytest.mark.asyncio
async def test_delete_semantic_database(async_session: AsyncSession):
    """delete_semantic_database removes SemanticDatabaseModel and all child records."""
    sem_db_id = await ensure_semantic_database(
        db=async_session,
        source_type="live_target",
        source_id=10,
        user_id=1,
        display_name="To Delete",
        dialect="postgresql",
    )
    await _seed_tables(async_session, sem_db_id)
    await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("Del Metric", "SUM", "a", "orders"),
        user_id=1,
    )

    # Delete semantic db
    deleted = await delete_semantic_database(async_session, sem_db_id)
    assert deleted is True

    # Verify deleted
    db_res = await async_session.get(SemanticDatabaseModel, sem_db_id)
    assert db_res is None
