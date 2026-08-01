"""Metric Suggest Node — Flow 1 Step 3.

Dùng LLM (via get_llm()) để phân tích enriched_schema và đề xuất
Business Metrics kèm SQL template tham chiếu (không thực thi SQL).
"""
from __future__ import annotations

from src.agents.state import AgentState
from src.services.llm import get_llm


async def metric_suggest_node(state: AgentState) -> dict:
    """Call LLM to propose Business Metrics based on enriched schema.

    Input state fields: enriched_schema
    Output state fields: suggested_metrics | error

    Note: LangGraph Interrupt (HITL) is triggered after this node.
    """
    enriched_schema = state.get("enriched_schema", {})
    if not enriched_schema:
        return {"error": "metric_suggest_node: enriched_schema is empty"}

    _llm = get_llm()
    # TODO: Implement steps:
    # 1. Build prompt yêu cầu LLM đề xuất 2-5 business metrics
    # 2. Gọi _llm.ainvoke(prompt) — async
    # 3. Parse JSON list: [{name, description, sql_template}, ...]
    # 4. Validate sql_template chỉ chứa SELECT (không INSERT/UPDATE/DELETE)
    return {
        "suggested_metrics": [],
        "error": "metric_suggest_node: not yet implemented",
    }
