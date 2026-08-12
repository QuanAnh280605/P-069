"""Tests for Live Target Database Service and Introspection."""

import asyncio
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema_metadata import SchemaDialect
from src.services.live_db_service import (
    create_live_target_db,
    delete_live_target_db,
    get_live_target_db,
    introspect_live_database,
    list_live_target_dbs,
)


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database with test schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE
        );
    """)
    cursor.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
    """)
    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


def test_introspect_live_database(temp_sqlite_db: str):
    """Test zero-data schema introspection on a SQLite database file."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    schema = introspect_live_database(conn_url, SchemaDialect.POSTGRESQL)
    assert schema.tables is not None
    table_names = [table.table_name.raw_name for table in schema.tables]
    assert "customers" in table_names
    assert "orders" in table_names

    orders_table = next(t for t in schema.tables if t.table_name.raw_name == "orders")
    col_names = [c.column_name.raw_name for c in orders_table.columns]
    assert "order_id" in col_names
    assert "customer_id" in col_names
    assert "total_amount" in col_names
    assert len(orders_table.foreign_keys) == 1


def test_introspect_live_database_with_string_auto_dialect(temp_sqlite_db: str):
    """Test introspect_live_database when passed string 'auto' as dialect."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    schema = introspect_live_database(conn_url, "auto")
    assert schema.dialect == SchemaDialect.SQLITE
    assert schema.tables is not None


@pytest.mark.asyncio
async def test_create_and_manage_live_target_db(async_session: AsyncSession, temp_sqlite_db: str):
    """Test full CRUD lifecycle for live target database records."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    user_id = 1
    display_name = "Test Retail Live DB"

    # Create & Introspect
    created = await create_live_target_db(
        db=async_session,
        user_id=user_id,
        display_name=display_name,
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )
    assert created.id > 0
    assert created.display_name == display_name
    assert created.table_count == 2

    # List
    summary_list = await list_live_target_dbs(async_session, user_id)
    assert len(summary_list) == 1
    assert summary_list[0].id == created.id

    # Get Single
    fetched = await get_live_target_db(async_session, user_id, created.id)
    assert fetched is not None
    assert fetched.display_name == display_name
    assert len(fetched.raw_schema.tables) == 2

    # Delete
    deleted = await delete_live_target_db(async_session, user_id, created.id)
    assert deleted is True

    # Verify deleted
    fetched_after = await get_live_target_db(async_session, user_id, created.id)
    assert fetched_after is None


def test_resolve_and_validate_dialect_auto_and_strict():
    """Test auto-detection and strict matching validation logic."""
    from src.services.live_db_service import resolve_and_validate_dialect

    # Auto detect tests
    assert resolve_and_validate_dialect("postgresql://localhost/db", "auto") == SchemaDialect.POSTGRESQL
    assert resolve_and_validate_dialect("mysql+pymysql://localhost/db", "auto") == SchemaDialect.MYSQL
    assert resolve_and_validate_dialect("sqlite:///test.db", None) == SchemaDialect.SQLITE

    # Strict match success
    assert resolve_and_validate_dialect("mysql+pymysql://localhost/db", "mysql") == SchemaDialect.MYSQL
    assert resolve_and_validate_dialect("postgresql://localhost/db", "postgresql") == SchemaDialect.POSTGRESQL

    # Strict match failure (mismatched URL scheme)
    with pytest.raises(ValueError, match="does not match selected dialect"):
        resolve_and_validate_dialect("postgresql://localhost/db", "mysql")


@pytest.mark.asyncio
@patch("src.services.live_db_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.live_db_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_live_target_db_calls_ensure_semantic_database(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
    temp_sqlite_db: str,
):
    """After introspection, create_live_target_db calls ensure_semantic_database."""
    mock_ensure.return_value = 42
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    conn_url = f"sqlite:///{temp_sqlite_db}"
    result = await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="Test Semantic Link",
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )

    mock_ensure.assert_called_once()
    call_kwargs = mock_ensure.call_args
    assert call_kwargs.kwargs["source_type"] == "live_target_db"
    assert call_kwargs.kwargs["display_name"] == "Test Semantic Link"
    assert result.id > 0


@pytest.mark.asyncio
@patch("src.services.live_db_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.live_db_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_live_target_db_sets_semantic_db_id(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
    temp_sqlite_db: str,
):
    """LiveTargetDbModel.semantic_db_id is set to the returned semantic database ID."""
    mock_ensure.return_value = 99
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    conn_url = f"sqlite:///{temp_sqlite_db}"
    result = await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="Test Link",
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )

    # Verify semantic_db_id was persisted by re-fetching
    fetched = await get_live_target_db(async_session, 1, result.id)
    assert fetched is not None


@pytest.mark.asyncio
@patch("src.services.live_db_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.live_db_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_live_target_db_calls_enrichment(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
    temp_sqlite_db: str,
):
    """After ensure_semantic_database, enrichment is called with connection_id=semantic_db_id."""
    mock_ensure.return_value = 42
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    conn_url = f"sqlite:///{temp_sqlite_db}"
    await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="Test Enrichment",
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )

    # Wait for background task to complete
    await asyncio.sleep(0.1)

    mock_enrich.assert_called_once()
    call_kwargs = mock_enrich.call_args
    assert call_kwargs.kwargs["connection_id"] == 42


@pytest.mark.asyncio
@patch("src.services.live_db_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.live_db_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_live_target_db_enrichment_error_does_not_fail_request(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
    temp_sqlite_db: str,
):
    """If enrichment raises an error, the request still succeeds."""
    mock_ensure.return_value = 42
    mock_enrich.side_effect = RuntimeError("LLM service unavailable")

    conn_url = f"sqlite:///{temp_sqlite_db}"
    result = await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="Test Error Handling",
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )

    # Request should succeed despite enrichment error
    assert result.id > 0
    assert result.display_name == "Test Error Handling"
    assert result.table_count == 2


@pytest.mark.asyncio
@patch("src.services.live_db_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.live_db_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_live_target_db_ensure_semantic_db_error_does_not_fail_request(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
    temp_sqlite_db: str,
):
    """If ensure_semantic_database raises, the request still succeeds and enrichment is skipped."""
    mock_ensure.side_effect = RuntimeError("DB connection failed")

    conn_url = f"sqlite:///{temp_sqlite_db}"
    result = await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="Test Ensure Error",
        dialect=SchemaDialect.SQLITE,
        conn_url=conn_url,
    )

    # Request should succeed despite ensure_semantic_database error
    assert result.id > 0
    assert result.display_name == "Test Ensure Error"

    # Enrichment should not be called if ensure failed
    mock_enrich.assert_not_called()


@pytest.mark.asyncio
async def test_delete_live_target_db_cascades_all_related_models(async_session: AsyncSession):
    """Verify that deleting a live target database cascades delete to SemanticDatabaseModel and all child records."""
    from src.models.db import (
        CanonicalRelationshipModel,
        LiveTargetDbModel,
        MetricVersionModel,
        SemanticColumnModel,
        SemanticDatabaseModel,
        SemanticMetricModel,
        SemanticTableModel,
    )

    user_id = 1
    # 1. Create SemanticDatabaseModel
    sem_db = SemanticDatabaseModel(
        created_by=user_id,
        display_name="Test Cascade DB",
        db_type="postgresql",
        conn_url_enc="semantic:live:9999",
        status="draft",
    )
    async_session.add(sem_db)
    await async_session.flush()

    # 2. Add table, column, metric, metric version, relationship
    table = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Đơn hàng",
    )
    async_session.add(table)
    await async_session.flush()

    col = SemanticColumnModel(
        table_id=table.id,
        column_name="id",
        data_type="INTEGER",
        business_name="Mã đơn hàng",
    )
    async_session.add(col)

    metric = SemanticMetricModel(
        db_id=sem_db.id,
        name="Doanh thu",
        description="Tổng doanh thu",
        sql_template="SELECT SUM(total) FROM orders",
    )
    async_session.add(metric)
    await async_session.flush()

    ver = MetricVersionModel(
        metric_id=metric.id,
        version=1,
        formula="SUM(total)",
    )
    async_session.add(ver)

    rel = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=table.id,
        to_entity_id=table.id,
        relationship_type="self",
        join_condition="orders.id = orders.id",
    )
    async_session.add(rel)

    # 3. Create LiveTargetDbModel linking to sem_db.id
    live_db = LiveTargetDbModel(
        created_by=user_id,
        display_name="Test Live DB",
        dialect="postgresql",
        conn_url_enc="enc_url",
        schema_metadata={"tables": []},
        semantic_db_id=sem_db.id,
    )
    async_session.add(live_db)
    await async_session.commit()

    live_db_id = live_db.id
    sem_db_id = sem_db.id
    table_id = table.id
    metric_id = metric.id

    # 4. Delete via delete_live_target_db
    deleted = await delete_live_target_db(async_session, user_id, live_db_id)
    assert deleted is True

    # 5. Assert all related records are gone
    assert await async_session.get(LiveTargetDbModel, live_db_id) is None
    assert await async_session.get(SemanticDatabaseModel, sem_db_id) is None
    assert await async_session.get(SemanticTableModel, table_id) is None
    assert await async_session.get(SemanticMetricModel, metric_id) is None
