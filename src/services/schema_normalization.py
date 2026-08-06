"""Pure helpers for producing deterministic raw-schema metadata."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from src.models.raw_schema import (
    ColumnReference,
    ForeignKeyMetadata,
    RelationshipMetadata,
)


def utc_timestamp() -> str:
    """Return the current UTC timestamp in JSON-compatible ISO-8601."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_data_type(value: object) -> str:
    """Normalize type casing and parameter whitespace without remapping types."""
    normalized = " ".join(str(value).strip().lower().split())
    return re.sub(r"\s*,\s*", ",", normalized)


def build_fk_links(
    from_table: str,
    default_schema: str | None,
    foreign_key: ForeignKeyMetadata,
) -> tuple[dict[str, ColumnReference], list[RelationshipMetadata]]:
    """Build per-column references and relationships for one constraint."""
    references: dict[str, ColumnReference] = {}
    relationships: list[RelationshipMetadata] = []
    target_schema = foreign_key["referred_schema"] or default_schema
    pairs = zip(foreign_key["constrained_columns"], foreign_key["referred_columns"], strict=True)
    for source_column, target_column in pairs:
        references[source_column] = _reference(foreign_key, target_schema, target_column)
        relationships.append(_relationship(from_table, source_column, foreign_key))
    return references, relationships


def _reference(
    foreign_key: ForeignKeyMetadata,
    schema: str | None,
    column: str,
) -> ColumnReference:
    return {"table": foreign_key["referred_table"], "column": column, "schema": schema}


def _relationship(
    from_table: str,
    from_column: str,
    foreign_key: ForeignKeyMetadata,
) -> RelationshipMetadata:
    target_column = foreign_key["referred_columns"][foreign_key["constrained_columns"].index(from_column)]
    return {
        "from_table": from_table,
        "from_column": from_column,
        "to_table": foreign_key["referred_table"],
        "to_column": target_column,
        "relationship_type": "many_to_one",
    }
