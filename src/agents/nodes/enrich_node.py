"""Enrich Node — Flow 1 Step 2.

Two-Pass Semantic Enrichment pipeline:
  Pass 1 — Global table glossary (business_name + description for all tables)
  Pass 2 — Parallel cluster enrichment (detailed column-level metadata)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agents.state import AgentState
from src.services.clustering import cluster_tables, table_key
from src.services.enrichment_config import DEFAULT_CONFIG
from src.services.pass1_global_glossary import execute_pass1
from src.services.pass2_cluster_enrichment import enrich_clusters_parallel

logger = logging.getLogger(__name__)


def _title_case(name: str) -> str:
    """Convert snake_case or table name to Title Case."""
    return name.replace("_", " ").strip().title()


def _build_fallback_columns(columns: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build fallback column items with Title Case names."""
    return [
        {
            "column_name": col["column_name"],
            "business_name": _title_case(col["column_name"]),
            "description": "",
        }
        for col in columns
    ]


def _build_fallback_table(
    table_meta: dict[str, Any],
    glossary_entry: dict[str, Any],
) -> dict[str, Any]:
    """Build fallback table metadata entry from glossary or table name."""
    t_name = table_meta["table_name"]
    return {
        "table_name": t_name,
        "business_name": glossary_entry.get("business_name") or _title_case(t_name),
        "description": glossary_entry.get("description") or f"Bảng {t_name}",
        "columns": _build_fallback_columns(table_meta.get("columns", [])),
    }


def _assemble_enriched_tables(
    tables: list[dict[str, Any]],
    enriched_tables_dict: dict[str, Any],
    global_glossary: dict[str, Any],
) -> list[dict[str, Any]]:
    """Combine Pass 2 enrichment with fallback entries for missing tables."""
    enriched_list: list[dict[str, Any]] = []
    for table_meta in tables:
        t_key = table_key(table_meta)
        if t_key in enriched_tables_dict:
            enriched_list.append(enriched_tables_dict[t_key])
        else:
            glossary_entry = global_glossary.get(t_key, {})
            enriched_list.append(_build_fallback_table(table_meta, glossary_entry))
    return enriched_list


async def enrich_node(state: AgentState) -> dict[str, Any]:
    """Two-Pass enrichment: Pass 1 global glossary + Pass 2 cluster enrichment.

    Input state fields: raw_schema, db_type
    Output state fields: enriched_schema, global_glossary | error
    """
    raw_schema = state.get("raw_schema", {})
    if not raw_schema or not raw_schema.get("tables"):
        return {"error": "enrich_node: raw_schema is empty"}

    try:
        tables = raw_schema["tables"]
        dialect = state.get("db_type", "postgresql")
        sem = asyncio.Semaphore(DEFAULT_CONFIG.max_concurrency)

        global_glossary = await execute_pass1(tables, dialect, sem)
        clusters = cluster_tables(tables)
        enriched_dict = await enrich_clusters_parallel(
            clusters,
            global_glossary,
            dialect,
            sem,
        )

        enriched_list = _assemble_enriched_tables(tables, enriched_dict, global_glossary)
        logger.info("enrich_node: successfully enriched %d tables", len(enriched_list))
        return {
            "enriched_schema": {"tables": enriched_list},
            "global_glossary": global_glossary,
        }
    except Exception as exc:
        logger.error("enrich_node error: %s", exc)
        return {"error": f"enrich_node: {exc}"}
