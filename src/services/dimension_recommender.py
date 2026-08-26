"""Service for recommending contextual dimensions for semantic metrics."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.models.schemas import FilterColumnItem, RecommendedDimensionItem

JUNK_KEYWORDS = {
    "note",
    "notes",
    "comment",
    "comments",
    "description",
    "address",
    "email",
    "phone",
    "mobile",
    "ip",
    "ip_address",
    "url",
    "link",
    "password",
    "token",
    "secret",
    "hash",
    "salt",
    "deleted",
    "raw",
    "avatar",
    "json",
    "payload",
    "body",
    "content",
}

NUMERIC_TYPES = {
    "INT",
    "INTEGER",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "NUMERIC",
    "REAL",
    "BIGINT",
    "SMALLINT",
    "MONEY",
    "NUMBER",
}

TIME_TYPES = {"DATE", "TIME", "TIMESTAMP", "DATETIME", "TIMESTAMPTZ"}


def is_valid_dimension_column(col: SemanticColumnModel) -> bool:
    """Validate if a column is a clean categorical/entity business dimension."""
    if col.is_primary_key or col.is_foreign_key:
        return False
    dt = (col.data_type or "").upper()
    if any(t in dt for t in TIME_TYPES) or col.is_time_dimension:
        return False
    if any(t in dt for t in NUMERIC_TYPES):
        if not col.allowed_values or len(col.allowed_values) > 30:
            return False
    name = col.column_name.lower()
    if any(junk in name for junk in JUNK_KEYWORDS):
        return False
    if col.allowed_values and len(col.allowed_values) > 30:
        return False
    return True


def _make_dimension_item(
    col: SemanticColumnModel,
    table: SemanticTableModel,
    tier: str,
    is_safe: bool,
    requires_reaggregation: bool,
) -> RecommendedDimensionItem:
    """Helper to instantiate RecommendedDimensionItem."""
    tier_labels = {
        "A": "Trực tiếp",
        "B": "Liên kết trực tiếp (N:1)",
        "C": "Liên kết mở rộng (N:1)",
        "D": "Chi tiết dòng hàng (1:N)",
    }
    cardinality = len(col.allowed_values) if col.allowed_values else None
    return RecommendedDimensionItem(
        column_id=col.id,
        column_name=col.column_name,
        business_name=col.business_name or col.column_name,
        table_id=table.id,
        table_name=table.table_name,
        table_business_name=table.business_name or table.table_name,
        tier=tier,
        tier_label=tier_labels.get(tier, tier),
        is_safe_join=is_safe,
        requires_reaggregation=requires_reaggregation,
        data_type=col.data_type,
        cardinality_hint=cardinality,
    )


def _collect_tier_a(base_table: SemanticTableModel) -> list[RecommendedDimensionItem]:
    """Collect Tier A (core) dimensions from the metric's base table."""
    items = []
    for col in base_table.columns:
        if is_valid_dimension_column(col):
            items.append(_make_dimension_item(col, base_table, "A", True, False))
    return items


def _collect_outgoing_rel_dims(
    tables_map: dict[int, SemanticTableModel],
    relationships: list[CanonicalRelationshipModel],
    source_table_id: int,
    tier: str,
) -> list[tuple[int, RecommendedDimensionItem]]:
    """Collect Tier B or C dimensions via outgoing N:1 or 1:1 relations."""
    results = []
    for rel in relationships:
        r_type = (rel.relationship_type or "").lower()
        is_n1 = r_type in ("many_to_one", "n:1", "one_to_one", "1:1")
        if rel.from_entity_id == source_table_id and is_n1:
            target_table = tables_map.get(rel.to_entity_id)
            if not target_table:
                continue
            for col in target_table.columns:
                if is_valid_dimension_column(col):
                    item = _make_dimension_item(col, target_table, tier, True, False)
                    results.append((rel.to_entity_id, item))
    return results


async def get_dimensions_for_metric(
    db: AsyncSession,
    db_id: int,
    metric_id: int,
    limit: int = 12,
) -> list[RecommendedDimensionItem]:
    """Recommend high-signal dimensions for a given metric across Tier A, B, and C (Safe N:1/1:1 joins)."""
    stmt_metric = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.is_deleted.is_(False),
    )
    metric = (await db.execute(stmt_metric)).scalar_one_or_none()
    if not metric or not metric.base_entity_id:
        return []

    stmt_tables = (
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
        .options(selectinload(SemanticTableModel.columns))
    )
    tables = (await db.execute(stmt_tables)).scalars().all()
    tables_map = {t.id: t for t in tables}

    base_table = tables_map.get(metric.base_entity_id)
    if not base_table:
        return []

    stmt_rels = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
    relationships = (await db.execute(stmt_rels)).scalars().all()

    # 1. Tier A (Core - same base table)
    tier_a_items = _collect_tier_a(base_table)

    # 2. Tier B (1-Hop N:1 / 1:1)
    tier_b_raw = _collect_outgoing_rel_dims(tables_map, relationships, base_table.id, "B")
    tier_b_items = [item for _, item in tier_b_raw]
    tier_b_target_ids = {target_id for target_id, _ in tier_b_raw}

    # 3. Tier C (2-Hop N:1 / 1:1)
    tier_c_items = []
    for t_id in tier_b_target_ids:
        tier_c_raw = _collect_outgoing_rel_dims(tables_map, relationships, t_id, "C")
        tier_c_items.extend([item for _, item in tier_c_raw if item.table_id != base_table.id])

    # Deduplicate via diamond path (Keep Tier A > B > C)
    all_candidates: list[RecommendedDimensionItem] = []
    seen_col_ids = set()

    for item in tier_a_items + tier_b_items + tier_c_items:
        if item.column_id not in seen_col_ids:
            seen_col_ids.add(item.column_id)
            all_candidates.append(item)

    all_candidates.sort(key=lambda x: (x.tier, x.cardinality_hint or 999))
    return all_candidates[:limit]


def is_valid_filter_column(col: SemanticColumnModel) -> bool:
    """Validate if a column is a clean and meaningful filterable column."""
    if col.is_foreign_key:
        return False
    name = col.column_name.lower()
    if any(junk in name for junk in JUNK_KEYWORDS):
        return False
    return True


def _make_filter_column_item(
    col: SemanticColumnModel,
    table: SemanticTableModel,
    group_type: Literal["base", "related"],
) -> FilterColumnItem:
    """Helper to instantiate FilterColumnItem."""
    return FilterColumnItem(
        column_id=col.id,
        column_name=col.column_name,
        business_name=col.business_name or col.column_name,
        table_id=table.id,
        table_name=table.table_name,
        table_business_name=table.business_name or table.table_name,
        group_type=group_type,
        data_type=col.data_type or "VARCHAR",
        is_time_dimension=bool(col.is_time_dimension),
    )


def _collect_safe_outgoing_table_ids(
    relationships: list[CanonicalRelationshipModel],
    source_id: int,
) -> set[int]:
    """Find target table IDs reachable via outgoing safe N:1 / 1:1 relations."""
    target_ids = set()
    for rel in relationships:
        r_type = (rel.relationship_type or "").lower()
        if rel.from_entity_id == source_id and r_type in ("many_to_one", "n:1", "one_to_one", "1:1"):
            target_ids.add(rel.to_entity_id)
    return target_ids


def _collect_related_filter_items(
    tables_map: dict[int, SemanticTableModel],
    target_ids: set[int],
    seen_col_ids: set[int],
) -> list[FilterColumnItem]:
    """Collect filterable columns from target related tables."""
    items: list[FilterColumnItem] = []
    for target_id in sorted(target_ids):
        target_table = tables_map.get(target_id)
        if not target_table:
            continue
        for col in target_table.columns:
            if col.id not in seen_col_ids and is_valid_filter_column(col):
                seen_col_ids.add(col.id)
                items.append(_make_filter_column_item(col, target_table, "related"))
    return items


async def get_filter_columns_for_metric(
    db: AsyncSession,
    db_id: int,
    metric_id: int,
) -> list[FilterColumnItem]:
    """Retrieve safe, scoped filter columns for a metric from base and reachable related tables."""
    stmt_metric = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.is_deleted.is_(False),
    )
    metric = (await db.execute(stmt_metric)).scalar_one_or_none()
    if not metric or not metric.base_entity_id:
        return []

    stmt_tables = (
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
        .options(selectinload(SemanticTableModel.columns))
    )
    tables = (await db.execute(stmt_tables)).scalars().all()
    tables_map = {t.id: t for t in tables}
    base_table = tables_map.get(metric.base_entity_id)
    if not base_table:
        return []

    stmt_rels = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
    relationships = (await db.execute(stmt_rels)).scalars().all()

    base_items = [
        _make_filter_column_item(c, base_table, "base") for c in base_table.columns if is_valid_filter_column(c)
    ]
    seen_col_ids = {item.column_id for item in base_items}

    hop1 = _collect_safe_outgoing_table_ids(relationships, base_table.id)
    hop2 = set()
    for t_id in hop1:
        hop2.update(_collect_safe_outgoing_table_ids(relationships, t_id))
    all_targets = (hop1 | hop2) - {base_table.id}

    related_items = _collect_related_filter_items(tables_map, all_targets, seen_col_ids)
    return base_items + related_items
