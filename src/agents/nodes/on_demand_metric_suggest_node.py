"""Generate canonical metric definitions from enriched semantic metadata."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem, MetricSuggestions
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json
from src.services.metric_dedupe import format_existing_metrics_context, merge_dedupe
from src.services.metrics import (
    _parse_metric_payload,
    _references_schema,
    build_metric_system_prompt,
    extract_schema_summary,
)

logger = logging.getLogger(__name__)


async def on_demand_metric_suggest_node(state: AgentState) -> dict[str, Any]:
    """Generate metric definitions from enriched schema without generating SQL."""
    schema = state.get("enriched_schema")
    if not schema:
        return {"error": "on_demand_metric_suggest_node: enriched_schema is empty"}
    try:
        valid_columns, schema_text = extract_schema_summary(schema)
        decision = state.get("metric_decision", {})
        existing = state.get("existing_metrics") or []
        existing_text = format_existing_metrics_context(existing) if existing else None
        sys_prompt = build_metric_system_prompt(schema_text, existing_text, requested_metric=True)
        user_msg = state.get("user_message", "").strip()
        history = _format_history(state.get("chat_history", []))
        current = user_msg if user_msg else "Hãy đề xuất 3 metric quan trọng nhất từ schema trên."
        messages = _metric_messages(sys_prompt, history, current, decision)
        definitions = await _generate_definitions_with_fallback(messages)
        definitions = _valid_definitions(definitions, valid_columns, decision)
        if not definitions:
            raise ValueError("LLM failed to generate a schema-valid metric definition")

        # Format the response as MetricSuggestionItem to match the frontend expectations
        items = [
            MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()).model_dump(mode="json")
            for item in definitions
        ]
        suggestions = [MetricSuggestionItem.model_validate(item) for item in items]
        kept, notices = merge_dedupe(suggestions, [], [], existing)
        action = "save_metric" if state.get("can_generate_metrics", False) else "submit_metric_request"
        return {
            "intent": "metric_query",
            "suggested_metrics": [item.model_dump(mode="json") for item in kept[:1]],
            "duplicate_notices": [notice.model_dump() for notice in notices],
            "dedupe_performed": state.get("dedupe_performed", True),
            "suggestion_action": action,
        }
    except Exception as exc:
        logger.warning("Metric definition generation failed: %s", exc)
        return {"error": f"on_demand_metric_suggest_node: {exc}"}


def _metric_messages(sys_prompt: str, history: str, current: str, decision: dict[str, Any]) -> list[tuple[str, str]]:
    """Build a bounded request that carries unresolved business assumptions."""
    assumptions = decision.get("assumptions", [])
    assumption_text = "\n".join(f"- {item}" for item in assumptions) or "(không có)"
    content = (
        f"Lịch sử liên quan:\n{history}\n\nYêu cầu mới nhất:\n{current}\n\nGiả định cần xác nhận:\n{assumption_text}"
    )
    return [("system", sys_prompt), ("user", content)]


def _valid_definitions(
    definitions: list[MetricDefinition], valid_columns: dict[str, set[str]], decision: dict[str, Any]
) -> list[MetricDefinition]:
    """Keep schema-valid definitions and make unresolved assumptions explicit."""
    valid = [item for item in definitions if _references_schema(item, valid_columns)]
    assumptions = [str(item).strip() for item in decision.get("assumptions", []) if str(item).strip()]
    for item in valid:
        _apply_assumptions(item, assumptions)
    return valid[:1]


def _apply_assumptions(definition: MetricDefinition, assumptions: list[str]) -> None:
    """Lower confidence without allowing the LLM to silently infer business rules."""
    if not assumptions:
        return
    note = "Giả định cần xác nhận: " + "; ".join(assumptions)
    existing = definition.metric.excluded_notes.strip()
    definition.metric.excluded_notes = f"{existing}\n{note}".strip()
    definition.metric.confidence = "low"


async def _generate_definitions_with_fallback(prompt: Any) -> list[MetricDefinition]:
    """Try structured output first, then fallback to text parsing."""
    raw_llm = get_llm(role="metric")
    try:
        structured = raw_llm.with_structured_output(MetricSuggestions)
        response = await structured.ainvoke(prompt)
        definitions = _parse_metric_payload(response)
        if definitions:
            return definitions
    except Exception as exc:
        logger.info("Structured output fallback in node: %s", exc)

    parsed = await ainvoke_json(raw_llm, prompt)
    return _parse_metric_payload(parsed)


def _format_history(history: list[dict[str, str]]) -> str:
    """Format bounded prior conversation context for metric generation."""
    lines = []
    for item in history[-6:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            lines.append(f"{item['role']}: {item['content'][:1200]}")
    return "\n".join(lines) or "(không có)"
