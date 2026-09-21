"""Semantic schema context service for dynamic dimension discovery.

Extracts database tables and columns reachable via safe many-to-one join paths
from metric base entities, enabling LLM-driven semantic reasoning without
hardcoded rule-based taxonomies or regexes.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticTableModel,
)
from src.services.dimension_recommender import is_valid_dimension_column
from src.services.join_path_service import enumerate_join_paths

logger = logging.getLogger(__name__)


def strip_accents(text: str) -> str:
    """Normalize and strip Vietnamese diacritics for robust matching."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


@dataclass
class GroundedCandidateDimension:
    """A candidate dimension with reachability and schema metadata."""

    column_id: int
    column_name: str
    business_name: str
    table_id: int
    table_name: str
    table_business_name: str
    sample_values: list[str]
    hop_count: int
    label: str


async def get_reachable_semantic_schema(
    db: AsyncSession,
    db_id: int,
    base_table_ids: list[int] | None = None,
    max_hops: int = 4,
) -> list[dict[str, Any]]:
    """Get all tables and valid dimensions reachable from base entities via safe N:1 paths."""
    stmt_tables = (
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
        .options(selectinload(SemanticTableModel.columns))
    )
    tables = list((await db.execute(stmt_tables)).scalars().all())
    if not tables:
        return []

    stmt_rels = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
    rels = list((await db.execute(stmt_rels)).scalars().all())

    return _build_reachable_schema_list(tables, rels, base_table_ids, max_hops)


def _build_reachable_schema_list(
    tables: list[SemanticTableModel],
    rels: list[CanonicalRelationshipModel],
    base_table_ids: list[int] | None,
    max_hops: int,
) -> list[dict[str, Any]]:
    """Filter reachable tables and collect valid descriptive dimensions."""
    base_ids = set(base_table_ids or [t.id for t in tables])
    reachable: list[dict[str, Any]] = []

    for table in tables:
        min_hops = _shortest_hop_to_any_base(rels, base_ids, table.id)
        if min_hops is None or min_hops > max_hops:
            continue

        dims = _extract_table_dimensions(table)
        if dims:
            reachable.append(
                {
                    "table_id": table.id,
                    "table_name": table.table_name,
                    "table_business_name": table.business_name or table.table_name,
                    "hops": min_hops,
                    "dimensions": dims,
                }
            )

    reachable.sort(key=lambda x: (x["hops"], x["table_business_name"]))
    return reachable


def _shortest_hop_to_any_base(
    rels: list[CanonicalRelationshipModel],
    base_ids: set[int],
    target_id: int,
) -> int | None:
    """Find the shortest hop count from any base table to the target table."""
    if target_id in base_ids:
        return 0
    shortest: int | None = None
    for b_id in base_ids:
        paths = enumerate_join_paths(rels, b_id, target_id)
        if paths:
            hops = len(paths[0].relationship_ids)
            if shortest is None or hops < shortest:
                shortest = hops
    return shortest


def _extract_table_dimensions(table: SemanticTableModel) -> list[dict[str, Any]]:
    """Extract clean descriptive dimensions for a semantic table."""
    dims = []
    for col in table.columns:
        if not is_valid_dimension_column(col):
            continue
        samples = _extract_sample_values(col)
        dims.append(
            {
                "column_id": col.id,
                "column_name": col.column_name,
                "business_name": col.business_name or col.column_name,
                "sample_values": samples,
            }
        )
    return dims


def _extract_sample_values(col: SemanticColumnModel) -> list[str]:
    """Extract sample or allowed values from column metadata."""
    raw = col.allowed_values
    if isinstance(raw, list):
        return [str(v) for v in raw if str(v).strip()][:3]
    if isinstance(raw, dict):
        return [str(k) for k in raw if str(k).strip()][:3]
    return []


def format_semantic_schema_for_prompt(schema_items: list[dict[str, Any]]) -> str:
    """Format reachable semantic schema into human-readable text for the LLM prompt."""
    if not schema_items:
        return "Không có chiều phân tích nào được kết nối trong Semantic Layer."

    lines = []
    for item in schema_items:
        tbl_label = f"{item['table_business_name']} ({item['table_name']})"
        col_parts = []
        for d in item["dimensions"][:5]:
            col_label = f"{d['business_name']} (id: {d['column_id']}, col: {d['column_name']})"
            if d.get("sample_values"):
                col_label += f" [Ví dụ: {', '.join(d['sample_values'])}]"
            col_parts.append(col_label)
        lines.append(f"- Bảng {tbl_label}: {'; '.join(col_parts)}")
    return "\n".join(lines)


async def find_grounded_candidate_dimensions(
    db: AsyncSession,
    db_id: int,
    base_table_id: int,
    user_query: str = "",
    limit: int = 4,
) -> list[GroundedCandidateDimension]:
    """Dynamically discover candidate dimensions reachable from base table for tests/compatibility."""
    schema = await get_reachable_semantic_schema(db, db_id, [base_table_id])
    candidates: list[GroundedCandidateDimension] = []
    for item in schema:
        for d in item["dimensions"]:
            label = f"{d['business_name']} (bảng {item['table_business_name']})"
            candidates.append(
                GroundedCandidateDimension(
                    column_id=d["column_id"],
                    column_name=d["column_name"],
                    business_name=d["business_name"],
                    table_id=item["table_id"],
                    table_name=item["table_name"],
                    table_business_name=item["table_business_name"],
                    sample_values=d.get("sample_values", []),
                    hop_count=item["hops"],
                    label=label,
                )
            )
    return candidates[:limit]
