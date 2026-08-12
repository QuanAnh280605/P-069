"""Generate canonical metric definitions without asking the LLM for SQL."""

from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp

from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem, MetricSuggestions
from src.services.llm import get_llm


def normalize_prompt(prompt: str) -> str:
    """Trim whitespace and validate prompt length."""
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty")
    if len(cleaned) > 2000:
        raise ValueError("Prompt exceeds maximum length of 2000 characters")
    return cleaned


def extract_schema_summary(schema_dict: dict[str, Any]) -> tuple[dict[str, set[str]], str]:
    """Build a valid-column index and readable schema prompt."""
    valid: dict[str, set[str]] = {}
    lines: list[str] = []
    for table_name, table in schema_dict.items():
        columns = table.get("columns", [])
        names = {column.get("column_name") or column.get("name") for column in columns}
        valid[table_name] = {name for name in names if name}
        lines.append(f"Entity `{table_name}`:")
        lines.extend(_format_columns(columns))
    return valid, "\n".join(lines)


def _format_columns(columns: list[dict[str, Any]]) -> list[str]:
    return [
        f"- `{column.get('column_name') or column.get('name')}` ({column.get('data_type', 'TEXT')})"
        for column in columns
        if column.get("column_name") or column.get("name")
    ]


def build_metric_system_prompt(schema_text: str) -> str:
    """Construct the structured-output prompt in Vietnamese."""
    return f"""Bạn là Data Analyst. Đề xuất 1-3 Business Metrics bằng tiếng Việt.
Chỉ trả về MetricDefinition JSON có metric.name, formula.function, formula.expression,
base_entity, filters, status=pending_approval, confidence, excluded_notes.
Không tạo SQL, sql_template, YAML, subquery hoặc tên cột không có trong schema.
formula.function chỉ dùng SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX.
formula.expression chỉ gồm cột của base_entity, số, ngoặc và + - * /.
Schema semantic:\n{schema_text}"""


async def _invoke_llm(prompt: str, schema_text: str) -> list[MetricDefinition]:
    llm = get_llm().with_structured_output(MetricSuggestions)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": build_metric_system_prompt(schema_text)},
            {"role": "user", "content": prompt},
        ]
    )
    if isinstance(response, MetricSuggestions):
        return response.metrics
    if isinstance(response, dict):
        return [MetricDefinition.model_validate(item) for item in response.get("metrics", [])]
    return []


def _references_schema(definition: MetricDefinition, valid: dict[str, set[str]]) -> bool:
    columns = valid.get(definition.metric.base_entity)
    if columns is None:
        return False
    parsed = sqlglot.parse_one(definition.metric.formula.expression)
    referenced = {column.name for column in parsed.find_all(exp.Column)}
    referenced.update(item.field for item in definition.metric.filters)
    return referenced.issubset(columns)


async def generate_metrics_from_prompt(
    prompt: str,
    dialect: str = "postgres",
    schema_dict: dict[str, Any] | None = None,
    schema_context: dict[str, Any] | None = None,
    target_tables: list[str] | None = None,
    max_retries: int = 1,
) -> list[MetricSuggestionItem]:
    """Generate validated metric definitions and YAML previews."""
    del dialect, max_retries
    schema = schema_dict or schema_context or {}
    if target_tables:
        schema = {name: value for name, value in schema.items() if name in target_tables}
    valid, schema_text = extract_schema_summary(schema)
    definitions = await _invoke_llm(normalize_prompt(prompt), schema_text)
    suggestions = [
        MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml())
        for item in definitions
        if _references_schema(item, valid)
    ]
    if not suggestions:
        raise ValueError("LLM failed to generate valid metric definitions")
    return suggestions[:3]
