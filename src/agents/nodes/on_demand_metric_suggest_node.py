"""On-demand metric suggestion node delegating to the dedupe-aware service."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.models.schemas import MetricSuggestionItem
from src.services.metric_dedupe import format_existing_metrics_context, merge_dedupe
from src.services.metrics import (
    build_metric_system_prompt,
    extract_schema_summary,
    generate_definitions_v2,
    validate_metric_definitions,
)

logger = logging.getLogger(__name__)

_DEFAULT_USER_PROMPT = "Hãy đề xuất 3 metric quan trọng nhất từ schema trên."


async def on_demand_metric_suggest_node(state: AgentState) -> dict[str, Any]:
    """Generate dedupe-aware metric definitions from enriched schema."""
    schema = state.get("enriched_schema")
    if not schema:
        return {"error": "on_demand_metric_suggest_node: enriched_schema is empty"}
    try:
        return await _generate(state, schema)
    except Exception as exc:
        logger.warning("Metric definition generation failed: %s", exc)
        return {"error": f"on_demand_metric_suggest_node: {exc}"}


async def _generate(state: AgentState, schema: dict[str, Any]) -> dict[str, Any]:
    """Run generation + validation + dedupe and build the node result."""
    existing = state.get("existing_metrics") or []
    _, schema_text = extract_schema_summary(schema)
    existing_text = format_existing_metrics_context(existing) if existing else None
    messages = [
        ("system", build_metric_system_prompt(schema_text, existing_text)),
        ("user", _user_message(state)),
    ]
    definitions, llm_duplicates, llm_conflicts = await generate_definitions_v2(messages, use_v2=bool(existing))
    valid = validate_metric_definitions(definitions, "postgres", schema)
    items = [MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()) for item in valid]
    kept, notices = merge_dedupe(items, llm_duplicates, llm_conflicts, existing)
    return {
        "suggested_metrics": [item.model_dump(mode="json") for item in kept],
        "duplicate_notices": [notice.model_dump() for notice in notices],
        "dedupe_performed": state.get("dedupe_performed", True),
    }


def _user_message(state: AgentState) -> str:
    """Combine bounded chat history with the latest request for generation."""
    history = _format_history(state.get("chat_history", []))
    current = state.get("user_message", "").strip() or _DEFAULT_USER_PROMPT
    return f"Lịch sử liên quan:\n{history}\n\nYêu cầu mới nhất:\n{current}"


def _format_history(history: list[dict[str, str]]) -> str:
    """Format bounded prior conversation context for metric generation."""
    lines = []
    for item in history[-6:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            lines.append(f"{item['role']}: {item['content'][:1200]}")
    return "\n".join(lines) or "(không có)"
