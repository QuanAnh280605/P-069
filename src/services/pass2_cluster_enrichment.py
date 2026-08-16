"""Pass 2: Parallel Cluster Enrichment — enriches each cluster in parallel."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.services.enrichment_config import DEFAULT_CONFIG, EnrichmentConfig
from src.services.llm_caller import enrich_cluster_with_retry, execute_llm_request

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def table_key(t: dict[str, Any]) -> str:
    """Return composite key: 'schema.table' if schema_name exists, else table_name."""
    schema = t.get("schema_name")
    name = t["table_name"]
    return f"{schema}.{name}" if schema else name


def _title_case(name: str) -> str:
    """Convert snake_case or table name to Title Case."""
    return name.replace("_", " ").strip().title()


def _normalize_col(name: str) -> str:
    """Normalize column name for matching: lowercase, stripped."""
    return name.strip().lower()


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_cluster_prompt(
    cluster: list[dict[str, Any]],
    global_glossary: dict[str, dict],
    dialect: str,
    is_retry: bool = False,
) -> str:
    """Build Vietnamese prompt for a cluster with limited glossary scope.

    Includes:
    - Tables in current cluster from glossary
    - Hub tables that this cluster FKs to from glossary
    - Detailed table info (columns, FK, sample values)
    - Retry format hint if is_retry
    """
    # 1. Identify hub FK targets (tables outside cluster that cluster FKs to)
    cluster_table_names = {t["table_name"] for t in cluster}
    hub_fk_targets: set[str] = set()
    for t in cluster:
        for fk in t.get("foreign_keys", []):
            ref = fk["referred_table"]
            if ref not in cluster_table_names:
                hub_fk_targets.add(ref)

    # 2. Build glossary context section (limited scope)
    glossary_lines: list[str] = []
    for t in cluster:
        key = table_key(t)
        if key in global_glossary:
            g = global_glossary[key]
            glossary_lines.append(f"  - {key}: {g.get('business_name', '')} — {g.get('description', '')}")
    for hub_name in sorted(hub_fk_targets):
        if hub_name in global_glossary:
            g = global_glossary[hub_name]
            glossary_lines.append(
                f"  - {hub_name} (hub FK target): {g.get('business_name', '')} — {g.get('description', '')}"
            )

    glossary_section = ""
    if glossary_lines:
        glossary_section = (
            "## Ngữ cảnh từ bảng chú giải toàn cục (chỉ các bảng liên quan):\n" + "\n".join(glossary_lines) + "\n\n"
        )

    # 3. Build detailed table info
    table_sections: list[str] = []
    for t in cluster:
        tname = t["table_name"]
        lines = [f"### Bảng: {tname}"]
        cols = t.get("columns", [])
        if cols:
            lines.append("Cột:")
            for col in cols:
                col_line = f"  - {col['column_name']} ({col['data_type']})"
                if col.get("is_primary_key"):
                    col_line += " [PK]"
                if col.get("is_foreign_key"):
                    col_line += " [FK]"
                if col.get("sample_values"):
                    samples = ", ".join(str(v) for v in col["sample_values"][:5])
                    col_line += f" — mẫu: {samples}"
                lines.append(col_line)
        fks = t.get("foreign_keys", [])
        if fks:
            lines.append("Khóa ngoại:")
            for fk in fks:
                constrained = ", ".join(fk["constrained_columns"])
                referred = ", ".join(fk["referred_columns"])
                lines.append(f"  - ({constrained}) → {fk['referred_table']}({referred})")
        table_sections.append("\n".join(lines))

    # 4. Assemble prompt
    prompt_parts = [
        f"Đây là metadata của các bảng trong cụm (dialect: {dialect}):",
        "",
        glossary_section,
        "\n\n".join(table_sections),
        "",
        "Hãy trả về JSON object với cấu trúc:",
        json.dumps(
            {
                "matched_tables": ["tên_bảng"],
                "tables": {
                    "tên_bảng": {
                        "business_name": "tên nghiệp vụ tiếng Việt",
                        "description": "mô tả ngắn tiếng Việt",
                        "columns": [
                            {
                                "column_name": "tên_cột",
                                "business_name": "tên nghiệp vụ cột",
                                "description": "mô tả cột",
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "Chỉ trả về JSON, không giải thích.",
    ]

    if is_retry:
        prompt_parts.append("")
        prompt_parts.append(
            "LƯU Ý QUAN TRỌNG: Bạn PHẢI trả về JSON hợp lệ. "
            "Đảm bảo mọi bảng trong cụm đều có trong matched_tables và tables. "
            "Mọi cột trong metadata phải có trong columns array của bảng tương ứng."
        )

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def _normalize_llm_tables(parsed_llm_data: dict[str, Any]) -> dict[str, dict]:
    """Extract and normalize tables map from LLM parsed dict or list output."""
    raw = parsed_llm_data.get("tables", {})
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        return {item["table_name"]: item for item in raw if isinstance(item, dict) and "table_name" in item}
    return {}


def _merge_matched_table(t: dict[str, Any], llm_data: dict[str, Any]) -> dict[str, Any]:
    """Merge columns and metadata for a table matched in LLM response."""
    tname = t["table_name"]
    llm_cols_map = {
        _normalize_col(lc["column_name"]): lc
        for lc in llm_data.get("columns", [])
        if isinstance(lc, dict) and "column_name" in lc
    }
    merged_columns: list[dict[str, str]] = []
    for meta_col in t.get("columns", []):
        cname = meta_col["column_name"]
        norm = _normalize_col(cname)
        if norm in llm_cols_map:
            col_info = llm_cols_map[norm]
            merged_columns.append(
                {
                    "column_name": cname,
                    "business_name": col_info.get("business_name") or _title_case(cname),
                    "description": col_info.get("description", ""),
                }
            )
        else:
            merged_columns.append({"column_name": cname, "business_name": _title_case(cname), "description": ""})
    return {
        "business_name": llm_data.get("business_name") or _title_case(tname),
        "description": llm_data.get("description") or f"Bảng {tname}",
        "columns": merged_columns,
    }


def _fallback_table_entry(t: dict[str, Any], global_glossary: dict[str, dict]) -> dict[str, Any]:
    """Generate fallback entry using glossary and title-cased names."""
    key = table_key(t)
    tname = t["table_name"]
    entry = global_glossary.get(key) or global_glossary.get(tname)
    bname = entry.get("business_name") if entry else None
    desc = entry.get("description") if entry else None
    return {
        "business_name": bname or _title_case(tname),
        "description": desc or f"Bảng {tname}",
        "columns": [
            {
                "column_name": col["column_name"],
                "business_name": _title_case(col["column_name"]),
                "description": "",
            }
            for col in t.get("columns", [])
        ],
    }


def _merge_cluster_result(
    cluster: list[dict[str, Any]],
    parsed_llm_data: dict[str, Any],
    global_glossary: dict[str, dict],
) -> dict[str, dict]:
    """Merge LLM response with fallback for missing tables.

    Fallback priority:
    1. global_glossary[table_key] (business_name + description from Pass 1)
    2. Title-case fallback
    """
    llm_tables = _normalize_llm_tables(parsed_llm_data)
    result: dict[str, dict] = {}
    for t in cluster:
        key = table_key(t)
        tname = t["table_name"]
        if tname in llm_tables:
            result[key] = _merge_matched_table(t, llm_tables[tname])
        else:
            result[key] = _fallback_table_entry(t, global_glossary)
    return result


# ---------------------------------------------------------------------------
# Ultra-wide table handler
# ---------------------------------------------------------------------------


async def _handle_ultra_wide_table(
    table_meta: dict[str, Any],
    global_glossary: dict[str, dict],
    dialect: str,
    sem: asyncio.Semaphore,
    config: EnrichmentConfig,
) -> dict[str, Any]:
    """Handle table with > ultra_wide_threshold columns by splitting into chunks."""
    columns = table_meta.get("columns", [])
    chunk_size = config.ultra_wide_chunk_size
    chunks = [columns[i : i + chunk_size] for i in range(0, len(columns), chunk_size)]

    tname = table_meta["table_name"]
    key = table_key(table_meta)
    all_merged_columns: list[dict] = []
    llm_business_name: str | None = None
    llm_description: str | None = None

    async def _enrich_chunk(chunk: list[dict]) -> list[dict]:
        nonlocal llm_business_name, llm_description
        chunk_table = {
            **table_meta,
            "columns": chunk,
        }
        prompt = build_cluster_prompt([chunk_table], global_glossary, dialect)
        raw = await execute_llm_request(prompt, sem, config.llm_call_timeout_sec)
        from src.services.llm_caller import parse_llm_json

        parsed = parse_llm_json(raw)
        llm_tables = parsed.get("tables", {})
        if tname in llm_tables:
            llm_tbl = llm_tables[tname]
            if llm_business_name is None and llm_tbl.get("business_name"):
                llm_business_name = llm_tbl["business_name"]
            if llm_description is None and llm_tbl.get("description"):
                llm_description = llm_tbl["description"]
            llm_cols_map = {}
            for lc in llm_tables[tname].get("columns", []):
                llm_cols_map[_normalize_col(lc["column_name"])] = lc
            chunk_result = []
            for col in chunk:
                norm = _normalize_col(col["column_name"])
                if norm in llm_cols_map:
                    llm_col = llm_cols_map[norm]
                    chunk_result.append(
                        {
                            "column_name": col["column_name"],
                            "business_name": llm_col.get("business_name", _title_case(col["column_name"])),
                            "description": llm_col.get("description", ""),
                        }
                    )
                else:
                    chunk_result.append(
                        {
                            "column_name": col["column_name"],
                            "business_name": _title_case(col["column_name"]),
                            "description": "",
                        }
                    )
            return chunk_result
        # Fallback for chunk
        return [
            {
                "column_name": col["column_name"],
                "business_name": _title_case(col["column_name"]),
                "description": "",
            }
            for col in chunk
        ]

    results = await asyncio.gather(
        *[_enrich_chunk(chunk) for chunk in chunks],
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, BaseException):
            logger.warning("Ultra-wide chunk failed: %s", r)
        else:
            all_merged_columns.extend(r)

    # Get business_name / description: prefer LLM data from chunks, then glossary, then fallback
    glossary_entry = global_glossary.get(key) or global_glossary.get(tname)

    business_name = llm_business_name
    description = llm_description

    if business_name is None and glossary_entry:
        business_name = glossary_entry.get("business_name")
    if description is None and glossary_entry:
        description = glossary_entry.get("description")

    if business_name is None:
        business_name = _title_case(tname)
    if description is None:
        description = f"Bảng {tname}"

    return {
        "business_name": business_name,
        "description": description,
        "columns": all_merged_columns,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def enrich_clusters_parallel(
    clusters: list[list[dict[str, Any]]],
    global_glossary: dict[str, dict],
    dialect: str,
    sem: asyncio.Semaphore,
    config: EnrichmentConfig | None = None,
) -> dict[str, dict]:
    """Enrich all clusters in parallel using semaphore from caller.

    Returns flat dict keyed by composite key (schema.table or table_name).
    """
    if config is None:
        config = DEFAULT_CONFIG

    async def _enrich_one_cluster(cluster: list[dict[str, Any]]) -> dict[str, dict]:
        # Check for ultra-wide tables in cluster
        result: dict[str, dict] = {}
        normal_tables: list[dict[str, Any]] = []

        for t in cluster:
            if len(t.get("columns", [])) > config.ultra_wide_threshold:
                ultra_result = await _handle_ultra_wide_table(t, global_glossary, dialect, sem, config)
                result[table_key(t)] = ultra_result
            else:
                normal_tables.append(t)

        if normal_tables:
            parsed = await enrich_cluster_with_retry(
                build_cluster_prompt,
                normal_tables,
                global_glossary,
                dialect,
                sem,
                config,
            )
            merged = _merge_cluster_result(normal_tables, parsed, global_glossary)
            result.update(merged)

        return result

    all_results = await asyncio.gather(
        *[_enrich_one_cluster(c) for c in clusters],
        return_exceptions=True,
    )

    merged: dict[str, dict] = {}
    for r in all_results:
        if isinstance(r, BaseException):
            logger.warning("Cluster enrichment failed: %s", r)
        else:
            merged.update(r)

    return merged
