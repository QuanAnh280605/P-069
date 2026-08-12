"""Tests for export_service — canonical schema export with relationships, metric versions."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    MetricVersionModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.services.export_service import build_semantic_layer_dict, serialize_to_json, serialize_to_yaml

# ---------------------------------------------------------------------------
# Fixtures — seed a full canonical schema
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_db(async_session: AsyncSession) -> int:
    """Seed a semantic database with tables, columns, relationships, metrics, and metric versions.

    Returns the semantic_database.id.
    """
    db_model = SemanticDatabaseModel(
        id=10,
        created_by=1,
        display_name="E-Commerce DB",
        db_type="postgresql",
        conn_url_enc="encrypted:xxx",
        status="approved",
    )
    async_session.add(db_model)
    await async_session.flush()

    # --- Tables ---
    users_table = SemanticTableModel(
        db_id=db_model.id,
        table_name="users",
        business_name="Users",
        description="User accounts",
        physical_schema="public",
        primary_key_column="user_id",
        created_by=1,
    )
    orders_table = SemanticTableModel(
        db_id=db_model.id,
        table_name="orders",
        business_name="Orders",
        description="Customer orders",
        physical_schema="public",
        primary_key_column="order_id",
        created_by=1,
    )
    async_session.add_all([users_table, orders_table])
    await async_session.flush()

    # --- Columns (Dimensions) ---
    user_id_col = SemanticColumnModel(
        table_id=users_table.id,
        column_name="user_id",
        data_type="INTEGER",
        business_name="User ID",
        description="Primary key",
        is_primary_key=True,
        is_foreign_key=False,
        is_nullable=False,
        is_time_dimension=False,
        allowed_values=None,
    )
    email_col = SemanticColumnModel(
        table_id=users_table.id,
        column_name="email",
        data_type="VARCHAR",
        business_name="Email",
        description="User email",
        is_primary_key=False,
        is_foreign_key=False,
        is_nullable=True,
        is_time_dimension=False,
        allowed_values=None,
    )
    order_id_col = SemanticColumnModel(
        table_id=orders_table.id,
        column_name="order_id",
        data_type="INTEGER",
        business_name="Order ID",
        description="Primary key",
        is_primary_key=True,
        is_foreign_key=False,
        is_nullable=False,
        is_time_dimension=False,
        allowed_values=None,
    )
    created_at_col = SemanticColumnModel(
        table_id=orders_table.id,
        column_name="created_at",
        data_type="TIMESTAMP",
        business_name="Created At",
        description="Order creation timestamp",
        is_primary_key=False,
        is_foreign_key=False,
        is_nullable=True,
        is_time_dimension=True,
        allowed_values=None,
    )
    status_col = SemanticColumnModel(
        table_id=orders_table.id,
        column_name="status",
        data_type="VARCHAR",
        business_name="Order Status",
        description="Current order status",
        is_primary_key=False,
        is_foreign_key=False,
        is_nullable=True,
        is_time_dimension=False,
        allowed_values=["pending", "shipped", "delivered", "cancelled"],
    )
    async_session.add_all([user_id_col, email_col, order_id_col, created_at_col, status_col])
    await async_session.flush()

    # --- Relationships ---
    rel = CanonicalRelationshipModel(
        connection_id=db_model.id,
        from_entity_id=orders_table.id,
        to_entity_id=users_table.id,
        relationship_type="many_to_one",
        join_condition="orders.user_id = users.user_id",
    )
    async_session.add(rel)
    await async_session.flush()

    # --- Metrics ---
    metric1 = SemanticMetricModel(
        db_id=db_model.id,
        created_by=1,
        name="Total Orders",
        description="Count of all orders",
        sql_template="SELECT COUNT(order_id) FROM orders",
        source="manual",
        status="approved",
        formula="COUNT(orders.order_id)",
        aggregation_type="COUNT",
        version=2,
        approved_by=1,
        base_entity_id=orders_table.id,
    )
    metric2 = SemanticMetricModel(
        db_id=db_model.id,
        created_by=1,
        name="Avg Order Value",
        description="Average order total",
        sql_template="SELECT AVG(total) FROM orders",
        source="manual",
        status="draft",
        formula="AVG(orders.total)",
        aggregation_type="AVG",
        version=1,
    )
    async_session.add_all([metric1, metric2])
    await async_session.flush()

    # --- Metric Versions ---
    v1 = MetricVersionModel(
        metric_id=metric1.id,
        version=1,
        formula="COUNT(orders.order_id)",
        changed_by=1,
        change_reason="Initial",
    )
    v2 = MetricVersionModel(
        metric_id=metric1.id,
        version=2,
        formula="COUNT(orders.order_id)",
        changed_by=1,
        change_reason="No change to formula",
    )
    async_session.add_all([v1, v2])
    await async_session.flush()

    return db_model.id


# ---------------------------------------------------------------------------
# Tests — Canonical Entities (tables with physical_schema, primary_key_column)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_canonical_entities_has_physical_schema(async_session: AsyncSession, seeded_db: int):
    """canonical_entities includes physical_schema and primary_key_column."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    assert "canonical_entities" in result
    entities = result["canonical_entities"]
    assert len(entities) == 2

    users_entity = next(e for e in entities if e["table_name"] == "users")
    assert users_entity["physical_schema"] == "public"
    assert users_entity["primary_key_column"] == "user_id"


@pytest.mark.asyncio
async def test_export_tables_include_business_fields(async_session: AsyncSession, seeded_db: int):
    """canonical_entities retains table_name, business_name, description, columns."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    entity = result["canonical_entities"][0]
    assert "table_name" in entity
    assert "business_name" in entity
    assert "description" in entity
    assert "columns" in entity
    assert isinstance(entity["columns"], list)


# ---------------------------------------------------------------------------
# Tests — Canonical Relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_canonical_relationships(async_session: AsyncSession, seeded_db: int):
    """Export includes canonical_relationships with correct fields."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    assert "canonical_relationships" in result
    rels = result["canonical_relationships"]
    assert len(rels) == 1

    rel = rels[0]
    assert rel["relationship_type"] == "many_to_one"
    assert rel["join_condition"] == "orders.user_id = users.user_id"
    assert "from_entity_id" in rel
    assert "to_entity_id" in rel


# ---------------------------------------------------------------------------
# Tests — Canonical Dimensions (columns with is_time_dimension, allowed_values)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_canonical_dimensions_has_time_dimension(async_session: AsyncSession, seeded_db: int):
    """canonical_dimensions includes is_time_dimension flag."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    assert "canonical_dimensions" in result
    dims = result["canonical_dimensions"]

    created_at = next(d for d in dims if d["column_name"] == "created_at")
    assert created_at["is_time_dimension"] is True
    assert created_at["data_type"] == "TIMESTAMP"


@pytest.mark.asyncio
async def test_export_canonical_dimensions_has_allowed_values(async_session: AsyncSession, seeded_db: int):
    """canonical_dimensions includes allowed_values for enum columns."""
    result = await build_semantic_layer_dict(async_session, seeded_db)
    dims = result["canonical_dimensions"]

    status_dim = next(d for d in dims if d["column_name"] == "status")
    assert status_dim["allowed_values"] == ["pending", "shipped", "delivered", "cancelled"]


@pytest.mark.asyncio
async def test_export_canonical_dimensions_count(async_session: AsyncSession, seeded_db: int):
    """All columns across all tables are flattened into canonical_dimensions."""
    result = await build_semantic_layer_dict(async_session, seeded_db)
    dims = result["canonical_dimensions"]
    assert len(dims) == 5  # 2 users + 3 orders


# ---------------------------------------------------------------------------
# Tests — Canonical Metrics (with formula, aggregation_type, version, status)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_canonical_metrics_has_formula_and_version(async_session: AsyncSession, seeded_db: int):
    """canonical_metrics includes formula, aggregation_type, version, status."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    assert "canonical_metrics" in result
    metrics = result["canonical_metrics"]
    assert len(metrics) == 2

    total_orders = next(m for m in metrics if m["name"] == "Total Orders")
    assert total_orders["formula"] == "COUNT(orders.order_id)"
    assert total_orders["aggregation_type"] == "COUNT"
    assert total_orders["version"] == 2
    assert total_orders["status"] == "approved"


@pytest.mark.asyncio
async def test_export_canonical_metrics_includes_versions(async_session: AsyncSession, seeded_db: int):
    """canonical_metrics includes version history list."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    total_orders = next(m for m in result["canonical_metrics"] if m["name"] == "Total Orders")
    assert "versions" in total_orders
    assert len(total_orders["versions"]) == 2
    assert total_orders["versions"][0]["version"] == 1
    assert total_orders["versions"][1]["version"] == 2


# ---------------------------------------------------------------------------
# Tests — Security: conn_url_enc MUST NOT appear in export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_does_not_contain_conn_url_enc(async_session: AsyncSession, seeded_db: int):
    """conn_url_enc must never appear in the exported dict."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    import json

    serialized = json.dumps(result)
    assert "conn_url_enc" not in serialized
    assert "encrypted:xxx" not in serialized


# ---------------------------------------------------------------------------
# Tests — Database metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_database_metadata(async_session: AsyncSession, seeded_db: int):
    """Export includes database metadata without sensitive fields."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    db_meta = result["database"]
    assert db_meta["id"] == seeded_db
    assert db_meta["display_name"] == "E-Commerce DB"
    assert db_meta["db_type"] == "postgresql"
    assert db_meta["status"] == "approved"
    assert "conn_url_enc" not in db_meta


# ---------------------------------------------------------------------------
# Tests — Full export has 6 top-level keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_has_six_top_level_keys(async_session: AsyncSession, seeded_db: int):
    """Export dict has exactly 6 top-level keys: database, canonical_entities, canonical_relationships, canonical_dimensions, canonical_metrics, metric_versions."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    expected_keys = {
        "database",
        "canonical_entities",
        "canonical_relationships",
        "canonical_dimensions",
        "canonical_metrics",
        "metric_versions",
    }
    assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Tests — Metric Versions top-level section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_metric_versions_section(async_session: AsyncSession, seeded_db: int):
    """metric_versions section includes version, formula, changed_by, change_reason."""
    result = await build_semantic_layer_dict(async_session, seeded_db)

    assert "metric_versions" in result
    versions = result["metric_versions"]
    assert len(versions) == 2
    v1 = next(v for v in versions if v["version"] == 1)
    assert v1["formula"] == "COUNT(orders.order_id)"
    assert "changed_by" in v1
    assert "change_reason" in v1


# ---------------------------------------------------------------------------
# Tests — Serialization helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serialize_to_json_produces_valid_json(async_session: AsyncSession, seeded_db: int):
    """serialize_to_json produces valid JSON with all sections."""
    result = await build_semantic_layer_dict(async_session, seeded_db)
    json_str = serialize_to_json(result)

    import json

    parsed = json.loads(json_str)
    assert "canonical_entities" in parsed
    assert "canonical_relationships" in parsed
    assert "canonical_metrics" in parsed


@pytest.mark.asyncio
async def test_serialize_to_yaml_produces_valid_yaml(async_session: AsyncSession, seeded_db: int):
    """serialize_to_yaml produces valid YAML with all sections."""
    result = await build_semantic_layer_dict(async_session, seeded_db)
    yaml_str = serialize_to_yaml(result)

    import yaml

    parsed = yaml.safe_load(yaml_str)
    assert "canonical_entities" in parsed
    assert "canonical_relationships" in parsed
    assert "canonical_metrics" in parsed


# ---------------------------------------------------------------------------
# Tests — Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_empty_database_has_empty_lists(async_session: AsyncSession):
    """Export for a database with no tables/metrics returns empty lists."""
    db_model = SemanticDatabaseModel(
        created_by=1,
        display_name="Empty DB",
        db_type="mysql",
        conn_url_enc="encrypted:empty",
        status="draft",
    )
    async_session.add(db_model)
    await async_session.flush()

    result = await build_semantic_layer_dict(async_session, db_model.id)

    assert result["canonical_entities"] == []
    assert result["canonical_relationships"] == []
    assert result["canonical_dimensions"] == []
    assert result["canonical_metrics"] == []
    assert result["metric_versions"] == []


@pytest.mark.asyncio
async def test_export_nonexistent_database_raises(async_session: AsyncSession):
    """Raises ValueError when database ID does not exist."""
    with pytest.raises(ValueError, match="not found"):
        await build_semantic_layer_dict(async_session, 9999)
