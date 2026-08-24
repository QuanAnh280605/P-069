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

from src.models.db import SemanticColumnModel, SemanticTableModel, utc_now
from src.models.review_mixin import REVIEW_STATUS_APPROVED, REVIEW_STATUS_PENDING

logger = logging.getLogger(__name__)


class SchemaRowNotFoundError(LookupError):
    """Raised when a reviewed table or column does not exist for a database."""


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


async def pending_review_counts(db: AsyncSession, db_id: int) -> dict[str, int]:
    """Count table and column rows still awaiting BA/DA approval."""
    table_stmt = (
        select(func.count())
        .select_from(SemanticTableModel)
        .where(
            SemanticTableModel.db_id == db_id,
            SemanticTableModel.review_status == REVIEW_STATUS_PENDING,
        )
    )
    column_stmt = (
        select(func.count())
        .select_from(SemanticColumnModel)
        .join(SemanticTableModel, SemanticColumnModel.table_id == SemanticTableModel.id)
        .where(
            SemanticTableModel.db_id == db_id,
            SemanticColumnModel.review_status == REVIEW_STATUS_PENDING,
        )
    )
    return {
        "pending_tables": (await db.execute(table_stmt)).scalar_one(),
        "pending_columns": (await db.execute(column_stmt)).scalar_one(),
    }


async def load_review_tables(db: AsyncSession, db_id: int) -> list[SemanticTableModel]:
    """Load every semantic table of *db_id* with its columns eagerly loaded."""
    stmt = (
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
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


def _approve_row(row: Any, actor_id: int) -> bool:
    """Stamp *row* as approved, returning True when it was still pending."""
    if row.review_status == REVIEW_STATUS_APPROVED:
        return False
    row.review_status = REVIEW_STATUS_APPROVED
    row.reviewed_by = actor_id
    row.reviewed_at = utc_now()
    return True


async def approve_schema(
    db: AsyncSession,
    db_id: int,
    actor_id: int,
    table_names: list[str] | None = None,
) -> dict[str, int]:
    """Approve pending tables and their columns into the official Metadata Store.

    Passing *table_names* approves only that subset, letting reviewers publish
    incrementally. Returns the number of rows promoted plus what remains pending.
    """
    tables = await load_review_tables(db, db_id)
    if table_names is not None:
        target_names = {t.lower() for t in table_names}
        selected = [item for item in tables if item.table_name.lower() in target_names]
        found_names = {item.table_name.lower() for item in selected}
        missing = target_names - found_names
        if missing:
            raise SchemaRowNotFoundError(f"Tables not found in database {db_id}: {sorted(missing)}")
    else:
        selected = tables

    approved_tables = sum(1 for table in selected if _approve_row(table, actor_id))
    approved_columns = 0
    for table in selected:
        approved_columns += sum(1 for column in table.columns if _approve_row(column, actor_id))

    await db.flush()
    remaining = await pending_review_counts(db, db_id)
    logger.info(
        "Schema review approved db_id=%s tables=%d columns=%d actor=%s",
        db_id,
        approved_tables,
        approved_columns,
        actor_id,
    )
    return {
        "approved_tables": approved_tables,
        "approved_columns": approved_columns,
        **remaining,
    }
