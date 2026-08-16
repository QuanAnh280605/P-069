"""Generate canonical metric definitions without asking the LLM for SQL."""

from __future__ import annotations

import logging
from typing import Any

import sqlglot
from sqlglot import exp

from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem, MetricSuggestions
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json, extract_json

logger = logging.getLogger(__name__)


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
    tables_data = schema_dict.get("tables", schema_dict)
    if isinstance(tables_data, list):
        items = [(t.get("table_name") or t.get("name", ""), t) for t in tables_data if isinstance(t, dict)]
    elif isinstance(tables_data, dict):
        items = list(tables_data.items())
    else:
        items = []
    for table_name, table in items:
        if not isinstance(table, dict):
            continue
        t_name = table.get("table_name") or table.get("name") or table_name or "unknown"
        columns = table.get("columns", [])
        names = {col.get("column_name") or col.get("name") for col in columns if isinstance(col, dict)}
        valid[t_name] = {name for name in names if name}
        business_name = table.get("business_name") or t_name
        description = table.get("description") or ""
        lines.append(f"Entity `{t_name}` ({business_name}): {description}")
        lines.extend(_format_columns(columns))
    return valid, "\n".join(lines)


def _format_columns(columns: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for column in columns:
        name = column.get("column_name") or column.get("name")
        if not name:
            continue
        flags = [
            label
            for enabled, label in (
                (column.get("is_primary_key"), "PK/grain"),
                (column.get("is_foreign_key"), "FK"),
                (column.get("is_nullable"), "nullable"),
            )
            if enabled
        ]
        business = column.get("business_name") or name
        desc = (column.get("description") or "").strip()
        desc_str = f" — {desc}" if desc and desc.lower() != business.lower() else ""
        suffix = f"; {', '.join(flags)}" if flags else ""
        default_val = column.get("default_value")
        if default_val is not None:
            suffix += f"; default: {default_val}"
        sample_vals = column.get("sample_values") or column.get("allowed_values")
        if sample_vals:
            suffix += f"; values: {sample_vals}"
        lines.append(f"- `{name}` ({column.get('data_type', 'TEXT')}; {business}{desc_str}{suffix})")
    return lines


def build_metric_system_prompt(schema_text: str) -> str:
    """Construct the structured-output prompt in Vietnamese."""
    return f"""Bạn là chuyên gia phân tích dữ liệu (Data Analyst).
Nhiệm vụ: Đề xuất 1-3 Business Metrics bằng tiếng Việt dựa trên schema cơ sở dữ liệu.

Trả về kết quả ở định dạng JSON thuần túy có cấu trúc như sau:
{{
  "metrics": [
    {{
      "metric": {{
        "name": "Tên metric tiếng Việt",
        "formula": {{
          "function": "SUM",
          "expression": "cột_tính_toán"
        }},
        "base_entity": "tên_bảng_chính",
        "filters": [],
        "status": "pending_approval",
        "confidence": "high",
        "excluded_notes": "Ghi chú nếu có"
      }}
    }}
  ]
}}

Quy tắc BẮT BUỘC:
1. formula.function chỉ dùng: SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX.
2. formula.expression chỉ gồm cột của base_entity, số và các toán tử (+, -, *, /). Không viết SQL, subquery, alias.
3. base_entity và các cột phải tồn tại chính xác trong Schema dưới đây.
4. Ưu tiên base_entity có PK/grain rõ ràng; không giả định quan hệ hoặc ý nghĩa không có trong schema.
5. Filter chỉ dùng cột của base_entity và giá trị được người dùng nêu rõ hoặc có ý nghĩa chắc chắn.
6. Khi dùng filter trên cột có values: [...] trong Schema, PHẢI dùng đúng 1 giá trị trong danh sách values. Không tự tạo giá trị mới.
7. Với các cột cờ nhị phân (is_*, has_*, flag) kiểu VARCHAR(1)/CHAR(1)/INT mà KHÔNG có danh sách values trong schema: mặc định dùng giá trị "1" cho trạng thái Hoàn thành / Kích hoạt / Bật, và "0" cho Chưa xong / Tắt. TUYỆT ĐỐI KHÔNG tự bịa ra 'Y', 'N', 'TRUE', 'true'.

Schema database:
{schema_text}"""


def _extract_json_from_text(text: str) -> Any:
    """Extract JSON object or array from LLM response text."""
    return extract_json(text)


def _parse_metric_payload(payload: Any) -> list[MetricDefinition]:
    """Parse various dictionary or list shapes into MetricDefinition list."""
    if isinstance(payload, MetricSuggestions):
        return payload.metrics
    items: list[Any] = []
    if isinstance(payload, dict):
        if "metrics" in payload and isinstance(payload["metrics"], list):
            items = payload["metrics"]
        elif "metric" in payload or "name" in payload:
            items = [payload]
    elif isinstance(payload, list):
        items = payload

    definitions: list[MetricDefinition] = []
    for item in items:
        try:
            definitions.append(MetricDefinition.model_validate(item))
        except Exception as exc:
            logger.debug("Failed to validate metric item: %s (%s)", item, exc)
    return definitions


async def _invoke_llm(prompt: str, schema_text: str) -> list[MetricDefinition]:
    """Invoke LLM with structured output or fallback to raw text parsing."""
    sys_prompt = build_metric_system_prompt(schema_text)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    raw_llm = get_llm(role="metric")
    try:
        structured = raw_llm.with_structured_output(MetricSuggestions)
        response = await structured.ainvoke(messages)
        definitions = _parse_metric_payload(response)
        if definitions:
            return definitions
    except Exception as exc:
        logger.info("Structured output fallback triggered: %s", exc)

    try:
        parsed = await ainvoke_json(raw_llm, messages)
        return _parse_metric_payload(parsed)
    except Exception as exc:
        logger.error("LLM metric extraction failed: %s", exc)
        return []


def _references_schema(definition: MetricDefinition, valid: dict[str, set[str]]) -> bool:
    """Check if the metric formula and filters reference existing schema tables and columns."""
    valid_lower = {k.lower(): (k, v) for k, v in valid.items()}
    entity_key = definition.metric.base_entity.strip().lower()
    if entity_key not in valid_lower:
        return False
    actual_table_name, columns = valid_lower[entity_key]
    definition.metric.base_entity = actual_table_name
    col_lower = {c.lower(): c for c in columns}
    try:
        parsed = sqlglot.parse_one(definition.metric.formula.expression)
        referenced = {col.name.lower() for col in parsed.find_all(exp.Column)}
        for item in definition.metric.filters:
            referenced.add(item.field.lower())
        return referenced.issubset(set(col_lower.keys()))
    except Exception:
        return False


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
