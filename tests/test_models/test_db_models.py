"""Unit tests for Metadata Store ORM models and encryption utilities."""

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.models.db import (
    Base,
    CanonicalRelationshipModel,
    MetricVersionModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
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


@pytest_asyncio.fixture
async def seed_user_and_db(async_db_session: AsyncSession):
    """Seed a user and a semantic database for tests that need them."""
    user = UserModel(
        email="creator@test.com",
        username="creator",
        hashed_password="hash",
        full_name="Test Creator",
        status="active",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    db_rec = SemanticDatabaseModel(
        created_by=user.id,
        display_name="Test DB",
        db_type="postgresql",
        conn_url_enc="dummy_enc",
        status="draft",
    )
    async_db_session.add(db_rec)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    await async_db_session.refresh(db_rec)
    return async_db_session, user, db_rec


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


# --- Tests for expanded SemanticTableModel ---


@pytest.mark.asyncio
async def test_semantic_table_new_fields(seed_user_and_db):
    """Test SemanticTableModel new fields: physical_schema, primary_key_column, created_by."""
    async_db_session, user, db_rec = seed_user_and_db

    table_rec = SemanticTableModel(
        db_id=db_rec.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng đơn hàng",
        physical_schema="public",
        primary_key_column="order_id",
        created_by=user.id,
    )
    async_db_session.add(table_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticTableModel).where(SemanticTableModel.id == table_rec.id))
    fetched = result.scalar_one()
    assert fetched.physical_schema == "public"
    assert fetched.primary_key_column == "order_id"
    assert fetched.created_by == user.id


@pytest.mark.asyncio
async def test_semantic_table_creator_relationship(seed_user_and_db):
    """Test SemanticTableModel.creator relationship to UserModel."""
    async_db_session, user, db_rec = seed_user_and_db

    table_rec = SemanticTableModel(
        db_id=db_rec.id,
        table_name="customers",
        business_name="Khách hàng",
        created_by=user.id,
    )
    async_db_session.add(table_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticTableModel).where(SemanticTableModel.id == table_rec.id))
    fetched = result.scalar_one()
    assert fetched.creator is not None
    assert fetched.creator.id == user.id
    assert fetched.creator.username == "creator"


@pytest.mark.asyncio
async def test_user_created_tables_relationship(seed_user_and_db):
    """Test UserModel.created_tables back_populates relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    table_rec = SemanticTableModel(
        db_id=db_rec.id,
        table_name="products",
        business_name="Sản phẩm",
        created_by=user.id,
    )
    async_db_session.add(table_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(UserModel).where(UserModel.id == user.id).options(selectinload(UserModel.created_tables))
    )
    fetched_user = result.scalar_one()
    assert len(fetched_user.created_tables) == 1
    assert fetched_user.created_tables[0].table_name == "products"


# --- Tests for expanded SemanticColumnModel ---


@pytest.mark.asyncio
async def test_semantic_column_time_dimension(async_db_session: AsyncSession):
    """Test SemanticColumnModel.is_time_dimension field."""
    db_rec = SemanticDatabaseModel(display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_db_session.add(db_rec)
    await async_db_session.flush()

    table_rec = SemanticTableModel(db_id=db_rec.id, table_name="orders", business_name="Đơn hàng")
    async_db_session.add(table_rec)
    await async_db_session.flush()

    col_rec = SemanticColumnModel(
        table_id=table_rec.id,
        column_name="order_date",
        data_type="TIMESTAMP",
        business_name="Ngày đặt hàng",
        is_time_dimension=True,
    )
    async_db_session.add(col_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticColumnModel).where(SemanticColumnModel.id == col_rec.id))
    fetched = result.scalar_one()
    assert fetched.is_time_dimension is True


@pytest.mark.asyncio
async def test_semantic_column_allowed_values(async_db_session: AsyncSession):
    """Test SemanticColumnModel.allowed_values JSON field."""
    db_rec = SemanticDatabaseModel(display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_db_session.add(db_rec)
    await async_db_session.flush()

    table_rec = SemanticTableModel(db_id=db_rec.id, table_name="orders", business_name="Đơn hàng")
    async_db_session.add(table_rec)
    await async_db_session.flush()

    allowed = ["pending", "paid", "cancelled"]
    col_rec = SemanticColumnModel(
        table_id=table_rec.id,
        column_name="status",
        data_type="VARCHAR",
        business_name="Trạng thái",
        allowed_values=allowed,
    )
    async_db_session.add(col_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticColumnModel).where(SemanticColumnModel.id == col_rec.id))
    fetched = result.scalar_one()
    assert fetched.allowed_values == allowed


# --- Tests for expanded SemanticMetricModel ---


@pytest.mark.asyncio
async def test_semantic_metric_new_fields(seed_user_and_db):
    """Test SemanticMetricModel new fields: base_entity_id, formula, aggregation_type, version, approved_by."""
    async_db_session, user, db_rec = seed_user_and_db

    table_rec = SemanticTableModel(
        db_id=db_rec.id,
        table_name="orders",
        business_name="Đơn hàng",
        created_by=user.id,
    )
    async_db_session.add(table_rec)
    await async_db_session.flush()

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Doanh thu trung bình",
        description="Giá trị đơn hàng trung bình",
        sql_template="SELECT AVG(total_amount) FROM orders",
        source="ai",
        base_entity_id=table_rec.id,
        formula="AVG(orders.total_amount)",
        aggregation_type="AVG",
        version=1,
        approved_by=user.id,
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched = result.scalar_one()
    assert fetched.base_entity_id == table_rec.id
    assert fetched.formula == "AVG(orders.total_amount)"
    assert fetched.aggregation_type == "AVG"
    assert fetched.version == 1
    assert fetched.approved_by == user.id


@pytest.mark.asyncio
async def test_semantic_metric_status_default_is_draft(async_db_session: AsyncSession):
    """Test SemanticMetricModel.status default is now 'draft'."""
    db_rec = SemanticDatabaseModel(display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_db_session.add(db_rec)
    await async_db_session.flush()

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Test Metric",
        description="Test",
        sql_template="SELECT 1",
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched = result.scalar_one()
    assert fetched.status == "draft"


@pytest.mark.asyncio
async def test_semantic_metric_formula_default_empty(async_db_session: AsyncSession):
    """Test SemanticMetricModel.formula defaults to empty string."""
    db_rec = SemanticDatabaseModel(display_name="DB", db_type="sqlite", conn_url_enc="enc")
    async_db_session.add(db_rec)
    await async_db_session.flush()

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Test",
        description="Test",
        sql_template="SELECT 1",
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched = result.scalar_one()
    assert fetched.formula == ""


@pytest.mark.asyncio
async def test_semantic_metric_base_entity_relationship(seed_user_and_db):
    """Test SemanticMetricModel.base_entity relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    table_rec = SemanticTableModel(db_id=db_rec.id, table_name="orders", business_name="Đơn hàng")
    async_db_session.add(table_rec)
    await async_db_session.flush()

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Revenue",
        description="Total revenue",
        sql_template="SELECT SUM(total) FROM orders",
        base_entity_id=table_rec.id,
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched = result.scalar_one()
    assert fetched.base_entity is not None
    assert fetched.base_entity.table_name == "orders"


@pytest.mark.asyncio
async def test_semantic_metric_approver_relationship(seed_user_and_db):
    """Test SemanticMetricModel.approver relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Revenue",
        description="Total revenue",
        sql_template="SELECT SUM(total) FROM orders",
        approved_by=user.id,
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(select(SemanticMetricModel).where(SemanticMetricModel.id == metric_rec.id))
    fetched = result.scalar_one()
    assert fetched.approver is not None
    assert fetched.approver.username == "creator"


@pytest.mark.asyncio
async def test_user_approved_metrics_relationship(seed_user_and_db):
    """Test UserModel.approved_metrics back_populates relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="AOV",
        description="Average order value",
        sql_template="SELECT AVG(total) FROM orders",
        approved_by=user.id,
    )
    async_db_session.add(metric_rec)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(UserModel).where(UserModel.id == user.id).options(selectinload(UserModel.approved_metrics))
    )
    fetched_user = result.scalar_one()
    assert len(fetched_user.approved_metrics) == 1
    assert fetched_user.approved_metrics[0].name == "AOV"


# --- Tests for new CanonicalRelationshipModel ---


@pytest.mark.asyncio
async def test_canonical_relationship_creation(seed_user_and_db):
    """Test creating a CanonicalRelationshipModel record."""
    async_db_session, _, db_rec = seed_user_and_db

    t1 = SemanticTableModel(db_id=db_rec.id, table_name="customers", business_name="Khách hàng")
    t2 = SemanticTableModel(db_id=db_rec.id, table_name="orders", business_name="Đơn hàng")
    async_db_session.add_all([t1, t2])
    await async_db_session.flush()

    rel = CanonicalRelationshipModel(
        connection_id=db_rec.id,
        from_entity_id=t1.id,
        to_entity_id=t2.id,
        relationship_type="one_to_many",
        join_condition="orders.customer_id = customers.id",
    )
    async_db_session.add(rel)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.id == rel.id)
    )
    fetched = result.scalar_one()
    assert fetched.relationship_type == "one_to_many"
    assert fetched.join_condition == "orders.customer_id = customers.id"


@pytest.mark.asyncio
async def test_canonical_relationship_entity_relationships(seed_user_and_db):
    """Test CanonicalRelationshipModel.from_entity and to_entity relationships."""
    async_db_session, _, db_rec = seed_user_and_db

    t1 = SemanticTableModel(db_id=db_rec.id, table_name="customers", business_name="Khách hàng")
    t2 = SemanticTableModel(db_id=db_rec.id, table_name="orders", business_name="Đơn hàng")
    async_db_session.add_all([t1, t2])
    await async_db_session.flush()

    rel = CanonicalRelationshipModel(
        connection_id=db_rec.id,
        from_entity_id=t1.id,
        to_entity_id=t2.id,
        relationship_type="one_to_many",
        join_condition="orders.customer_id = customers.id",
    )
    async_db_session.add(rel)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(CanonicalRelationshipModel)
        .where(CanonicalRelationshipModel.id == rel.id)
        .options(
            selectinload(CanonicalRelationshipModel.from_entity),
            selectinload(CanonicalRelationshipModel.to_entity),
        )
    )
    fetched = result.scalar_one()
    assert fetched.from_entity.table_name == "customers"
    assert fetched.to_entity.table_name == "orders"


@pytest.mark.asyncio
async def test_canonical_relationship_database_relationship(seed_user_and_db):
    """Test CanonicalRelationshipModel.database relationship via SemanticDatabaseModel."""
    async_db_session, _, db_rec = seed_user_and_db

    t1 = SemanticTableModel(db_id=db_rec.id, table_name="a", business_name="A")
    t2 = SemanticTableModel(db_id=db_rec.id, table_name="b", business_name="B")
    async_db_session.add_all([t1, t2])
    await async_db_session.flush()

    rel = CanonicalRelationshipModel(
        connection_id=db_rec.id,
        from_entity_id=t1.id,
        to_entity_id=t2.id,
        relationship_type="one_to_one",
        join_condition="b.a_id = a.id",
    )
    async_db_session.add(rel)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(SemanticDatabaseModel)
        .where(SemanticDatabaseModel.id == db_rec.id)
        .options(selectinload(SemanticDatabaseModel.relationships))
    )
    fetched_db = result.scalar_one()
    assert len(fetched_db.relationships) == 1
    assert fetched_db.relationships[0].relationship_type == "one_to_one"


# --- Tests for new MetricVersionModel ---


@pytest.mark.asyncio
async def test_metric_version_creation(seed_user_and_db):
    """Test creating a MetricVersionModel record."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Revenue",
        description="Total revenue",
        sql_template="SELECT SUM(total) FROM orders",
        formula="SUM(orders.total)",
        version=1,
    )
    async_db_session.add(metric_rec)
    await async_db_session.flush()

    mv = MetricVersionModel(
        metric_id=metric_rec.id,
        version=1,
        formula="SUM(orders.total)",
        changed_by=user.id,
        change_reason="Initial version",
    )
    async_db_session.add(mv)
    await async_db_session.commit()

    result = await async_db_session.execute(select(MetricVersionModel).where(MetricVersionModel.id == mv.id))
    fetched = result.scalar_one()
    assert fetched.version == 1
    assert fetched.formula == "SUM(orders.total)"
    assert fetched.change_reason == "Initial version"


@pytest.mark.asyncio
async def test_metric_version_metric_relationship(seed_user_and_db):
    """Test MetricVersionModel.metric relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="AOV",
        description="Average order value",
        sql_template="SELECT AVG(total) FROM orders",
        formula="AVG(orders.total)",
        version=2,
    )
    async_db_session.add(metric_rec)
    await async_db_session.flush()

    mv = MetricVersionModel(
        metric_id=metric_rec.id,
        version=2,
        formula="AVG(orders.total)",
        changed_by=user.id,
    )
    async_db_session.add(mv)
    await async_db_session.commit()

    result = await async_db_session.execute(select(MetricVersionModel).where(MetricVersionModel.id == mv.id))
    fetched = result.scalar_one()
    assert fetched.metric.name == "AOV"


@pytest.mark.asyncio
async def test_metric_version_changer_relationship(seed_user_and_db):
    """Test MetricVersionModel.changer relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="AOV",
        description="Average order value",
        sql_template="SELECT AVG(total) FROM orders",
    )
    async_db_session.add(metric_rec)
    await async_db_session.flush()

    mv = MetricVersionModel(
        metric_id=metric_rec.id,
        version=1,
        formula="AVG(orders.total)",
        changed_by=user.id,
    )
    async_db_session.add(mv)
    await async_db_session.commit()

    result = await async_db_session.execute(select(MetricVersionModel).where(MetricVersionModel.id == mv.id))
    fetched = result.scalar_one()
    assert fetched.changer.username == "creator"


@pytest.mark.asyncio
async def test_semantic_metric_versions_relationship(seed_user_and_db):
    """Test SemanticMetricModel.versions relationship."""
    async_db_session, user, db_rec = seed_user_and_db

    metric_rec = SemanticMetricModel(
        db_id=db_rec.id,
        name="Revenue",
        description="Total revenue",
        sql_template="SELECT SUM(total) FROM orders",
        version=2,
    )
    async_db_session.add(metric_rec)
    await async_db_session.flush()

    mv1 = MetricVersionModel(metric_id=metric_rec.id, version=1, formula="SUM(orders.total)", changed_by=user.id)
    mv2 = MetricVersionModel(metric_id=metric_rec.id, version=2, formula="SUM(o.total)", changed_by=user.id)
    async_db_session.add_all([mv1, mv2])
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(SemanticMetricModel)
        .where(SemanticMetricModel.id == metric_rec.id)
        .options(selectinload(SemanticMetricModel.versions))
    )
    fetched = result.scalar_one()
    assert len(fetched.versions) == 2
