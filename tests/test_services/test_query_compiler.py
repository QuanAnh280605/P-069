"""Tests for query_compiler — SemanticQueryCompiler and validate_read_only."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.services.query_compiler import CompiledQuery, SemanticQueryCompiler, validate_read_only

# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------


async def _seed_schema(db: AsyncSession) -> dict:
    """Seed a minimal semantic schema for query compiler tests.

    Schema:
        users(user_id PK, email, name)
        orders(order_id PK, user_id FK→users, total_amount, created_at)
        order_items(id PK, order_id FK→orders, product_id FK→products, quantity, price)
        products(product_id PK, name, category)

    Relationships (directed):
        orders → users       (orders.user_id = users.user_id)
        order_items → orders (order_items.order_id = orders.order_id)
        order_items → products (order_items.product_id = products.product_id)

    Metrics (approved except last):
        Total Revenue: SUM(orders.total_amount), base=orders
        Order Count:   COUNT(orders.order_id),   base=orders
        Avg Item Price: AVG(order_items.price),  base=order_items
        Draft Metric:  COUNT(*),                 base=orders, status=draft

    Returns dict of all IDs.
    """
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Test DB",
        db_type="postgresql",
        conn_url_enc="test-conn",
        status="approved",
    )
    db.add(sem_db)
    await db.flush()

    # --- Tables ---
    tbl_users = SemanticTableModel(
        db_id=sem_db.id,
        table_name="users",
        business_name="Nguoi dung",
        primary_key_column="user_id",
        created_by=1,
    )
    tbl_orders = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Don hang",
        primary_key_column="order_id",
        created_by=1,
    )
    tbl_oi = SemanticTableModel(
        db_id=sem_db.id,
        table_name="order_items",
        business_name="Chi tiet don",
        primary_key_column="id",
        created_by=1,
    )
    tbl_products = SemanticTableModel(
        db_id=sem_db.id,
        table_name="products",
        business_name="San pham",
        primary_key_column="product_id",
        created_by=1,
    )
    db.add_all([tbl_users, tbl_orders, tbl_oi, tbl_products])
    await db.flush()

    # --- Columns ---
    col_user_id = SemanticColumnModel(
        table_id=tbl_users.id,
        column_name="user_id",
        data_type="INTEGER",
        business_name="Ma nguoi dung",
        is_primary_key=True,
    )
    col_user_email = SemanticColumnModel(
        table_id=tbl_users.id,
        column_name="email",
        data_type="VARCHAR",
        business_name="Email",
    )
    col_user_name = SemanticColumnModel(
        table_id=tbl_users.id,
        column_name="name",
        data_type="VARCHAR",
        business_name="Ten",
    )

    col_order_id = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="order_id",
        data_type="INTEGER",
        business_name="Ma don",
        is_primary_key=True,
    )
    col_order_uid = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="user_id",
        data_type="INTEGER",
        business_name="Ma nguoi dat",
        is_foreign_key=True,
        fk_target_table="users",
        fk_target_column="user_id",
    )
    col_order_total = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="total_amount",
        data_type="DECIMAL",
        business_name="Tong tien",
    )
    col_order_created = SemanticColumnModel(
        table_id=tbl_orders.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Ngay tao",
        is_time_dimension=True,
    )

    col_oi_id = SemanticColumnModel(
        table_id=tbl_oi.id,
        column_name="id",
        data_type="INTEGER",
        business_name="ID",
        is_primary_key=True,
    )
    col_oi_oid = SemanticColumnModel(
        table_id=tbl_oi.id,
        column_name="order_id",
        data_type="INTEGER",
        business_name="Ma don",
        is_foreign_key=True,
        fk_target_table="orders",
        fk_target_column="order_id",
    )
    col_oi_pid = SemanticColumnModel(
        table_id=tbl_oi.id,
        column_name="product_id",
        data_type="INTEGER",
        business_name="Ma SP",
        is_foreign_key=True,
        fk_target_table="products",
        fk_target_column="product_id",
    )
    col_oi_qty = SemanticColumnModel(
        table_id=tbl_oi.id,
        column_name="quantity",
        data_type="INTEGER",
        business_name="So luong",
    )
    col_oi_price = SemanticColumnModel(
        table_id=tbl_oi.id,
        column_name="price",
        data_type="DECIMAL",
        business_name="Don gia",
    )

    col_prod_id = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="product_id",
        data_type="INTEGER",
        business_name="Ma SP",
        is_primary_key=True,
    )
    col_prod_name = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="name",
        data_type="VARCHAR",
        business_name="Ten SP",
    )
    col_prod_cat = SemanticColumnModel(
        table_id=tbl_products.id,
        column_name="category",
        data_type="VARCHAR",
        business_name="Danh muc",
    )

    db.add_all(
        [
            col_user_id,
            col_user_email,
            col_user_name,
            col_order_id,
            col_order_uid,
            col_order_total,
            col_order_created,
            col_oi_id,
            col_oi_oid,
            col_oi_pid,
            col_oi_qty,
            col_oi_price,
            col_prod_id,
            col_prod_name,
            col_prod_cat,
        ]
    )
    await db.flush()

    # --- Relationships ---
    rel_ou = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=tbl_orders.id,
        to_entity_id=tbl_users.id,
        relationship_type="many_to_one",
        join_condition="orders.user_id = users.user_id",
    )
    rel_io = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=tbl_oi.id,
        to_entity_id=tbl_orders.id,
        relationship_type="many_to_one",
        join_condition="order_items.order_id = orders.order_id",
    )
    rel_ip = CanonicalRelationshipModel(
        connection_id=sem_db.id,
        from_entity_id=tbl_oi.id,
        to_entity_id=tbl_products.id,
        relationship_type="many_to_one",
        join_condition="order_items.product_id = products.product_id",
    )
    db.add_all([rel_ou, rel_io, rel_ip])
    await db.flush()

    # --- Metrics ---
    m_rev = SemanticMetricModel(
        db_id=sem_db.id,
        name="Total Revenue",
        description="Revenue",
        sql_template="SELECT SUM(total_amount) FROM orders",
        formula="SUM(orders.total_amount)",
        aggregation_type="SUM",
        status="approved",
        base_entity_id=tbl_orders.id,
        created_by=1,
    )
    m_cnt = SemanticMetricModel(
        db_id=sem_db.id,
        name="Order Count",
        description="Count",
        sql_template="SELECT COUNT(order_id) FROM orders",
        formula="COUNT(orders.order_id)",
        aggregation_type="COUNT",
        status="approved",
        base_entity_id=tbl_orders.id,
        created_by=1,
    )
    m_avg = SemanticMetricModel(
        db_id=sem_db.id,
        name="Avg Item Price",
        description="Avg",
        sql_template="SELECT AVG(price) FROM order_items",
        formula="AVG(order_items.price)",
        aggregation_type="AVG",
        status="approved",
        base_entity_id=tbl_oi.id,
        created_by=1,
    )
    m_draft = SemanticMetricModel(
        db_id=sem_db.id,
        name="Draft Metric",
        description="Draft",
        sql_template="SELECT COUNT(*) FROM orders",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="draft",
        base_entity_id=tbl_orders.id,
        created_by=1,
    )
    db.add_all([m_rev, m_cnt, m_avg, m_draft])
    await db.flush()
    await db.commit()

    return {
        "sem_db_id": sem_db.id,
        "orders_id": tbl_orders.id,
        "users_id": tbl_users.id,
        "oi_id": tbl_oi.id,
        "products_id": tbl_products.id,
        # Dimension column IDs
        "col_user_name_id": col_user_name.id,
        "col_user_email_id": col_user_email.id,
        "col_order_created_id": col_order_created.id,
        "col_order_uid_id": col_order_uid.id,
        "col_order_total_id": col_order_total.id,
        "col_prod_cat_id": col_prod_cat.id,
        "col_prod_name_id": col_prod_name.id,
        "col_oi_price_id": col_oi_price.id,
        # Metric IDs
        "m_rev_id": m_rev.id,
        "m_cnt_id": m_cnt.id,
        "m_avg_id": m_avg.id,
        "m_draft_id": m_draft.id,
    }


# ===================================================================
# validate_read_only — standalone tests (no DB)
# ===================================================================


def test_validate_read_only_accepts_select():
    """Simple SELECT is accepted."""
    assert validate_read_only("SELECT id, name FROM users") is True


def test_validate_read_only_accepts_select_with_join():
    """SELECT with JOIN is accepted."""
    sql = "SELECT u.name FROM orders o JOIN users u ON o.user_id = u.user_id"
    assert validate_read_only(sql) is True


def test_validate_read_only_rejects_insert():
    """INSERT is rejected."""
    with pytest.raises(ValueError, match="(?i)insert"):
        validate_read_only("INSERT INTO users (name) VALUES ('test')")


def test_validate_read_only_rejects_update():
    """UPDATE is rejected."""
    with pytest.raises(ValueError, match="(?i)update"):
        validate_read_only("UPDATE users SET name = 'test'")


def test_validate_read_only_rejects_delete():
    """DELETE is rejected."""
    with pytest.raises(ValueError, match="(?i)delete"):
        validate_read_only("DELETE FROM users WHERE id = 1")


def test_validate_read_only_rejects_drop():
    """DROP TABLE is rejected."""
    with pytest.raises(ValueError, match="(?i)drop"):
        validate_read_only("DROP TABLE users")


def test_validate_read_only_rejects_alter():
    """ALTER TABLE is rejected."""
    with pytest.raises(ValueError, match="(?i)alter"):
        validate_read_only("ALTER TABLE users ADD COLUMN age INT")


def test_validate_read_only_rejects_truncate():
    """TRUNCATE TABLE is rejected."""
    with pytest.raises(ValueError, match="(?i)truncate"):
        validate_read_only("TRUNCATE TABLE users")


def test_validate_read_only_rejects_select_into():
    """SELECT ... INTO is rejected."""
    with pytest.raises(ValueError, match="INTO"):
        validate_read_only("SELECT * INTO backup FROM users")


def test_validate_read_only_rejects_multi_statement():
    """Semicolon-separated queries are rejected."""
    with pytest.raises(ValueError, match="[Mm]ulti"):
        validate_read_only("SELECT 1; DROP TABLE users")


def test_validate_read_only_rejects_cte_with_dml():
    """CTE containing DELETE is rejected."""
    sql = "WITH deleted AS (DELETE FROM users RETURNING *) SELECT * FROM deleted"
    with pytest.raises(ValueError, match="DML"):
        validate_read_only(sql)


# ===================================================================
# SemanticQueryCompiler.compile — DB-backed tests
# ===================================================================


@pytest.mark.asyncio
async def test_compile_single_metric_same_table_dimension(async_session: AsyncSession):
    """1 metric + 1 dimension from the same table → simple SELECT, no JOIN."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_order_created_id"]],
    )

    assert isinstance(result, CompiledQuery)
    sql_upper = result.sql.upper()
    assert "SUM" in sql_upper
    assert "orders" in result.sql
    assert "created_at" in result.sql
    assert "GROUP BY" in sql_upper
    assert "LIMIT 100" in sql_upper
    assert "JOIN" not in sql_upper


@pytest.mark.asyncio
async def test_compile_with_two_table_join(async_session: AsyncSession):
    """Metric on orders + dimension from users → triggers JOIN."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_user_name_id"]],
    )

    sql_upper = result.sql.upper()
    assert "JOIN" in sql_upper
    assert "users" in result.sql
    assert "orders" in result.sql
    assert "user_id" in result.sql


@pytest.mark.asyncio
async def test_compile_multi_hop_join(async_session: AsyncSession):
    """Metric on orders + dimension from products (path: orders → order_items → products)."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_prod_cat_id"]],
    )

    sql = result.sql
    assert "order_items" in sql
    assert "products" in sql
    assert "orders" in sql
    assert "JOIN" in sql.upper()


@pytest.mark.asyncio
async def test_compile_join_path_resolution_bfs(async_session: AsyncSession):
    """BFS resolves shortest path: orders → order_items → products."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_prod_cat_id"]],
    )

    # Should have exactly2 joins (order_items + products)
    join_count = result.sql.upper().count("JOIN")
    assert join_count == 2

    # Metadata should track the joins
    assert len(result.metadata["joins"]) == 2


@pytest.mark.asyncio
async def test_compile_rejects_draft_metric(async_session: AsyncSession):
    """Draft (non-approved) metrics are rejected."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    with pytest.raises(ValueError, match="approved"):
        await compiler.compile(
            connection_id=data["sem_db_id"],
            metric_ids=[data["m_draft_id"]],
            dimension_ids=[data["col_order_created_id"]],
        )


@pytest.mark.asyncio
async def test_compile_formula_with_table_prefix(async_session: AsyncSession):
    """Formula SUM(orders.total_amount) extracts aggregation and column correctly."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_order_created_id"]],
    )

    assert "SUM" in result.sql
    assert "total_amount" in result.sql


@pytest.mark.asyncio
async def test_compile_formula_without_table_prefix(async_session: AsyncSession):
    """Formula COUNT(*) (no table prefix) resolves using base_entity_id."""
    # Create a metric with COUNT(*) that is approved
    data = await _seed_schema(async_session)
    m_star = SemanticMetricModel(
        db_id=data["sem_db_id"],
        name="All Orders",
        description="All orders",
        sql_template="SELECT COUNT(*) FROM orders",
        formula="COUNT(*)",
        aggregation_type="COUNT",
        status="approved",
        base_entity_id=data["orders_id"],
        created_by=1,
    )
    async_session.add(m_star)
    await async_session.flush()
    await async_session.commit()

    compiler = SemanticQueryCompiler(async_session)
    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[m_star.id],
        dimension_ids=[data["col_order_created_id"]],
    )

    assert "COUNT" in result.sql.upper()
    assert "orders" in result.sql


@pytest.mark.asyncio
async def test_compile_formula_with_distinct(async_session: AsyncSession):
    """Formula COUNT(DISTINCT orders.user_id) produces DISTINCT in SQL."""
    data = await _seed_schema(async_session)
    m_distinct = SemanticMetricModel(
        db_id=data["sem_db_id"],
        name="Unique Users",
        description="Distinct users",
        sql_template="SELECT COUNT(DISTINCT user_id) FROM orders",
        formula="COUNT(DISTINCT orders.user_id)",
        aggregation_type="COUNT",
        status="approved",
        base_entity_id=data["orders_id"],
        created_by=1,
    )
    async_session.add(m_distinct)
    await async_session.flush()
    await async_session.commit()

    compiler = SemanticQueryCompiler(async_session)
    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[m_distinct.id],
        dimension_ids=[data["col_order_created_id"]],
    )

    assert "DISTINCT" in result.sql.upper()
    assert "COUNT" in result.sql.upper()


@pytest.mark.asyncio
async def test_compile_limit_default_100(async_session: AsyncSession):
    """Default limit is 100."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_cnt_id"]],
        dimension_ids=[data["col_order_created_id"]],
    )

    assert "LIMIT 100" in result.sql


@pytest.mark.asyncio
async def test_compile_limit_custom(async_session: AsyncSession):
    """Custom limit is applied."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_cnt_id"]],
        dimension_ids=[data["col_order_created_id"]],
        limit=50,
    )

    assert "LIMIT 50" in result.sql


@pytest.mark.asyncio
async def test_compile_limit_capped_at_1000(async_session: AsyncSession):
    """Limit is capped at 1000."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_cnt_id"]],
        dimension_ids=[data["col_order_created_id"]],
        limit=5000,
    )

    assert "LIMIT 1000" in result.sql


@pytest.mark.asyncio
async def test_compile_raises_on_missing_join_path(async_session: AsyncSession):
    """Raises ValueError when no join path exists."""
    data = await _seed_schema(async_session)

    # Create an isolated table with no relationships
    isolated = SemanticTableModel(
        db_id=data["sem_db_id"],
        table_name="isolated",
        business_name="Isolated",
        primary_key_column="id",
        created_by=1,
    )
    async_session.add(isolated)
    await async_session.flush()
    col_iso = SemanticColumnModel(
        table_id=isolated.id,
        column_name="label",
        data_type="VARCHAR",
        business_name="Label",
    )
    async_session.add(col_iso)
    await async_session.flush()
    await async_session.commit()

    compiler = SemanticQueryCompiler(async_session)
    with pytest.raises(ValueError, match="[Cc]annot join"):
        await compiler.compile(
            connection_id=data["sem_db_id"],
            metric_ids=[data["m_rev_id"]],
            dimension_ids=[col_iso.id],
        )


@pytest.mark.asyncio
async def test_compile_multiple_metrics(async_session: AsyncSession):
    """Multiple metrics in a single query."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"], data["m_cnt_id"]],
        dimension_ids=[data["col_order_created_id"]],
    )

    sql_upper = result.sql.upper()
    assert "SUM" in sql_upper
    assert "COUNT" in sql_upper


@pytest.mark.asyncio
async def test_compile_multiple_dimensions(async_session: AsyncSession):
    """Multiple dimensions appear in SELECT and GROUP BY."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_order_created_id"], data["col_order_uid_id"]],
    )

    sql = result.sql
    assert "created_at" in sql
    assert "user_id" in sql
    # GROUP BY should contain both
    group_by_section = sql.upper().split("GROUP BY")[1]
    assert "CREATED_AT" in group_by_section
    assert "USER_ID" in group_by_section


@pytest.mark.asyncio
async def test_compile_returns_compiled_query_metadata(async_session: AsyncSession):
    """CompiledQuery metadata contains tables, joins, metrics, dimensions."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    result = await compiler.compile(
        connection_id=data["sem_db_id"],
        metric_ids=[data["m_rev_id"]],
        dimension_ids=[data["col_user_name_id"]],
    )

    assert "tables" in result.metadata
    assert "joins" in result.metadata
    assert "metrics" in result.metadata
    assert "dimensions" in result.metadata
    assert "Total Revenue" in result.metadata["metrics"]
    assert "users.name" in result.metadata["dimensions"]


@pytest.mark.asyncio
async def test_compile_rejects_nonexistent_metric(async_session: AsyncSession):
    """Raises ValueError for non-existent metric ID."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    with pytest.raises(ValueError, match="[Nn]ot found"):
        await compiler.compile(
            connection_id=data["sem_db_id"],
            metric_ids=[99999],
            dimension_ids=[data["col_order_created_id"]],
        )


@pytest.mark.asyncio
async def test_compile_rejects_nonexistent_dimension(async_session: AsyncSession):
    """Raises ValueError for non-existent dimension column ID."""
    data = await _seed_schema(async_session)
    compiler = SemanticQueryCompiler(async_session)

    with pytest.raises(ValueError, match="[Nn]ot found"):
        await compiler.compile(
            connection_id=data["sem_db_id"],
            metric_ids=[data["m_rev_id"]],
            dimension_ids=[99999],
        )
