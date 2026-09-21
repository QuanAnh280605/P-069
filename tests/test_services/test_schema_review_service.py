"""Tests for the HITL schema-review state: inline edits, approval, and re-generation safety."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticTableModel,
)
from src.models.review_mixin import REVIEW_STATUS_APPROVED, REVIEW_STATUS_PENDING
from src.services.schema_review_service import (
    RelationshipValidationError,
    SchemaRowNotFoundError,
    apply_ai_proposal,
    approve_schema,
    load_review_relationship_items,
    load_review_tables,
    pending_review_counts,
    update_column_review,
    update_relationship_review,
    update_table_review,
)


async def _seed(db: AsyncSession) -> tuple[int, SemanticTableModel, SemanticColumnModel]:
    """Seed one pending table with one pending column."""
    sem_db = SemanticDatabaseModel(
        created_by=1,
        display_name="Review DB",
        db_type="postgresql",
        conn_url_enc="encrypted",
        status="draft",
    )
    db.add(sem_db)
    await db.flush()
    table = SemanticTableModel(
        db_id=sem_db.id,
        table_name="orders",
        business_name="Đơn hàng",
        description="AI mô tả",
        ai_business_name="Đơn hàng",
        ai_description="AI mô tả",
        review_status=REVIEW_STATUS_PENDING,
    )
    db.add(table)
    await db.flush()
    column = SemanticColumnModel(
        table_id=table.id,
        column_name="total",
        data_type="NUMERIC",
        business_name="Tổng",
        description="",
        review_status=REVIEW_STATUS_PENDING,
    )
    db.add(column)
    await db.flush()
    return sem_db.id, table, column


# ---------------------------------------------------------------------------
# apply_ai_proposal — a re-generation must never clobber approved names
# ---------------------------------------------------------------------------


def test_ai_proposal_adopted_while_pending():
    """A row still in review adopts the AI proposal directly."""
    row = SemanticTableModel(
        db_id=1, table_name="orders", business_name="", description="", review_status=REVIEW_STATUS_PENDING
    )

    apply_ai_proposal(row, "Đơn hàng", "Bảng đơn hàng")

    assert row.business_name == "Đơn hàng"
    assert row.ai_business_name == "Đơn hàng"
    assert row.review_status == REVIEW_STATUS_PENDING


def test_ai_proposal_keeps_approved_value_and_reopens_review():
    """An approved name survives re-generation; only the review flag re-opens."""
    row = SemanticTableModel(
        db_id=1,
        table_name="orders",
        business_name="Đơn đặt hàng",
        description="Đã review",
        review_status=REVIEW_STATUS_APPROVED,
    )

    apply_ai_proposal(row, "Đơn hàng", "AI mô tả mới")

    assert row.business_name == "Đơn đặt hàng"
    assert row.description == "Đã review"
    assert row.ai_business_name == "Đơn hàng"
    assert row.review_status == REVIEW_STATUS_PENDING


def test_identical_ai_proposal_leaves_approved_row_untouched():
    """A proposal matching the approved value does not drag the row back into the queue."""
    row = SemanticTableModel(
        db_id=1,
        table_name="orders",
        business_name="Đơn hàng",
        description="Bảng đơn hàng",
        review_status=REVIEW_STATUS_APPROVED,
    )

    apply_ai_proposal(row, "Đơn hàng", "Bảng đơn hàng")

    assert row.review_status == REVIEW_STATUS_APPROVED


# ---------------------------------------------------------------------------
# Inline edit + approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inline_edit_stays_pending_and_clears_stamp(async_session: AsyncSession):
    """A reviewer edit is not an approval — it clears any previous stamp."""
    db_id, table, _ = await _seed(async_session)
    table.review_status = REVIEW_STATUS_APPROVED
    table.reviewed_by = 9
    await async_session.flush()

    edited = await update_table_review(async_session, db_id, "orders", "  Đơn đặt hàng  ", " Đã review ", 1)

    assert edited.business_name == "Đơn đặt hàng"
    assert edited.description == "Đã review"
    assert edited.updated_by == 1
    assert edited.review_status == REVIEW_STATUS_PENDING
    assert edited.reviewed_by is None
    assert edited.reviewed_at is None


@pytest.mark.asyncio
async def test_column_inline_edit_and_missing_rows(async_session: AsyncSession):
    """Column edits work by physical names; unknown rows raise SchemaRowNotFoundError."""
    db_id, _, _ = await _seed(async_session)

    column = await update_column_review(async_session, db_id, "orders", "total", "Tổng tiền", "Tổng giá trị", 1)
    assert column.business_name == "Tổng tiền"

    with pytest.raises(SchemaRowNotFoundError, match="Column"):
        await update_column_review(async_session, db_id, "orders", "ghost", "X", "", 1)
    with pytest.raises(SchemaRowNotFoundError, match="Table"):
        await update_table_review(async_session, db_id, "ghost", "X", "", 1)


@pytest.mark.asyncio
async def test_approve_schema_promotes_tables_and_columns(async_session: AsyncSession):
    """Approval stamps every pending row and empties the queue."""
    db_id, _, _ = await _seed(async_session)
    assert await pending_review_counts(async_session, db_id) == {
        "pending_tables": 1,
        "pending_columns": 1,
        "pending_relationships": 0,
    }

    result = await approve_schema(async_session, db_id, actor_id=7)

    assert result == {
        "approved_tables": 1,
        "approved_columns": 1,
        "approved_relationships": 0,
        "pending_tables": 0,
        "pending_columns": 0,
        "pending_relationships": 0,
    }
    table = (await load_review_tables(async_session, db_id))[0]
    assert table.review_status == REVIEW_STATUS_APPROVED
    assert table.reviewed_by == 7
    assert table.reviewed_at is not None
    assert table.columns[0].review_status == REVIEW_STATUS_APPROVED
    assert table.columns[0].reviewed_by == 7


@pytest.mark.asyncio
async def test_approve_schema_subset_and_idempotence(async_session: AsyncSession):
    """A subset approval leaves other tables pending; re-approving promotes nothing new."""
    db_id, _, _ = await _seed(async_session)
    async_session.add(
        SemanticTableModel(
            db_id=db_id,
            table_name="customers",
            business_name="Khách hàng",
            description="",
            review_status=REVIEW_STATUS_PENDING,
        )
    )
    await async_session.flush()

    first = await approve_schema(async_session, db_id, actor_id=7, table_names=["orders"])
    assert first["approved_tables"] == 1
    assert first["pending_tables"] == 1

    again = await approve_schema(async_session, db_id, actor_id=7, table_names=["orders"])
    assert again["approved_tables"] == 0
    assert again["approved_columns"] == 0
    assert again["pending_tables"] == 1


@pytest.mark.asyncio
async def test_approve_schema_unknown_table_raises(async_session: AsyncSession):
    """Naming a table that does not exist is an error, not a silent no-op."""
    db_id, _, _ = await _seed(async_session)

    with pytest.raises(SchemaRowNotFoundError, match="ghost"):
        await approve_schema(async_session, db_id, actor_id=7, table_names=["orders", "ghost"])


# ---------------------------------------------------------------------------
# Relationship review: inline edit, approval, invalid rejection, pending counts
# ---------------------------------------------------------------------------


async def _seed_relationship(
    session: AsyncSession,
    db_id: int,
    *,
    validation_status: str = "valid",
    review_status: str = REVIEW_STATUS_PENDING,
    business_name: str = "",
    key_suffix: str = "customers",
) -> CanonicalRelationshipModel:
    """Seed one canonical relationship on the seeded database."""
    rel = CanonicalRelationshipModel(
        connection_id=db_id,
        from_entity_id=1,
        to_entity_id=1,
        relationship_type="many_to_one",
        join_condition="orders.customer_id = customers.id",
        relationship_key=f"orders:orders.customer_id = customers.id:{key_suffix}",
        column_pairs=[{"from_column_id": 1, "to_column_id": 1}],
        validation_status=validation_status,
        review_status=review_status,
        business_name=business_name,
    )
    session.add(rel)
    await session.flush()
    return rel


@pytest.mark.asyncio
async def test_relationship_inline_edit_stays_pending_and_clears_stamp(async_session: AsyncSession):
    """Editing a relationship keeps it pending and clears any prior approval stamp."""
    db_id, _, _ = await _seed(async_session)
    rel = await _seed_relationship(async_session, db_id)
    rel.review_status = REVIEW_STATUS_APPROVED
    rel.reviewed_by = 9
    await async_session.flush()

    edited = await update_relationship_review(
        async_session, db_id, rel.id, "Đơn hàng thuộc về Khách hàng", "Quan hệ nhiều-một", 1
    )

    assert edited.business_name == "Đơn hàng thuộc về Khách hàng"
    assert edited.review_status == REVIEW_STATUS_PENDING
    assert edited.reviewed_by is None
    assert edited.reviewed_at is None


@pytest.mark.asyncio
async def test_relationship_inline_edit_unknown_raises(async_session: AsyncSession):
    """Editing an unknown relationship id is a 404-style lookup error."""
    db_id, _, _ = await _seed(async_session)

    with pytest.raises(SchemaRowNotFoundError, match="9999"):
        await update_relationship_review(async_session, db_id, 9999, "X", "", 1)


@pytest.mark.asyncio
async def test_pending_review_counts_includes_relationships(async_session: AsyncSession):
    """Pending relationship counts surface alongside table/column counts."""
    db_id, _, _ = await _seed(async_session)
    await _seed_relationship(async_session, db_id)

    counts = await pending_review_counts(async_session, db_id)
    assert counts["pending_relationships"] == 1
    assert counts["pending_tables"] == 1


@pytest.mark.asyncio
async def test_approve_schema_promotes_valid_relationships(async_session: AsyncSession):
    """Approval of the whole queue promotes valid relationships too."""
    db_id, _, _ = await _seed(async_session)
    await _seed_relationship(async_session, db_id)

    result = await approve_schema(async_session, db_id, actor_id=7)

    assert result["approved_relationships"] == 1
    assert result["pending_relationships"] == 0
    rel = (await load_review_relationship_items(async_session, db_id))[0]
    assert rel.review_status == REVIEW_STATUS_APPROVED


@pytest.mark.asyncio
async def test_approve_schema_skips_invalid_relationships(async_session: AsyncSession):
    """Technically-invalid relationships stay blocked during approve-all."""
    db_id, _, _ = await _seed(async_session)
    await _seed_relationship(async_session, db_id, validation_status="invalid")

    result = await approve_schema(async_session, db_id, actor_id=7)

    assert result["approved_relationships"] == 0
    assert result["pending_relationships"] == 1


@pytest.mark.asyncio
async def test_approve_schema_invalid_relationship_request_raises(async_session: AsyncSession):
    """Explicitly approving an invalid relationship is rejected with a stable error."""
    db_id, _, _ = await _seed(async_session)
    rel = await _seed_relationship(async_session, db_id, validation_status="invalid")

    with pytest.raises(RelationshipValidationError, match=str(rel.id)):
        await approve_schema(async_session, db_id, actor_id=7, relationship_ids=[rel.id])


@pytest.mark.asyncio
async def test_approve_schema_relationship_subset(async_session: AsyncSession):
    """Approving a named relationship subset leaves others pending."""
    db_id, _, _ = await _seed(async_session)
    rel1 = await _seed_relationship(async_session, db_id, key_suffix="customers")
    rel2 = await _seed_relationship(async_session, db_id, key_suffix="products")

    result = await approve_schema(async_session, db_id, actor_id=7, relationship_ids=[rel1.id])

    assert result["approved_relationships"] == 1
    assert result["pending_relationships"] == 1
    items = {item.relationship_id: item for item in await load_review_relationship_items(async_session, db_id)}
    assert items[rel1.id].review_status == REVIEW_STATUS_APPROVED
    assert items[rel2.id].review_status == REVIEW_STATUS_PENDING


@pytest.mark.asyncio
async def test_load_review_relationship_items_exposes_governance(async_session: AsyncSession):
    """The review DTO exposes endpoints, editable fields, statuses and ambiguity."""
    db_id, _, _ = await _seed(async_session)
    rel = await _seed_relationship(async_session, db_id, business_name="Quan hệ mặc định")

    items = await load_review_relationship_items(async_session, db_id)
    assert len(items) == 1
    item = items[0]
    assert item.relationship_id == rel.id
    assert item.from_entity_id == 1
    assert item.to_entity_id == 1
    assert item.business_name == "Quan hệ mặc định"
    assert item.validation_status == "valid"
    assert item.review_status == REVIEW_STATUS_PENDING
    assert item.ambiguous_target_groups == []
