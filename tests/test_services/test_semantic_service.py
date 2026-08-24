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
    SemanticMetricModel,
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
from src.services.metric_rollback import rollback_metric
from src.services.semantic_service import (
    _pydantic_tables_to_typeddict,
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
                column_name=Identifier.from_raw("id", dialect),
                ordinal_position=2,
                raw_data_type="INTEGER",
                data_type="INTEGER",
                nullable=False,
                primary_key=False,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("user_id", dialect),
                ordinal_position=3,
                raw_data_type="INTEGER",
                data_type="INTEGER",
                nullable=False,
                primary_key=False,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("total", dialect),
                ordinal_position=4,
                raw_data_type="NUMERIC",
                data_type="NUMERIC",
                nullable=True,
                primary_key=False,
            ),
            ColumnMetadata(
                column_name=Identifier.from_raw("created_at", dialect),
                ordinal_position=5,
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
                    {"column_name": "id", "business_name": "ID", "description": "Định danh"},
                    {"column_name": "user_id", "business_name": "Mã người đặt", "description": "FK tới users"},
                    {"column_name": "total", "business_name": "Tổng tiền", "description": "Tổng tiền đơn hàng"},
                    {"column_name": "created_at", "business_name": "Ngày tạo", "description": "Thời gian tạo đơn"},
                ],
            },
        }
    )


def _hitl_enrichment() -> dict:
    """Build enrichment dict in list format matching _make_raw_schema() table order."""
    return {
        "tables": [
            {
                "table_name": "users",
                "business_name": "Người dùng",
                "description": "Bảng lưu trữ thông tin người dùng hệ thống",
                "columns": [
                    {"column_name": "user_id", "business_name": "Mã người dùng", "description": "Khóa chính"},
                    {"column_name": "email", "business_name": "Email", "description": "Địa chỉ email"},
                ],
            },
            {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "description": "Bảng lưu trữ thông tin đơn hàng",
                "columns": [
                    {"column_name": "order_id", "business_name": "Mã đơn hàng", "description": "Khóa chính"},
                    {"column_name": "id", "business_name": "ID", "description": "Định danh"},
                    {"column_name": "user_id", "business_name": "Mã người đặt", "description": "FK tới users"},
                    {"column_name": "total", "business_name": "Tổng tiền", "description": "Tổng tiền đơn hàng"},
                    {"column_name": "created_at", "business_name": "Ngày tạo", "description": "Thời gian tạo đơn"},
                ],
            },
        ]
    }


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
    """enrich_and_save_canonical_schema parks every enriched table in pending_review (HITL gate)."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    result = await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=_hitl_enrichment(),
    )

    assert result["status"] == "pending_review"
    assert result["pending_tables"] == 2
    assert result["pending_columns"] > 0
    assert len(result["tables"]) == 2

    # AI proposals are stored but not yet officially approved
    db_result = await async_session.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db_id))
    tables = db_result.scalars().all()
    for table in tables:
        assert table.business_name != ""  # enriched
        assert table.description != ""
        assert table.ai_business_name == table.business_name
        assert table.review_status == "pending_review"
        assert table.reviewed_by is None


@pytest.mark.asyncio
async def test_enrich_saves_columns_with_status_draft(async_session: AsyncSession):
    """enrich_and_save_canonical_schema saves columns with business_name from LLM, time dimension detected."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=_hitl_enrichment(),
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

    result = await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=_hitl_enrichment(),
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

    await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=_hitl_enrichment(),
    )

    # Update enrichment data
    updated_enrichment = {
        "tables": [
            {
                "table_name": "users",
                "business_name": "Bảng người dùng",
                "description": "Updated description",
                "columns": [
                    {"column_name": "user_id", "business_name": "ID", "description": "PK"},
                    {"column_name": "email", "business_name": "Thư điện tử", "description": "Email address"},
                ],
            },
            {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "description": "Orders table",
                "columns": [
                    {"column_name": "order_id", "business_name": "Mã đơn", "description": "PK"},
                    {"column_name": "user_id", "business_name": "Người đặt", "description": "FK"},
                    {"column_name": "created_at", "business_name": "Ngày đặt", "description": "Created"},
                ],
            },
        ]
    }

    await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=updated_enrichment,
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
    table = SemanticTableModel(db_id=db_id, table_name="orders", business_name="Đơn hàng", primary_key_column="id")
    db.add(table)
    await db.flush()
    db.add(
        SemanticColumnModel(
            table_id=table.id, column_name="id", data_type="INTEGER", business_name="ID", is_primary_key=True
        )
    )
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
async def test_enrich_saves_allowed_values_from_sample_values(async_session: AsyncSession):
    """enrich_and_save_canonical_schema persists sample_values as allowed_values in SemanticColumnModel."""
    dialect = SchemaDialect.POSTGRESQL
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
            column_name=Identifier.from_raw("status", dialect),
            ordinal_position=2,
            raw_data_type="VARCHAR",
            data_type="VARCHAR",
            nullable=True,
            primary_key=False,
            sample_values=("active", "inactive"),
        ),
    )
    table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("users", dialect),
        columns=users_cols,
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("user_id", dialect),)),
    )
    raw_schema = RawSchemaMetadata(
        dialect=dialect,
        schemas=(
            SchemaMetadata(
                schema_name=Identifier.from_raw("public", dialect),
            ),
        ),
        tables=(table,),
    )

    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    hitl = {
        "tables": [
            {
                "table_name": "users",
                "business_name": "Người dùng",
                "description": "Test",
                "columns": [
                    {"column_name": "user_id", "business_name": "ID", "description": "PK"},
                    {"column_name": "status", "business_name": "Trạng thái", "description": "Status"},
                ],
            }
        ]
    }

    await enrich_and_save_canonical_schema(
        db=async_session,
        user_id=1,
        connection_id=sem_db_id,
        raw_schema=raw_schema,
        dialect="postgresql",
        enrichment=hitl,
    )

    users_table = (
        await async_session.execute(
            select(SemanticTableModel).where(
                SemanticTableModel.db_id == sem_db_id, SemanticTableModel.table_name == "users"
            )
        )
    ).scalar_one()

    status_col = (
        await async_session.execute(
            select(SemanticColumnModel).where(
                SemanticColumnModel.table_id == users_table.id,
                SemanticColumnModel.column_name == "status",
            )
        )
    ).scalar_one()
    assert status_col.allowed_values == ["active", "inactive"]

    user_id_col = (
        await async_session.execute(
            select(SemanticColumnModel).where(
                SemanticColumnModel.table_id == users_table.id,
                SemanticColumnModel.column_name == "user_id",
            )
        )
    ).scalar_one()
    assert user_id_col.allowed_values is None


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


# ---------------------------------------------------------------------------
# Task 6: Two-Pass enrichment integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hitl_enrichment_skips_llm(async_session: AsyncSession):
    """When enrichment is provided (HITL), _call_llm_enrichment must NOT be called."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    with patch("src.services.semantic_service._call_llm_enrichment") as mock_llm:
        result = await enrich_and_save_canonical_schema(
            db=async_session,
            user_id=1,
            connection_id=sem_db_id,
            raw_schema=raw_schema,
            dialect="postgresql",
            enrichment=_hitl_enrichment(),
        )
        mock_llm.assert_not_called()

    assert result["status"] == "pending_review"
    assert len(result["tables"]) == 2

    db_result = await async_session.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == sem_db_id))
    tables = db_result.scalars().all()
    for table in tables:
        assert table.business_name != ""


@pytest.mark.asyncio
async def test_two_pass_pipeline_called_when_no_enrichment(async_session: AsyncSession):
    """When enrichment is None, Two-Pass pipeline (execute_pass1 + enrich_clusters_parallel) must be called."""
    raw_schema = _make_raw_schema()
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )

    with (
        patch("src.services.semantic_service.execute_pass1", new_callable=AsyncMock) as mock_pass1,
        patch("src.services.semantic_service.enrich_clusters_parallel", new_callable=AsyncMock) as mock_pass2,
        patch("src.services.semantic_service.cluster_tables") as mock_cluster,
    ):
        mock_pass1.return_value = {"orders.user_id": "Users table"}
        mock_cluster.return_value = [[t] for t in _pydantic_tables_to_typeddict(raw_schema.tables)]
        mock_pass2.return_value = {
            "public.users": {
                "table_name": "users",
                "business_name": "Người dùng",
                "description": "Users table",
                "columns": [
                    {"column_name": "user_id", "business_name": "ID", "description": "PK"},
                    {"column_name": "email", "business_name": "Email", "description": "Email"},
                ],
            },
            "public.orders": {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "description": "Orders table",
                "columns": [
                    {"column_name": "order_id", "business_name": "Order ID", "description": "PK"},
                    {"column_name": "id", "business_name": "ID", "description": "ID"},
                    {"column_name": "user_id", "business_name": "User ID", "description": "FK"},
                    {"column_name": "total", "business_name": "Total", "description": "Total"},
                    {"column_name": "created_at", "business_name": "Created", "description": "Created"},
                ],
            },
        }

        result = await enrich_and_save_canonical_schema(
            db=async_session,
            user_id=1,
            connection_id=sem_db_id,
            raw_schema=raw_schema,
            dialect="postgresql",
        )

        mock_pass1.assert_called_once()
        mock_cluster.assert_called_once()
        mock_pass2.assert_called_once()

    assert result["status"] == "pending_review"
    assert len(result["tables"]) == 2


def test_pydantic_tables_to_typeddict_references():
    """_pydantic_tables_to_typeddict correctly maps FK references onto columns."""
    dialect = SchemaDialect.POSTGRESQL
    users_table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("users", dialect),
        columns=(
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
        ),
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("user_id", dialect),)),
    )
    orders_table = TableMetadata(
        schema_name=Identifier.from_raw("public", dialect),
        table_name=Identifier.from_raw("orders", dialect),
        columns=(
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
                nullable=True,
                primary_key=False,
            ),
        ),
        primary_key=PrimaryKeyMetadata(constrained_columns=(Identifier.from_raw("order_id", dialect),)),
        foreign_keys=(
            ForeignKeyMetadata(
                constraint_name=Identifier.from_raw("fk_user", dialect),
                constrained_columns=(Identifier.from_raw("user_id", dialect),),
                referred_schema=Identifier.from_raw("public", dialect),
                referred_table=Identifier.from_raw("users", dialect),
                referred_columns=(Identifier.from_raw("user_id", dialect),),
            ),
        ),
    )

    result = _pydantic_tables_to_typeddict((users_table, orders_table))

    assert len(result) == 2

    users_td = result[0]
    assert users_td["table_name"] == "users"
    assert users_td["schema_name"] == "public"
    assert users_td["primary_keys"] == ["user_id"]
    assert users_td["foreign_keys"] == []
    for col in users_td["columns"]:
        assert col["references"] is None

    orders_td = result[1]
    assert orders_td["table_name"] == "orders"
    assert len(orders_td["foreign_keys"]) == 1
    assert orders_td["foreign_keys"][0]["constrained_columns"] == ["user_id"]
    assert orders_td["foreign_keys"][0]["referred_table"] == "users"
    assert orders_td["foreign_keys"][0]["referred_columns"] == ["user_id"]

    user_id_col = next(c for c in orders_td["columns"] if c["column_name"] == "user_id")
    assert user_id_col["is_foreign_key"] is True
    assert user_id_col["references"] is not None
    assert user_id_col["references"]["table"] == "users"
    assert user_id_col["references"]["column"] == "user_id"
    assert user_id_col["references"]["schema"] == "public"

    order_id_col = next(c for c in orders_td["columns"] if c["column_name"] == "order_id")
    assert order_id_col["is_foreign_key"] is False
    assert order_id_col["references"] is None


# ---------------------------------------------------------------------------
# Task 3: Unverified metric lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_metric_as_unverified(async_session: AsyncSession):
    """create_metric persists an explicit server-controlled unverified status."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("Unverified Metric", "COUNT", "id", "orders"),
        user_id=1,
        status_override="unverified",
    )
    assert metric.status == "unverified"
    assert metric.definition["metric"]["status"] == "unverified"


@pytest.mark.asyncio
async def test_approve_unverified_metric(async_session: AsyncSession):
    """approve_metric transitions an unverified metric to approved when no diagnostics."""
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
    # Manually set to unverified to test transition
    metric.status = "unverified"
    await async_session.flush()

    approved = await approve_metric(db=async_session, metric_id=metric.id, user_id=1)
    assert approved.status == "approved"
    assert approved.approved_by == 1


@pytest.mark.asyncio
async def test_approve_metric_blocks_when_diagnostics(async_session: AsyncSession):
    """approve_metric raises ValueError and sets status='needs_review' when diagnostics exist."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    # Seed a table WITHOUT a primary key to trigger MISSING_GRAIN diagnostic
    table = SemanticTableModel(
        db_id=sem_db_id, table_name="no_pk_table", business_name="No PK", primary_key_column=None
    )
    async_session.add(table)
    await async_session.flush()
    async_session.add(
        SemanticColumnModel(table_id=table.id, column_name="val", data_type="NUMERIC", business_name="Val")
    )
    await async_session.flush()

    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("No PK Metric", "SUM", "val", "no_pk_table"),
        user_id=1,
    )
    # create_metric sets status='needs_review' when diagnostics are present
    assert metric.status == "needs_review"

    with pytest.raises(ValueError, match="requires review"):
        await approve_metric(db=async_session, metric_id=metric.id, user_id=1)

    # Refresh and confirm status remains needs_review
    await async_session.refresh(metric)
    assert metric.status == "needs_review"
    assert metric.approved_by is None


@pytest.mark.asyncio
async def test_approve_metric_raises_typed_review_error(async_session: AsyncSession):
    """approve_metric raises MetricRequiresReviewError (a ValueError subclass) when diagnostics exist."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    table = SemanticTableModel(
        db_id=sem_db_id, table_name="no_pk_table", business_name="No PK", primary_key_column=None
    )
    async_session.add(table)
    await async_session.flush()
    async_session.add(
        SemanticColumnModel(table_id=table.id, column_name="val", data_type="NUMERIC", business_name="Val")
    )
    await async_session.flush()

    metric = await create_metric(
        db=async_session,
        connection_id=sem_db_id,
        metric_data=_make_def("No PK Typed", "SUM", "val", "no_pk_table"),
        user_id=1,
    )

    with pytest.raises(ValueError) as excinfo:
        await approve_metric(db=async_session, metric_id=metric.id, user_id=1)
    assert type(excinfo.value).__name__ == "MetricRequiresReviewError"


# ---------------------------------------------------------------------------
# rollback_metric — non-destructive revert as a new version
# ---------------------------------------------------------------------------


async def _seed_three_versions(db: AsyncSession, sem_db_id: int) -> SemanticMetricModel:
    """Create a metric and update it twice so v1/v2/v3 snapshots exist."""
    metric = await create_metric(
        db=db,
        connection_id=sem_db_id,
        metric_data=_make_def("Revenue V1", "COUNT", "id", "orders"),
        user_id=1,
    )
    await update_metric(
        db=db, metric_id=metric.id, metric_data=_make_def("Revenue V2", "SUM", "total", "orders"), user_id=1
    )
    await update_metric(
        db=db, metric_id=metric.id, metric_data=_make_def("Revenue V3", "AVG", "total", "orders"), user_id=1
    )
    return metric


async def _fetch_versions(db: AsyncSession, metric_id: int) -> list[MetricVersionModel]:
    result = await db.execute(
        select(MetricVersionModel).where(MetricVersionModel.metric_id == metric_id).order_by(MetricVersionModel.version)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_rollback_metric_appends_revert_version(async_session: AsyncSession):
    """rollback to v2 republishes the v2 payload as a new v4 and keeps all history."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)

    history_before = await _fetch_versions(async_session, metric.id)
    assert [v.version for v in history_before] == [1, 2, 3]
    v1_snapshot = history_before[0].definition
    v2_snapshot = history_before[1].definition

    rolled = await rollback_metric(db=async_session, metric_id=metric.id, target_version=2, actor_id=7)

    assert rolled.version == 4
    assert rolled.status == "approved"
    assert rolled.approved_by == 7
    assert rolled.formula == "total"
    assert rolled.aggregation_type == "SUM"
    assert rolled.definition["metric"]["name"] == "Revenue V2"
    assert rolled.definition["metric"]["formula"]["expression"] == "total"
    assert rolled.definition["metric"]["formula"]["function"] == "SUM"
    assert rolled.definition["metric"]["status"] == "approved"
    # Identity fields are preserved, not rewound.
    assert rolled.source == "manual"
    assert rolled.created_by == 1

    remaining = await _fetch_versions(async_session, metric.id)
    assert [v.version for v in remaining] == [1, 2, 3, 4]
    assert remaining[0].id == history_before[0].id
    assert remaining[0].definition == v1_snapshot
    assert remaining[1].id == history_before[1].id
    assert remaining[1].definition == v2_snapshot
    revert = remaining[3]
    assert revert.status == "approved"
    assert revert.parent_version == 2
    assert revert.changed_by == 7
    assert revert.approved_by == 7
    assert "2" in revert.change_reason
    assert revert.definition["metric"]["formula"]["expression"] == "total"


@pytest.mark.asyncio
@pytest.mark.parametrize(("target_version",), [(0,), (3,), (99,)])
async def test_rollback_metric_rejects_invalid_targets(async_session: AsyncSession, target_version: int):
    """rollback_metric raises ValueError for past-zero, current, and future targets."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)

    with pytest.raises(ValueError, match="version"):
        await rollback_metric(db=async_session, metric_id=metric.id, target_version=target_version, actor_id=1)


@pytest.mark.asyncio
async def test_rollback_metric_rejects_legacy_null_target(async_session: AsyncSession):
    """rollback_metric raises ValueError when the target snapshot has no stored definition."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)

    legacy = (await _fetch_versions(async_session, metric.id))[1]
    legacy.definition = None
    await async_session.flush()

    with pytest.raises(ValueError, match="version"):
        await rollback_metric(db=async_session, metric_id=metric.id, target_version=2, actor_id=1)


@pytest.mark.asyncio
async def test_rollback_metric_ownership_check(async_session: AsyncSession):
    """rollback_metric raises ValueError when require_ownership is set and actor is not the creator."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)

    with pytest.raises(ValueError, match=" ownership "):
        await rollback_metric(
            db=async_session, metric_id=metric.id, target_version=2, actor_id=999, require_ownership=True
        )


@pytest.mark.asyncio
async def test_rollback_metric_missing_snapshot_leaves_state_unchanged(async_session: AsyncSession):
    """A range-valid target whose version row was deleted raises and changes nothing."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)
    metric_id = metric.id
    await async_session.commit()

    v2_row = (await _fetch_versions(async_session, metric_id))[1]
    await async_session.delete(v2_row)
    await async_session.flush()

    with pytest.raises(ValueError, match="version"):
        await rollback_metric(db=async_session, metric_id=metric_id, target_version=2, actor_id=1)

    await async_session.rollback()

    refreshed = (
        (await async_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)))
        .scalars()
        .one()
    )
    assert refreshed.version == 3
    assert refreshed.status == "pending_approval"
    assert refreshed.approved_by is None
    remaining = await _fetch_versions(async_session, metric_id)
    assert [v.version for v in remaining] == [1, 2, 3]


@pytest.mark.asyncio
async def test_rollback_metric_invalid_target_leaves_state_unchanged(async_session: AsyncSession):
    """When the historical definition no longer validates, current row and history stay untouched."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)
    metric_id = metric.id
    await async_session.commit()

    orders_table = (
        (
            await async_session.execute(
                select(SemanticTableModel).where(
                    SemanticTableModel.db_id == sem_db_id, SemanticTableModel.table_name == "orders"
                )
            )
        )
        .scalars()
        .one()
    )
    total_col = (
        (
            await async_session.execute(
                select(SemanticColumnModel).where(
                    SemanticColumnModel.table_id == orders_table.id, SemanticColumnModel.column_name == "total"
                )
            )
        )
        .scalars()
        .one()
    )
    await async_session.delete(total_col)
    await async_session.flush()

    with pytest.raises(ValueError):
        await rollback_metric(db=async_session, metric_id=metric_id, target_version=2, actor_id=1)

    await async_session.rollback()

    refreshed = (
        (await async_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)))
        .scalars()
        .one()
    )
    assert refreshed.version == 3
    assert refreshed.status == "pending_approval"
    assert refreshed.approved_by is None
    assert refreshed.definition["metric"]["name"] == "Revenue V3"
    remaining = await _fetch_versions(async_session, metric_id)
    assert [v.version for v in remaining] == [1, 2, 3]


@pytest.mark.asyncio
async def test_rollback_metric_compile_failure_leaves_state_unchanged(async_session: AsyncSession):
    """A compile failure after field restoration must not delete history once the session rolls back."""
    sem_db_id = await ensure_semantic_database(
        db=async_session, source_type="live_target", source_id=1, user_id=1, display_name="T", dialect="postgresql"
    )
    await _seed_tables(async_session, sem_db_id)
    metric = await _seed_three_versions(async_session, sem_db_id)
    metric_id = metric.id
    await async_session.commit()

    with patch("src.services.metric_rollback.SemanticQueryCompiler") as compiler_cls:
        compiler_cls.return_value.compile = AsyncMock(side_effect=ValueError("compile exploded"))
        with pytest.raises(ValueError, match="compile exploded"):
            await rollback_metric(db=async_session, metric_id=metric_id, target_version=2, actor_id=1)

    await async_session.rollback()

    refreshed = (
        (await async_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)))
        .scalars()
        .one()
    )
    assert refreshed.version == 3
    assert refreshed.status == "pending_approval"
    assert refreshed.approved_by is None
    remaining = await _fetch_versions(async_session, metric_id)
    assert [v.version for v in remaining] == [1, 2, 3]
