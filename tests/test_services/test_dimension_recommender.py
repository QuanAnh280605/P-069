import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.review_mixin import REVIEW_STATUS_APPROVED
from src.models.schemas import RecommendedDimensionItem
from src.services.dimension_recommender import (
    _dimension_priority,
    _rank_and_truncate_candidates,
    get_dimensions_for_metric,
    get_filter_columns_for_metric,
    is_valid_dimension_column,
    is_valid_filter_column,
)


@pytest.mark.asyncio
async def test_is_valid_dimension_column():
    # Valid categorical
    col_status = SemanticColumnModel(
        table_id=1,
        column_name="status",
        data_type="VARCHAR",
        business_name="Trạng thái",
        is_primary_key=False,
        is_foreign_key=False,
        is_time_dimension=False,
    )
    assert is_valid_dimension_column(col_status) is True

    # Primary key -> invalid
    col_pk = SemanticColumnModel(
        table_id=1,
        column_name="id",
        data_type="INTEGER",
        business_name="ID",
        is_primary_key=True,
        is_foreign_key=False,
    )
    assert is_valid_dimension_column(col_pk) is False

    # Foreign key -> invalid
    col_fk = SemanticColumnModel(
        table_id=1,
        column_name="customer_id",
        data_type="INTEGER",
        business_name="Mã khách hàng",
        is_primary_key=False,
        is_foreign_key=True,
    )
    assert is_valid_dimension_column(col_fk) is False

    # Numeric measure -> invalid
    col_price = SemanticColumnModel(
        table_id=1,
        column_name="total_price",
        data_type="DECIMAL(10,2)",
        business_name="Tổng tiền",
        is_primary_key=False,
        is_foreign_key=False,
    )
    assert is_valid_dimension_column(col_price) is False

    # Time dimension -> invalid
    col_time = SemanticColumnModel(
        table_id=1,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Ngày tạo",
        is_time_dimension=True,
    )
    assert is_valid_dimension_column(col_time) is False

    # Junk keyword -> invalid
    col_note = SemanticColumnModel(
        table_id=1,
        column_name="delivery_note",
        data_type="VARCHAR",
        business_name="Ghi chú",
        is_primary_key=False,
        is_foreign_key=False,
    )
    assert is_valid_dimension_column(col_note) is False


@pytest.mark.asyncio
async def test_get_dimensions_for_metric_tiers(async_session: AsyncSession):
    # Setup user and db
    user = UserModel(
        email="rec@example.com", hashed_password="pw", full_name="Recommender Tester", username="recommender"
    )
    async_session.add(user)
    await async_session.flush()

    s_db = SemanticDatabaseModel(
        display_name="test_ecommerce", db_type="sqlite", conn_url_enc="enc", created_by=user.id
    )
    async_session.add(s_db)
    await async_session.flush()

    # Tables: orders (base), customers (N:1), regions (N:1 from customers), order_items (1:N), products (N:1 from items)
    t_orders = SemanticTableModel(db_id=s_db.id, table_name="orders", business_name="Đơn hàng", created_by=user.id)
    t_customers = SemanticTableModel(
        db_id=s_db.id, table_name="customers", business_name="Khách hàng", created_by=user.id
    )
    t_regions = SemanticTableModel(db_id=s_db.id, table_name="regions", business_name="Vùng miền", created_by=user.id)
    t_items = SemanticTableModel(
        db_id=s_db.id, table_name="order_items", business_name="Dòng đơn hàng", created_by=user.id
    )
    t_products = SemanticTableModel(db_id=s_db.id, table_name="products", business_name="Sản phẩm", created_by=user.id)
    async_session.add_all([t_orders, t_customers, t_regions, t_items, t_products])
    await async_session.flush()

    # Columns
    c1 = SemanticColumnModel(
        table_id=t_orders.id,
        column_name="status",
        data_type="VARCHAR",
        business_name="Trạng thái đơn",
        is_primary_key=False,
        is_foreign_key=False,
    )
    c2 = SemanticColumnModel(
        table_id=t_orders.id,
        column_name="channel",
        data_type="VARCHAR",
        business_name="Kênh bán",
        is_primary_key=False,
        is_foreign_key=False,
    )
    c_note = SemanticColumnModel(
        table_id=t_orders.id,
        column_name="note",
        data_type="VARCHAR",
        business_name="Ghi chú",
        is_primary_key=False,
        is_foreign_key=False,
    )

    c3 = SemanticColumnModel(
        table_id=t_customers.id,
        column_name="city",
        data_type="VARCHAR",
        business_name="Tỉnh / Thành phố",
        is_primary_key=False,
        is_foreign_key=False,
    )
    c4 = SemanticColumnModel(
        table_id=t_regions.id,
        column_name="region_name",
        data_type="VARCHAR",
        business_name="Tên vùng miền",
        is_primary_key=False,
        is_foreign_key=False,
    )
    c5 = SemanticColumnModel(
        table_id=t_products.id,
        column_name="category",
        data_type="VARCHAR",
        business_name="Danh mục",
        is_primary_key=False,
        is_foreign_key=False,
    )
    async_session.add_all([c1, c2, c_note, c3, c4, c5])
    await async_session.flush()

    # Relationships:
    # orders -> customers (many_to_one)
    r1 = CanonicalRelationshipModel(
        connection_id=s_db.id,
        from_entity_id=t_orders.id,
        to_entity_id=t_customers.id,
        relationship_type="many_to_one",
        join_condition="orders.customer_id = customers.id",
        relationship_key="orders:customers",
        validation_status="valid",
        review_status=REVIEW_STATUS_APPROVED,
    )
    # customers -> regions (many_to_one)
    r2 = CanonicalRelationshipModel(
        connection_id=s_db.id,
        from_entity_id=t_customers.id,
        to_entity_id=t_regions.id,
        relationship_type="many_to_one",
        join_condition="customers.region_id = regions.id",
        relationship_key="customers:regions",
        validation_status="valid",
        review_status=REVIEW_STATUS_APPROVED,
    )
    # orders -> order_items (one_to_many)
    r3 = CanonicalRelationshipModel(
        connection_id=s_db.id,
        from_entity_id=t_orders.id,
        to_entity_id=t_items.id,
        relationship_type="one_to_many",
        join_condition="orders.id = order_items.order_id",
        relationship_key="orders:items",
        validation_status="valid",
        review_status=REVIEW_STATUS_APPROVED,
    )
    # order_items -> products (many_to_one)
    r4 = CanonicalRelationshipModel(
        connection_id=s_db.id,
        from_entity_id=t_items.id,
        to_entity_id=t_products.id,
        relationship_type="many_to_one",
        join_condition="order_items.product_id = products.id",
        relationship_key="items:products",
        validation_status="valid",
        review_status=REVIEW_STATUS_APPROVED,
    )
    async_session.add_all([r1, r2, r3, r4])
    await async_session.flush()

    # Metric: Doanh thu thuần on orders
    metric = SemanticMetricModel(
        db_id=s_db.id,
        created_by=user.id,
        name="Doanh thu thuần",
        description="Tổng doanh thu",
        sql_template="SELECT SUM(price) FROM orders",
        base_entity_id=t_orders.id,
    )
    async_session.add(metric)
    await async_session.flush()

    # Call get_dimensions_for_metric
    dims = await get_dimensions_for_metric(async_session, s_db.id, metric.id)

    # Assertions
    tier_map = {d.column_name: d.tier for d in dims}
    assert "status" in tier_map
    assert tier_map["status"] == "A"
    assert "channel" in tier_map
    assert tier_map["channel"] == "A"
    assert "note" not in tier_map  # Junk filtered out
    assert "city" in tier_map
    assert tier_map["city"] == "B"  # 1-hop N:1
    assert "region_name" in tier_map
    assert tier_map["region_name"] == "C"  # 2-hop N:1
    assert "category" not in tier_map  # 1:N downstream safely excluded to prevent UNSAFE_FANOUT

    # Call get_filter_columns_for_metric
    filter_cols = await get_filter_columns_for_metric(async_session, s_db.id, metric.id)
    group_map = {c.column_name: c.group_type for c in filter_cols}
    assert "status" in group_map
    assert group_map["status"] == "base"
    assert "channel" in group_map
    assert group_map["channel"] == "base"
    assert "note" not in group_map
    assert "city" in group_map
    assert group_map["city"] == "related"
    assert "region_name" in group_map
    assert group_map["region_name"] == "related"
    assert "category" not in group_map


@pytest.mark.parametrize(
    "validation_status,review_status",
    [
        ("valid", "pending_review"),
        ("invalid", "approved"),
    ],
)
@pytest.mark.asyncio
async def test_relationship_governance_gate_excludes_unapproved(
    async_session: AsyncSession, validation_status: str, review_status: str
):
    """A relationship that is not both valid AND approved must never leak into
    recommended dimensions or filter columns (the compiler would fail-closed)."""
    user = UserModel(email="gate@example.com", hashed_password="pw", full_name="Gate Tester", username="gate")
    async_session.add(user)
    await async_session.flush()

    s_db = SemanticDatabaseModel(display_name="test_gate", db_type="sqlite", conn_url_enc="enc", created_by=user.id)
    async_session.add(s_db)
    await async_session.flush()

    t_orders = SemanticTableModel(db_id=s_db.id, table_name="orders", business_name="Đơn hàng", created_by=user.id)
    t_customers = SemanticTableModel(
        db_id=s_db.id, table_name="customers", business_name="Khách hàng", created_by=user.id
    )
    async_session.add_all([t_orders, t_customers])
    await async_session.flush()

    c_status = SemanticColumnModel(
        table_id=t_orders.id,
        column_name="status",
        data_type="VARCHAR",
        business_name="Trạng thái",
        is_primary_key=False,
        is_foreign_key=False,
    )
    c_city = SemanticColumnModel(
        table_id=t_customers.id,
        column_name="city",
        data_type="VARCHAR",
        business_name="Tỉnh / Thành phố",
        is_primary_key=False,
        is_foreign_key=False,
    )
    async_session.add_all([c_status, c_city])
    await async_session.flush()

    rel = CanonicalRelationshipModel(
        connection_id=s_db.id,
        from_entity_id=t_orders.id,
        to_entity_id=t_customers.id,
        relationship_type="many_to_one",
        join_condition="orders.customer_id = customers.id",
        relationship_key="orders:customers",
        validation_status=validation_status,
        review_status=review_status,
    )
    async_session.add(rel)
    await async_session.flush()

    metric = SemanticMetricModel(
        db_id=s_db.id,
        created_by=user.id,
        name="Doanh thu",
        description="Tổng doanh thu",
        sql_template="SELECT SUM(price) FROM orders",
        base_entity_id=t_orders.id,
    )
    async_session.add(metric)
    await async_session.flush()

    dims = await get_dimensions_for_metric(async_session, s_db.id, metric.id)
    assert all(d.column_name != "city" for d in dims)

    filters = await get_filter_columns_for_metric(async_session, s_db.id, metric.id)
    assert all(c.column_name != "city" for c in filters)


@pytest.mark.asyncio
async def test_is_valid_filter_column():
    col_status = SemanticColumnModel(
        table_id=1,
        column_name="status",
        data_type="VARCHAR",
        business_name="Trạng thái",
        is_primary_key=False,
        is_foreign_key=False,
    )
    assert is_valid_filter_column(col_status) is True

    col_fk = SemanticColumnModel(
        table_id=1,
        column_name="customer_id",
        data_type="INTEGER",
        business_name="Mã khách hàng",
        is_primary_key=False,
        is_foreign_key=True,
    )
    assert is_valid_filter_column(col_fk) is False

    col_pass = SemanticColumnModel(
        table_id=1,
        column_name="password_hash",
        data_type="VARCHAR",
        business_name="Mật khẩu mã hóa",
        is_primary_key=False,
        is_foreign_key=False,
    )
    assert is_valid_filter_column(col_pass) is False


def test_dimension_priority_ranking():
    """Verify descriptive names are ranked ahead of boolean flags."""
    item_bool = RecommendedDimensionItem(
        column_id=1,
        column_name="is_delivered",
        business_name="Đã giao",
        table_id=10,
        table_name="order_header",
        table_business_name="Đơn hàng",
        tier="A",
        tier_label="Trực tiếp",
        is_safe_join=True,
        requires_reaggregation=False,
        data_type="BOOLEAN",
        cardinality_hint=2,
    )
    item_name = RecommendedDimensionItem(
        column_id=2,
        column_name="name",
        business_name="Tên cửa hàng",
        table_id=20,
        table_name="store",
        table_business_name="Cửa hàng",
        tier="B",
        tier_label="Liên kết trực tiếp (N:1)",
        is_safe_join=True,
        requires_reaggregation=False,
        data_type="VARCHAR",
        cardinality_hint=10,
    )
    item_status = RecommendedDimensionItem(
        column_id=3,
        column_name="status",
        business_name="Trạng thái",
        table_id=10,
        table_name="order_header",
        table_business_name="Đơn hàng",
        tier="A",
        tier_label="Trực tiếp",
        is_safe_join=True,
        requires_reaggregation=False,
        data_type="VARCHAR",
        cardinality_hint=5,
    )
    assert _dimension_priority(item_name) == 0
    assert _dimension_priority(item_status) == 1
    assert _dimension_priority(item_bool) == 4

    ranked = _rank_and_truncate_candidates([item_bool, item_name, item_status], limit=2)
    assert len(ranked) == 2
    assert ranked[0].column_name == "name"
    assert ranked[1].column_name == "status"
