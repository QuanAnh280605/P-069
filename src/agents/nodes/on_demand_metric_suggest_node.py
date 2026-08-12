"""Generate canonical metric definitions from enriched semantic metadata."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestions
from src.services.llm import get_llm
from src.services.metrics import (
    _extract_json_from_text,
    _parse_metric_payload,
    build_metric_system_prompt,
)

logger = logging.getLogger(__name__)


async def on_demand_metric_suggest_node(state: AgentState) -> dict[str, Any]:
    """Generate metric definitions from enriched schema without generating SQL."""
    schema = state.get("enriched_schema")
    if not schema:
        return {"error": "on_demand_metric_suggest_node: enriched_schema is empty"}
    try:
        schema_text = _format_schema_for_prompt(schema)
        sys_prompt = build_metric_system_prompt(schema_text)
        definitions = await _generate_definitions_with_fallback(sys_prompt)
        return {"suggested_metrics": [item.model_dump(mode="json") for item in definitions]}
    except Exception as exc:
        logger.warning("Metric definition generation failed: %s", exc)
        return {"error": f"on_demand_metric_suggest_node: {exc}"}


async def _generate_definitions_with_fallback(prompt: str) -> list[MetricDefinition]:
    """Try structured output first, then fallback to text parsing."""
    raw_llm = get_llm()
    try:
        structured = raw_llm.with_structured_output(MetricSuggestions)
        response = await structured.ainvoke(prompt)
        definitions = _parse_metric_payload(response)
        if definitions:
            return definitions
    except Exception as exc:
        logger.info("Structured output fallback in node: %s", exc)

    resp = await raw_llm.ainvoke(prompt)
    raw_text = resp.content if hasattr(resp, "content") else str(resp)
    parsed = _extract_json_from_text(raw_text)
    return _parse_metric_payload(parsed)


def _format_schema_for_prompt(schema: dict[str, Any]) -> str:
    """Format enriched tables and columns for structured generation."""
    lines: list[str] = []
    for table in schema.get("tables", []):
        table_name = _resolve_name(table, "table_name")
        lines.append(f"Entity `{table_name}`:")
        for column in table.get("columns", []):
            name = _resolve_name(column, "column_name")
            lines.append(f"- `{name}` ({column.get('data_type', 'TEXT')})")
    return "\n".join(lines)


def _resolve_name(value: dict[str, Any], key: str) -> str:
    """Resolve flat or Identifier-shaped names."""
    name = value.get(key) or value.get("name", "unknown")
    if isinstance(name, dict):
        return str(name.get("raw_name") or name.get("normalized_name", "unknown"))
    return str(name)
