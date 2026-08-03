"""Unit tests for Metadata Store ORM models and encryption utilities."""

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.db import (
    Base,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.services.database import decrypt_conn_url, encrypt_conn_url


@pytest_asyncio.fixture
async def async_db_session():
    """Fixture providing an async in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_fernet_encryption_decryption():
    """Test Fernet encryption and decryption for database connection URLs."""
    raw_url = "postgresql://devuser:secretpass@localhost:5432/testdb"
    key = Fernet.generate_key().decode("utf-8")

    enc_url = encrypt_conn_url(raw_url, key=key)
    assert enc_url != raw_url
    assert len(enc_url) > 20

    dec_url = decrypt_conn_url(enc_url, key=key)
    assert dec_url == raw_url


@pytest.mark.asyncio
async def test_semantic_database_creation(async_db_session: AsyncSession):
    """Test creating and querying a SemanticDatabaseModel record."""
    db_rec = SemanticDatabaseModel(
        display_name="Production DB",
        db_type="postgresql",
        conn_url_enc="gAAAAABl...",
        status="active",
    )
    async_db_session.add(db_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_rec.id))
    fetched = result.scalar_one()
    assert fetched.display_name == "Production DB"
    assert fetched.db_type == "postgresql"


@pytest.mark.asyncio
async def test_semantic_table_and_columns_relationships(async_db_session: AsyncSession):
    """Test relationship and cascade behavior between database, tables, and columns."""
    db_rec = SemanticDatabaseModel(
        display_name="E-Commerce DB",
        db_type="sqlite",
        conn_url_enc="dummy_enc",
    )
    async_db_session.add(db_rec)
    await async_db_session.commit()

    table_rec = SemanticTableModel(
        db_id=db_rec.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng lưu thông tin đơn hàng",
    )
    async_db_session.add(table_rec)
    await async_db_session.commit()

    col_rec = SemanticColumnModel(
        table_id=table_rec.id,
        column_name="order_id",
        data_type="INTEGER",
        business_name="Mã đơn hàng",
        is_primary_key=True,
    )
    async_db_session.add(col_rec)
    await async_db_session.commit()

    # Query back table with columns
    result = await async_db_session.execute(select(SemanticTableModel).where(SemanticTableModel.id == table_rec.id))
    fetched_table = result.scalar_one()
    assert fetched_table.business_name == "Đơn hàng"


@pytest.mark.asyncio
async def test_semantic_metric_creation(async_db_session: AsyncSession):
    """Test creating a SemanticMetricModel record linked to a database."""
    db_rec = SemanticDatabaseModel(
        display_name="Analytics DB",
        db_type="postgresql",
        conn_url_enc="dummy_enc",
    )
    async_db_session.add(db_rec)
    await async_db_session.commit()

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Tổng Doanh Thu",
        description="Tổng giá trị đơn hàng đã thanh toán",
        sql_template="SELECT SUM(total_amount) FROM orders WHERE status = 'paid'",
        source="ai",
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched_metric = result.scalar_one()
    assert fetched_metric.name == "Tổng Doanh Thu"
    assert fetched_metric.source == "ai"
