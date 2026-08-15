"""Generate canonical metric definitions from enriched semantic metadata."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem, MetricSuggestions
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json
from src.services.metrics import (
    _parse_metric_payload,
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
        _, schema_text = extract_schema_summary(schema)
        sys_prompt = build_metric_system_prompt(schema_text)
        user_msg = state.get("user_message", "").strip()
        messages = [
            ("system", sys_prompt),
            ("user", user_msg if user_msg else "Hãy đề xuất 3 metric quan trọng nhất từ schema trên."),
        ]
        definitions = await _generate_definitions_with_fallback(messages)

        # Format the response as MetricSuggestionItem to match the frontend expectations
        results = [
            MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()).model_dump(mode="json")
            for item in definitions
        ]
        return {"suggested_metrics": results}
    except Exception as exc:
        logger.warning("Metric definition generation failed: %s", exc)
        return {"error": f"on_demand_metric_suggest_node: {exc}"}


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
