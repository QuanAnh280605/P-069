"""Enrich Node — Flow 1 Step 2.

Dùng LLM (via get_llm()) để phân tích raw_schema và sinh ra
business_name tiếng Việt + description chi tiết cho từng bảng và cột.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)


def _build_enrich_prompt(raw_schema: dict[str, Any]) -> str:
    """Build prompt string instructing LLM to generate Vietnamese business metadata."""
    tables_summary = []
    for tbl in raw_schema.get("tables", []):
        t_name = tbl.get("table_name", "")
        cols = [f"- {c.get('column_name')} ({c.get('data_type')})" for c in tbl.get("columns", [])]
        tables_summary.append(f"Bảng `{t_name}`:\n" + "\n".join(cols))

    schema_text = "\n\n".join(tables_summary)
    return (
        "Bạn là chuyên gia phân tích dữ liệu nghiệp vụ (Business Analyst).\n"
        "Hãy phân tích cấu trúc kỹ thuật của các bảng và cột dưới đây, sau đó sinh ra tên nghiệp vụ "
        "(business_name tiếng Việt có nghĩa) và mô tả chi tiết (description) cho từng bảng và từng cột.\n\n"
        f"### CẤU TRÚC DATABASE:\n{schema_text}\n\n"
        "### YÊU CẦU ĐẦU RA:\n"
        "Trả về định dạng JSON thuần túy (không kèm markdown format ngoài JSON) có cấu trúc:\n"
        "{\n"
        '  "tables": [\n'
        "    {\n"
        '      "table_name": "tên_bảng_kỹ_thuật",\n'
        '      "business_name": "Tên Nghiệp Vụ Tiếng Việt",\n'
        '      "description": "Mô tả chi tiết ý nghĩa kinh doanh của bảng",\n'
        '      "columns": [\n'
        "        {\n"
        '          "column_name": "tên_cột_kỹ_thuật",\n'
        '          "business_name": "Tên Nghiệp Vụ Cột Tiếng Việt",\n'
        '          "description": "Mô tả chi tiết ý nghĩa cột"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )


def _parse_enrich_response(raw_response: str, raw_schema: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON LLM output and merge with raw schema structure."""
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "tables" in parsed:
            return parsed
    except json.JSONDecodeError:
        logger.warning("enrich_node: Failed to parse JSON response from LLM")

    # Fallback structure if JSON parse fails
    fallback_tables = []
    for tbl in raw_schema.get("tables", []):
        t_name = tbl.get("table_name", "")
        cols = [
            {
                "column_name": c.get("column_name", ""),
                "business_name": c.get("column_name", "").replace("_", " ").title(),
                "description": f"Cột {c.get('column_name')}",
            }
            for c in tbl.get("columns", [])
        ]
        fallback_tables.append({
            "table_name": t_name,
            "business_name": t_name.replace("_", " ").title(),
            "description": f"Bảng {t_name}",
            "columns": cols,
        })
    return {"tables": fallback_tables}


async def enrich_node(state: AgentState) -> dict[str, Any]:
    """Call LLM to generate Vietnamese business names for each table/column.

    Input state fields: raw_schema
    Output state fields: enriched_schema | error
    """
    raw_schema = state.get("raw_schema", {})
    if not raw_schema or not raw_schema.get("tables"):
        return {"error": "enrich_node: raw_schema is empty"}

    try:
        prompt = _build_enrich_prompt(raw_schema)
        llm = get_llm()
        response = await llm.ainvoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)

        enriched = _parse_enrich_response(raw_text, raw_schema)
        logger.info("enrich_node: successfully enriched %d tables", len(enriched.get("tables", [])))
        return {"enriched_schema": enriched}
    except Exception as exc:
        logger.error("enrich_node error: %s", exc)
        return {"error": f"enrich_node: {exc}"}

