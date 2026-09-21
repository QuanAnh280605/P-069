"""HITL review state for canonical schema metadata (tables & columns).

The pipeline never publishes AI-proposed business names directly: enrichment
writes them as ``pending_review`` and a BA/DA must edit and approve them before
they count as officially stored in the Metadata Store. Human-approved names are
never clobbered by a later re-generation — the new AI proposal is kept aside in
``ai_business_name`` so the reviewer can accept or ignore it.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticTableModel,
    utc_now,
)
from src.models.review_mixin import REVIEW_STATUS_APPROVED, REVIEW_STATUS_PENDING
from src.models.review_schemas import ReviewRelationshipItem
from src.services.join_path_service import ambiguous_relationship_groups

logger = logging.getLogger(__name__)


class SchemaRowNotFoundError(LookupError):
    """Raised when a reviewed table or column does not exist for a database."""


class RelationshipValidationError(ValueError):
    """Raised when an approval targets a technically-invalid relationship."""

    def __init__(self, relationship_id: int, detail: str) -> None:
        self.relationship_id = relationship_id
        super().__init__(detail)


def apply_ai_proposal(row: Any, business_name: str, description: str) -> None:
    """Record an AI proposal on *row* without overwriting approved human edits.

    Pending rows adopt the proposal directly. Already-approved rows keep their
    reviewed value and only re-enter review when the proposal actually differs.
    """
    row.ai_business_name = business_name
    row.ai_description = description
    if row.review_status == REVIEW_STATUS_APPROVED:
        if business_name != row.business_name or description != row.description:
            row.review_status = REVIEW_STATUS_PENDING
        return
    row.business_name = business_name
    row.description = description
    row.review_status = REVIEW_STATUS_PENDING


async def _count_pending_relationships(db: AsyncSession, db_id: int) -> int:
    """Count canonical relationships of *db_id* still awaiting approval."""
    stmt = (
        select(func.count())
        .select_from(CanonicalRelationshipModel)
        .where(
            CanonicalRelationshipModel.connection_id == db_id,
            CanonicalRelationshipModel.review_status == REVIEW_STATUS_PENDING,
        )
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def pending_review_counts(db: AsyncSession, db_id: int) -> dict[str, int]:
    """Count table, column and relationship rows still awaiting BA/DA approval."""
    table_stmt = (
        select(func.count())
        .select_from(SemanticTableModel)
        .where(
            SemanticTableModel.db_id == db_id,
            SemanticTableModel.review_status == REVIEW_STATUS_PENDING,
            ~SemanticTableModel.business_name.startswith("[Deprecated]"),
        )
    )
    column_stmt = (
        select(func.count())
        .select_from(SemanticColumnModel)
        .join(SemanticTableModel, SemanticColumnModel.table_id == SemanticTableModel.id)
        .where(
            SemanticTableModel.db_id == db_id,
            SemanticColumnModel.review_status == REVIEW_STATUS_PENDING,
            ~SemanticTableModel.business_name.startswith("[Deprecated]"),
            ~SemanticColumnModel.business_name.startswith("[Deprecated]"),
        )
    )
    return {
        "pending_tables": int((await db.execute(table_stmt)).scalar_one() or 0),
        "pending_columns": int((await db.execute(column_stmt)).scalar_one() or 0),
        "pending_relationships": await _count_pending_relationships(db, db_id),
    }


async def load_review_tables(db: AsyncSession, db_id: int) -> list[SemanticTableModel]:
    """Load every active semantic table of *db_id* with its columns eagerly loaded."""
    stmt = (
        select(SemanticTableModel)
        .where(
            SemanticTableModel.db_id == db_id,
            ~SemanticTableModel.business_name.startswith("[Deprecated]"),
        )
        .options(selectinload(SemanticTableModel.columns))
        .order_by(SemanticTableModel.table_name)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _require_table(db: AsyncSession, db_id: int, table_name: str) -> SemanticTableModel:
    """Load one table of *db_id* by physical name or raise SchemaRowNotFoundError."""
    stmt = select(SemanticTableModel).where(
        SemanticTableModel.db_id == db_id,
        SemanticTableModel.table_name == table_name,
    )
    table = (await db.execute(stmt)).scalar_one_or_none()
    if table is None:
        raise SchemaRowNotFoundError(f"Table {table_name} not found in database {db_id}")
    return table


async def _require_column(db: AsyncSession, db_id: int, table_name: str, column_name: str) -> SemanticColumnModel:
    """Load one column of *db_id* by physical names or raise SchemaRowNotFoundError."""
    table = await _require_table(db, db_id, table_name)
    stmt = select(SemanticColumnModel).where(
        SemanticColumnModel.table_id == table.id,
        SemanticColumnModel.column_name == column_name,
    )
    column = (await db.execute(stmt)).scalar_one_or_none()
    if column is None:
        raise SchemaRowNotFoundError(f"Column {column_name} not found in table {table_name}")
    return column


def _apply_inline_edit(row: Any, business_name: str, description: str, actor_id: int) -> None:
    """Store a reviewer's inline edit and keep the row awaiting explicit approval."""
    row.business_name = business_name.strip()
    row.description = description.strip()
    row.updated_by = actor_id
    row.review_status = REVIEW_STATUS_PENDING
    row.reviewed_by = None
    row.reviewed_at = None


async def update_table_review(
    db: AsyncSession,
    db_id: int,
    table_name: str,
    business_name: str,
    description: str,
    actor_id: int,
) -> SemanticTableModel:
    """Apply an inline edit to a table's business name and description."""
    table = await _require_table(db, db_id, table_name)
    _apply_inline_edit(table, business_name, description, actor_id)
    await db.flush()
    return table


async def update_column_review(
    db: AsyncSession,
    db_id: int,
    table_name: str,
    column_name: str,
    business_name: str,
    description: str,
    actor_id: int,
) -> SemanticColumnModel:
    """Apply an inline edit to a column's business name and description."""
    column = await _require_column(db, db_id, table_name, column_name)
    _apply_inline_edit(column, business_name, description, actor_id)
    await db.flush()
    return column


async def load_review_relationships(db: AsyncSession, db_id: int) -> list[CanonicalRelationshipModel]:
    """Load every canonical relationship of *db_id* with its endpoints eagerly loaded."""
    stmt = (
        select(CanonicalRelationshipModel)
        .where(CanonicalRelationshipModel.connection_id == db_id)
        .options(
            selectinload(CanonicalRelationshipModel.from_entity),
            selectinload(CanonicalRelationshipModel.to_entity),
        )
        .order_by(CanonicalRelationshipModel.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_relationship_review(
    db: AsyncSession,
    db_id: int,
    relationship_id: int,
    business_name: str,
    description: str,
    actor_id: int,
) -> CanonicalRelationshipModel:
    """Apply an inline edit to a relationship's business name and description."""
    stmt = select(CanonicalRelationshipModel).where(
        CanonicalRelationshipModel.id == relationship_id,
        CanonicalRelationshipModel.connection_id == db_id,
    )
    rel = (await db.execute(stmt)).scalar_one_or_none()
    if rel is None:
        raise SchemaRowNotFoundError(f"Relationship {relationship_id} not found in database {db_id}")
    _apply_inline_edit(rel, business_name, description, actor_id)
    await db.flush()
    return rel


def _collect_relationship_column_ids(relationships: list[CanonicalRelationshipModel]) -> set[int]:
    """Collect every column id referenced by the relationships' column pairs."""
    ids: set[int] = set()
    for rel in relationships:
        for pair in rel.column_pairs or []:
            for cid in (pair.get("from_column_id"), pair.get("to_column_id")):
                if cid is not None:
                    ids.add(cid)
    return ids


async def _load_column_name_map(db: AsyncSession, col_ids: set[int]) -> dict[int, tuple[str, str]]:
    """Map column id -> (table_name, column_name) for the given ids."""
    if not col_ids:
        return {}
    cols = (
        await db.execute(
            select(SemanticColumnModel, SemanticTableModel.table_name)
            .join(SemanticTableModel, SemanticColumnModel.table_id == SemanticTableModel.id)
            .where(SemanticColumnModel.id.in_(col_ids))
        )
    ).all()
    return {col.id: (table_name, col.column_name) for col, table_name in cols}


def _build_review_relationship_item(
    rel: CanonicalRelationshipModel,
    col_map: dict[int, tuple[str, str]],
    ambiguity: dict[int, list[dict[str, object]]],
) -> ReviewRelationshipItem:
    """Build the review DTO for one relationship, including column-pair labels."""
    pairs: list[dict[str, object]] = []
    for pair in rel.column_pairs or []:
        fc = col_map.get(pair.get("from_column_id"))  # type: ignore[arg-type]
        tc = col_map.get(pair.get("to_column_id"))  # type: ignore[arg-type]
        pairs.append(
            {
                "from_column_id": pair.get("from_column_id"),
                "to_column_id": pair.get("to_column_id"),
                "from_column_name": fc[1] if fc else None,
                "to_column_name": tc[1] if tc else None,
            }
        )
    return ReviewRelationshipItem(
        relationship_id=rel.id,
        from_entity_id=rel.from_entity_id,
        to_entity_id=rel.to_entity_id,
        from_table_name=rel.from_entity.table_name if rel.from_entity else "",
        to_table_name=rel.to_entity.table_name if rel.to_entity else "",
        column_pairs=pairs,
        business_name=rel.business_name,
        description=rel.description,
        ai_business_name=rel.ai_business_name,
        ai_description=rel.ai_description,
        validation_status=rel.validation_status,
        review_status=rel.review_status,
        ambiguous_target_groups=ambiguity.get(rel.id, []),
    )


async def load_review_relationship_items(db: AsyncSession, db_id: int) -> list[ReviewRelationshipItem]:
    """Build review DTOs for every canonical relationship of *db_id*.

    Each item exposes the physical endpoints/columns, the editable governance
    fields plus their AI suggestion, the two independent status signals, and any
    ambiguous join-path groups that a reviewer must disambiguate.
    """
    relationships = await load_review_relationships(db, db_id)
    if not relationships:
        return []
    col_ids = _collect_relationship_column_ids(relationships)
    col_map = await _load_column_name_map(db, col_ids)
    ambiguity = ambiguous_relationship_groups(relationships)
    return [_build_review_relationship_item(rel, col_map, ambiguity) for rel in relationships]


def _approve_row(row: Any, actor_id: int) -> bool:
    """Stamp *row* as approved, returning True when it was still pending."""
    if row.review_status == REVIEW_STATUS_APPROVED:
        return False
    row.review_status = REVIEW_STATUS_APPROVED
    row.reviewed_by = actor_id
    row.reviewed_at = utc_now()
    return True


def _select_tables_to_approve(
    tables: list[SemanticTableModel], table_names: list[str] | None
) -> list[SemanticTableModel]:
    """Return the tables to approve, or raise if a named table is unknown."""
    if table_names is None:
        return tables
    target_names = {name.lower() for name in table_names}
    selected = [item for item in tables if item.table_name.lower() in target_names]
    missing = target_names - {item.table_name.lower() for item in selected}
    if missing:
        raise SchemaRowNotFoundError(f"Tables not found in database: {sorted(missing)}")
    return selected


async def approve_schema(
    db: AsyncSession,
    db_id: int,
    actor_id: int,
    table_names: list[str] | None = None,
    relationship_ids: list[int] | None = None,
) -> dict[str, int]:
    """Approve pending tables, columns and valid relationships into the Metadata Store.

    *table_names* / *relationship_ids* scope the approval to a subset; invalid
    relationships are never approved and requesting one raises
    ``RelationshipValidationError``. Returns promoted counts plus what remains pending.
    """
    tables = await load_review_tables(db, db_id)
    selected = _select_tables_to_approve(tables, table_names)

    approved_tables = sum(1 for table in selected if _approve_row(table, actor_id))
    approved_columns = 0
    for table in selected:
        approved_columns += sum(1 for column in table.columns if _approve_row(column, actor_id))

    approved_relationships = await _approve_relationships(db, db_id, actor_id, relationship_ids)

    await db.flush()
    remaining = await pending_review_counts(db, db_id)
    logger.info(
        "Schema review approved db_id=%s tables=%d columns=%d relationships=%d actor=%s",
        db_id,
        approved_tables,
        approved_columns,
        approved_relationships,
        actor_id,
    )
    return {
        "approved_tables": approved_tables,
        "approved_columns": approved_columns,
        "approved_relationships": approved_relationships,
        **remaining,
    }


def _resolve_requested_relationships(
    rel_by_id: dict[int, CanonicalRelationshipModel],
    relationship_ids: list[int],
    db_id: int,
) -> list[CanonicalRelationshipModel]:
    """Return the requested relationships, raising on unknown or invalid ids."""
    targets: list[CanonicalRelationshipModel] = []
    for rid in relationship_ids:
        rel = rel_by_id.get(rid)
        if rel is None:
            raise SchemaRowNotFoundError(f"Relationship {rid} not found in database {db_id}")
        if rel.validation_status != "valid":
            raise RelationshipValidationError(
                rid,
                f"Relationship {rid} is technically invalid (validation_status="
                f"{rel.validation_status!r}) and cannot be approved",
            )
        targets.append(rel)
    return targets


async def _approve_relationships(
    db: AsyncSession,
    db_id: int,
    actor_id: int,
    relationship_ids: list[int] | None,
) -> int:
    """Approve valid relationships, returning the count promoted.

    With *relationship_ids* set, every id must be valid; an invalid id raises
    ``RelationshipValidationError``. With *relationship_ids* ``None`` all valid
    pending relationships are approved and invalid ones stay blocked.
    """
    relationships = await load_review_relationships(db, db_id)
    rel_by_id = {rel.id: rel for rel in relationships}
    targets = (
        _resolve_requested_relationships(rel_by_id, list(relationship_ids), db_id)
        if relationship_ids is not None
        else relationships
    )

    promoted = 0
    for rel in targets:
        if rel.validation_status == "valid" and _approve_row(rel, actor_id):
            promoted += 1
    return promoted
