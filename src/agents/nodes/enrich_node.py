"""Enrich Node — Flow 1 Step 2.

Dùng LLM (via get_llm()) để phân tích raw_schema và sinh ra
business_name tiếng Việt + description chi tiết cho từng bảng và cột.
"""
from __future__ import annotations

from src.agents.state import AgentState
from src.services.llm import get_llm


async def enrich_node(state: AgentState) -> dict:
    """Call LLM to generate Vietnamese business names for each table/column.

    Input state fields: raw_schema
    Output state fields: enriched_schema | error
    """
    raw_schema = state.get("raw_schema", {})
    if not raw_schema:
        return {"error": "enrich_node: raw_schema is empty"}

    _llm = get_llm()
    # TODO: Implement steps:
    # 1. Build prompt từ raw_schema (yêu cầu output tiếng Việt)
    # 2. Gọi _llm.ainvoke(prompt) — async
    # 3. Parse JSON response ra enriched_schema
    # 4. Validate từng field business_name không rỗng
    return {
        "enriched_schema": {},
        "error": "enrich_node: not yet implemented",
    }
