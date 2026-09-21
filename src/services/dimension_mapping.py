"""Deterministically map technical dimension keys to display columns."""

from __future__ import annotations

import re
from typing import Any

_KEY_SUFFIX_RE = re.compile(r"_(?:id|code|key)$", re.IGNORECASE)
_DISPLAY_SUFFIX_RE = re.compile(r"_(?:name|title|label)$", re.IGNORECASE)


def normalize_dimension_references(
    dimensions: list[str],
    base_entity: str,
    candidates: list[dict[str, Any]],
) -> list[str]:
    """Replace technical ID/code/key dimensions with grounded display columns."""
    return [_map_dimension_reference(item, base_entity, candidates) for item in dimensions]


def dimension_candidates_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract name-like, non-key display columns from supported schema shapes."""
    candidates: list[dict[str, Any]] = []
    for table_name, table in _schema_tables(schema):
        for column in table.get("columns", []):
            if not isinstance(column, dict) or not _is_display_column(column):
                continue
            candidates.append(
                {
                    "table_name": table_name,
                    "column_name": column.get("column_name") or column.get("name"),
                    "business_name": column.get("business_name"),
                }
            )
    return candidates


def _schema_tables(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    tables = schema.get("tables")
    if isinstance(tables, list):
        return [
            (str(item.get("table_name") or item.get("name") or ""), item) for item in tables if isinstance(item, dict)
        ]
    if isinstance(tables, dict):
        return [(str(name), item) for name, item in tables.items() if isinstance(item, dict)]
    return [(str(name), item) for name, item in schema.items() if isinstance(item, dict) and "columns" in item]


def _is_display_column(column: dict[str, Any]) -> bool:
    if column.get("is_primary_key") or column.get("is_foreign_key"):
        return False
    name = str(column.get("column_name") or column.get("name") or "").lower()
    business_name = str(column.get("business_name") or "").lower()
    return name == "name" or bool(_DISPLAY_SUFFIX_RE.search(name)) or "name" in business_name or "tên" in business_name


def _map_dimension_reference(
    dimension: str,
    base_entity: str,
    candidates: list[dict[str, Any]],
) -> str:
    entity = _key_entity(dimension)
    if not entity:
        return dimension
    matches = [(_candidate_score(item, entity), item) for item in candidates]
    matches = [item for item in matches if item[0] > 0]
    if not matches:
        return dimension
    candidate = max(matches, key=lambda item: item[0])[1]
    table = str(candidate.get("table_name") or "").strip()
    column = str(candidate.get("column_name") or "").strip()
    return f"{table}.{column}" if table and table != base_entity else column


def _key_entity(dimension: str) -> str | None:
    value = dimension.strip().lower()
    leaf = value.rsplit(".", 1)[-1]
    if leaf == "id" and "." in value:
        return _canonical_entity(value.rsplit(".", 1)[0])
    if not _KEY_SUFFIX_RE.search(leaf):
        return None
    return _canonical_entity(_KEY_SUFFIX_RE.sub("", leaf))


def _canonical_entity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if normalized.startswith("dim_"):
        normalized = normalized[4:]
    if normalized.endswith("ies"):
        return f"{normalized[:-3]}y"
    return normalized[:-1] if normalized.endswith("s") else normalized


def _candidate_score(candidate: dict[str, Any], entity: str) -> int:
    table = _canonical_entity(str(candidate.get("table_name") or ""))
    column = str(candidate.get("column_name") or "").lower()
    column_entity = _canonical_entity(_DISPLAY_SUFFIX_RE.sub("", column))
    score = 100 if table == entity else 0
    if column_entity == entity:
        score += 40 if score else 80
    if score == 0 and entity in {part for part in table.split("_") if part}:
        score = 50
    if score > 0 and (column == "name" or column.endswith("_name")):
        score += 20
    return score - int(candidate.get("hop_count") or 0) if score > 0 else 0
