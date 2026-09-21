"""Select a compact metric schema without another LLM completion."""

from __future__ import annotations

import re
from typing import Any

from src.services.semantic_concept_resolver import strip_accents


def select_metric_schema(
    schema: dict[str, Any],
    user_message: str,
    target_tables: list[str] | None = None,
    clarified_dims: list[str] | None = None,
    candidate_dims: list[dict[str, Any]] | None = None,
    max_tables: int = 2,
) -> dict[str, Any]:
    """Return target tables or the highest-scoring relationship-complete subset."""
    tables = schema.get("tables", [])
    if target_tables:
        selected = [table for table in tables if table.get("table_name") in set(target_tables)]
    elif len(tables) <= max_tables:
        selected = list(tables)
    else:
        selected = _rank_tables(tables, user_message, clarified_dims, candidate_dims, max_tables)
        _expand_reachable_neighbors(selected, tables, schema.get("relationships", []), max_tables + 1)
    return _selected_subgraph(selected, schema.get("relationships", []))


def _rank_tables(
    tables: list[dict[str, Any]],
    user_message: str,
    clarified_dims: list[str] | None,
    candidate_dims: list[dict[str, Any]] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Rank tables using enriched semantic metadata and grounded dimensions."""
    query_tokens = _extract_search_tokens(user_message, clarified_dims, candidate_dims)
    candidate_tables = {item.get("table_name") for item in (candidate_dims or []) if item.get("table_name")}
    scored = [(_score_table(table, query_tokens, candidate_tables), table) for table in tables]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [table for score, table in scored[:limit] if score > 0]
    return selected or [table for _, table in scored[:limit]]


def _selected_subgraph(selected: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep relationships whose endpoints both remain selected."""
    selected_names = {table.get("table_name") for table in selected}
    kept_relationships = [
        relation
        for relation in relationships
        if relation.get("from_table") in selected_names and relation.get("to_table") in selected_names
    ]
    return {"tables": selected, "relationships": kept_relationships}


def _extract_search_tokens(
    user_message: str,
    clarified_dims: list[str] | None,
    candidate_dims: list[dict[str, Any]] | None,
) -> set[str]:
    """Extract normalized query words from conversation context."""
    text = user_message.lower()
    if clarified_dims:
        text += " " + " ".join(dimension.lower() for dimension in clarified_dims)
    for item in candidate_dims or []:
        text += f" {item.get('column_name', '')} {item.get('business_name', '')} {item.get('table_name', '')}"
    raw = set(re.findall(r"\w+", strip_accents(text)))
    stop = {"tao", "metric", "tinh", "theo", "cho", "cac", "nhung", "voi", "mot", "va", "la", "cua", "trong", "tren"}
    return {token for token in raw if len(token) >= 2 and token not in stop}


def _score_table(table: dict[str, Any], query_tokens: set[str], candidate_tables: set[Any]) -> int:
    """Score a table by whole-word overlap with enriched metadata."""
    table_name = str(table.get("table_name", ""))
    score = 25 if table_name in candidate_tables else 0
    score += _overlap_score(query_tokens, table_name, table.get("business_name"), table.get("description"), 10)
    for column in table.get("columns", []):
        score += _overlap_score(
            query_tokens, column.get("column_name"), column.get("business_name"), column.get("description"), 5
        )
    return score


def _overlap_score(tokens: set[str], name: Any, business_name: Any, description: Any, weight: int) -> int:
    """Score technical name, business name, and description token overlap."""

    def words(value: Any) -> set[str]:
        return set(re.findall(r"\w+", strip_accents(str(value or ""))))

    return (
        len(tokens & words(name)) * weight
        + len(tokens & words(business_name)) * weight
        + len(tokens & words(description)) * max(weight // 2, 1)
    )


def _expand_reachable_neighbors(
    selected: list[dict[str, Any]],
    all_tables: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    limit: int,
) -> None:
    """Expand selected tables to direct relationship neighbors."""
    selected_names = {table.get("table_name") for table in selected}
    table_map = {table.get("table_name"): table for table in all_tables}
    for relation in relationships:
        if len(selected) >= limit:
            break
        from_table, to_table = relation.get("from_table"), relation.get("to_table")
        neighbor = to_table if from_table in selected_names else from_table if to_table in selected_names else None
        if neighbor not in selected_names and neighbor in table_map:
            selected.append(table_map[neighbor])
            selected_names.add(neighbor)
