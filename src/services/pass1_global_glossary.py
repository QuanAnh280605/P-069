"""Pass 1: Global Table Glossary — generates business_name + description for ALL tables."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.services.enrichment_config import DEFAULT_CONFIG, EnrichmentConfig
from src.services.llm import get_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def table_key(t: dict[str, Any]) -> str:
    """Return composite key: 'schema.table' if schema_name exists, else table_name."""
    schema = t.get("schema_name")
    name = t["table_name"]
    return f"{schema}.{name}" if schema else name


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM response text."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _title_case(name: str) -> str:
    """Convert snake_case or table name to Title Case."""
    return name.replace("_", " ").strip().title()


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def build_pass1_prompt(table_names: list[str], dialect: str) -> str:
    """Build prompt asking LLM to return business_name + description for all tables."""
    table_list = ", ".join(f'"{n}"' for n in table_names)
    return (
        f"Đây là danh sách tên bảng trong cơ sở dữ liệu (dialect: {dialect}): "
        f"[{table_list}].\n\n"
        'Hãy trả về JSON object (flat, không có wrapper key "tables") '
        "trong đó mỗi key là tên bảng, value là object gồm:\n"
        '  - "business_name": tên nghiệp vụ tiếng Việt ngắn gọn\n'
        '  - "description": mô tả ngắn bằng tiếng Việt về bảng đó\n\n'
        'Ví dụ: {"orders": {"business_name": "Đơn hàng", '
        '"description": "Bảng lưu trữ thông tin đơn hàng"}}\n\n'
        "Chỉ trả về JSON, không giải thích."
    )


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def _fallback_glossary(tables: list[dict[str, Any]]) -> dict[str, dict]:
    """Build fallback glossary when LLM fails."""
    result: dict[str, dict] = {}
    for t in tables:
        key = table_key(t)
        name = t["table_name"]
        result[key] = {
            "business_name": _title_case(name),
            "description": f"Bảng {name}",
        }
    return result


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_glossaries(glossaries: list[dict[str, dict]]) -> dict[str, dict]:
    """Merge multiple glossary batches into one flat dict."""
    merged: dict[str, dict] = {}
    for g in glossaries:
        merged.update(g)
    return merged


# ---------------------------------------------------------------------------
# Execute Pass 1
# ---------------------------------------------------------------------------


async def execute_pass1(
    tables: list[dict[str, Any]],
    dialect: str,
    sem: asyncio.Semaphore,
    config: EnrichmentConfig | None = None,
) -> dict[str, dict]:
    """Generate global table glossary (business_name + description) for all tables."""
    cfg = config or DEFAULT_CONFIG
    llm = get_llm()
    table_names = [t["table_name"] for t in tables]

    async def _call_llm(names: list[str]) -> dict[str, dict]:
        prompt = build_pass1_prompt(names, dialect)
        async with sem:
            resp = await llm.ainvoke(prompt)
        parsed = _parse_llm_json(resp.content)
        # Map LLM response keys to composite keys
        result: dict[str, dict] = {}
        for t in tables:
            tname = t["table_name"]
            if tname in parsed:
                result[table_key(t)] = parsed[tname]
        return result

    try:
        if len(tables) <= cfg.pass1_single_prompt_threshold:
            return await _call_llm(table_names)
        # Batch mode
        batch_size = cfg.pass1_batch_size
        batches = [table_names[i : i + batch_size] for i in range(0, len(table_names), batch_size)]
        results = await asyncio.gather(
            *[_call_llm(batch) for batch in batches],
            return_exceptions=True,
        )
        valid: list[dict[str, dict]] = []
        for r in results:
            if isinstance(r, BaseException):
                logger.warning("Batch failed: %s", r)
            else:
                valid.append(r)
        if not valid:
            return _fallback_glossary(tables)
        return merge_glossaries(valid)
    except Exception:
        logger.exception("Pass 1 failed, using fallback")
        return _fallback_glossary(tables)
