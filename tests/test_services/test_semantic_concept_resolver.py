"""Unit tests for dynamic semantic schema context and multi-hop reachability."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.db import (
    Base,
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticTableModel,
)
from src.services.semantic_concept_resolver import (
    find_grounded_candidate_dimensions,
    format_semantic_schema_for_prompt,
    get_reachable_semantic_schema,
    strip_accents,
)


def test_strip_accents():
    """Verify Vietnamese accents are correctly stripped and normalized."""
    assert strip_accents("Doanh thu theo vùng miền") == "doanh thu theo vung mien"
    assert strip_accents("Hà Nội & TP. Hồ Chí Minh") == "ha noi & tp. ho chi minh"
    assert strip_accents("Đơn hàng đã hoàn thành") == "don hang da hoan thanh"


@pytest.mark.asyncio
async def test_get_reachable_semantic_schema_multihop():
    """Verify 4-hop reachable schema discovery without rule-based taxonomy."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        # Create database
        db_record = SemanticDatabaseModel(id=1, display_name="Test DB", db_type="sqlite", conn_url_enc="mock_enc_url")
        session.add(db_record)

        # Create 5 tables in 4-hop chain
        t_items = SemanticTableModel(id=10, db_id=1, table_name="order_items", business_name="Chi tiết đơn")
        t_orders = SemanticTableModel(id=20, db_id=1, table_name="orders", business_name="Đơn hàng")
        t_cust = SemanticTableModel(id=30, db_id=1, table_name="customers", business_name="Khách hàng")
        t_addr = SemanticTableModel(id=40, db_id=1, table_name="addresses", business_name="Địa chỉ")
        t_city = SemanticTableModel(id=50, db_id=1, table_name="cities", business_name="Thành phố")
        session.add_all([t_items, t_orders, t_cust, t_addr, t_city])

        # Columns
        c_city = SemanticColumnModel(
            id=501,
            table_id=50,
            column_name="city_name",
            data_type="VARCHAR",
            business_name="Tên thành phố",
            allowed_values=["Hà Nội", "TP. Hồ Chí Minh"],
        )
        c_region = SemanticColumnModel(
            id=502,
            table_id=50,
            column_name="region_name",
            data_type="VARCHAR",
            business_name="Vùng miền",
            allowed_values=["Miền Bắc", "Miền Nam"],
        )
        session.add_all([c_city, c_region])

        # Relationships creating 4-hop chain: 10 -> 20 -> 30 -> 40 -> 50
        rels = [
            CanonicalRelationshipModel(
                connection_id=1,
                relationship_key="10:order_id:20",
                from_entity_id=10,
                to_entity_id=20,
                join_condition="order_items.order_id = orders.id",
                relationship_type="many_to_one",
                validation_status="valid",
                review_status="approved",
            ),
            CanonicalRelationshipModel(
                connection_id=1,
                relationship_key="20:customer_id:30",
                from_entity_id=20,
                to_entity_id=30,
                join_condition="orders.customer_id = customers.id",
                relationship_type="many_to_one",
                validation_status="valid",
                review_status="approved",
            ),
            CanonicalRelationshipModel(
                connection_id=1,
                relationship_key="30:address_id:40",
                from_entity_id=30,
                to_entity_id=40,
                join_condition="customers.address_id = addresses.id",
                relationship_type="many_to_one",
                validation_status="valid",
                review_status="approved",
            ),
            CanonicalRelationshipModel(
                connection_id=1,
                relationship_key="40:city_id:50",
                from_entity_id=40,
                to_entity_id=50,
                join_condition="addresses.city_id = cities.id",
                relationship_type="many_to_one",
                validation_status="valid",
                review_status="approved",
            ),
        ]
        session.add_all(rels)
        await session.commit()

        schema = await get_reachable_semantic_schema(session, 1, [10], max_hops=4)
        assert len(schema) >= 1

        city_tbl = next((t for t in schema if t["table_name"] == "cities"), None)
        assert city_tbl is not None
        assert city_tbl["hops"] == 4
        assert len(city_tbl["dimensions"]) == 2

        col_names = {d["column_name"] for d in city_tbl["dimensions"]}
        assert "city_name" in col_names
        assert "region_name" in col_names

        prompt_text = format_semantic_schema_for_prompt(schema)
        assert "Thành phố (cities)" in prompt_text
        assert "Tên thành phố" in prompt_text
        assert "Vùng miền" in prompt_text

        candidates = await find_grounded_candidate_dimensions(session, 1, 10, limit=4)
        assert len(candidates) == 2
        assert candidates[0].column_id in (501, 502)
