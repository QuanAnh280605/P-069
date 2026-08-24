"""Generate canonical metric definitions without asking the LLM for SQL."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import sqlglot
from pydantic import BaseModel
from sqlglot import exp

from src.models.metric_definition import MetricDefinition
from src.models.schemas import (
    DuplicateMetricNotice,
    MetricConflictInfo,
    MetricSuggestionItem,
    MetricSuggestions,
    MetricSuggestionsV2,
)
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json, extract_json
from src.services.metric_dedupe import format_existing_metrics_context, merge_dedupe

logger = logging.getLogger(__name__)

_NoticeT = TypeVar("_NoticeT", bound=BaseModel)

_ParsedSuggestions = tuple[list[MetricDefinition], list[DuplicateMetricNotice], list[MetricConflictInfo]]


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


_PROMPT_HEADER = """Bạn là chuyên gia phân tích dữ liệu (Data Analyst).
Nhiệm vụ: Đề xuất 1-3 Business Metrics bằng tiếng Việt dựa trên schema cơ sở dữ liệu."""

_V1_OUTPUT_FORMAT = """Trả về kết quả ở định dạng JSON thuần túy có cấu trúc như sau:
{
  "metrics": [
    {
      "metric": {
        "name": "Tên metric tiếng Việt",
        "formula": {
          "function": "SUM",
          "expression": "cột_tính_toán"
        },
        "base_entity": "tên_bảng_chính",
        "filters": [],
        "status": "pending_approval",
        "confidence": "high",
        "excluded_notes": "Ghi chú nếu có"
      }
    }
  ]
}"""

_V2_OUTPUT_FORMAT = """Trả về kết quả ở định dạng JSON thuần túy có cấu trúc như sau:
{
  "metrics": [
    {
      "metric": {
        "name": "Tên metric tiếng Việt",
        "formula": {
          "function": "SUM",
          "expression": "cột_tính_toán"
        },
        "base_entity": "tên_bảng_chính",
        "filters": [],
        "status": "pending_approval",
        "confidence": "high",
        "excluded_notes": "Ghi chú nếu có"
      }
    }
  ],
  "duplicates": [
    {
      "proposed_metric_name": "Tên metric đề xuất bị coi là trùng",
      "existing_metric_id": 12,
      "existing_metric_name": "Tên metric đã tồn tại",
      "existing_metric_status": "approved",
      "user_message": "Thông báo tiếng Việt giải thích cho người dùng",
      "similarity_reason": "Điểm giống nhau về ý nghĩa nghiệp vụ và công thức"
    }
  ],
  "conflicts": [
    {
      "proposed_metric_name": "Tên metric đề xuất",
      "existing_metric_id": 12,
      "existing_metric_name": "Tên metric đã tồn tại",
      "existing_metric_status": "approved",
      "suggested_name": "Tên thay thế gợi ý tiếng Việt",
      "clarify_question": "Câu hỏi làm rõ tiếng Việt cho người dùng"
    }
  ]
}

Cả hai mảng "duplicates" và "conflicts" đều được phép rỗng [] nếu không có mục nào."""
_BASE_RULES = """Quy tắc BẮT BUỘC:
0. MỌI nội dung hiển thị cho người dùng (metric.name, excluded_notes, diagnostics) PHẢI bằng tiếng Việt; chỉ giữ nguyên tên bảng/cột và mã kỹ thuật trong Schema.
1. formula.function chỉ dùng: SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX.
2. formula.expression chỉ gồm cột của base_entity, số và các toán tử (+, -, *, /). Không viết SQL, subquery, alias.
3. base_entity và các cột phải tồn tại chính xác trong Schema dưới đây.
4. Ưu tiên base_entity có PK/grain rõ ràng; không giả định quan hệ hoặc ý nghĩa không có trong schema.
5. Filter chỉ dùng cột của base_entity và giá trị được người dùng nêu rõ hoặc có ý nghĩa chắc chắn.
6. Khi dùng filter trên cột có values: [...] trong Schema, PHẢI dùng đúng 1 giá trị trong danh sách values. Không tự tạo giá trị mới.
7. Không tự thêm filter cho trạng thái hoàn thành, hoàn tiền, kích hoạt hoặc bất kỳ điều kiện nghiệp vụ nào người dùng chưa nêu rõ.
8. formula.function SUM và AVG CHỈ áp dụng cho các cột kiểu số (INT, DECIMAL, FLOAT, NUMERIC,...). TUYỆT ĐỐI KHÔNG dùng SUM/AVG cho cột kiểu BOOLEAN (ví dụ: is_canceled, is_active) hay TEXT. Để đếm các bản ghi thoả mãn cờ boolean hoặc trạng thái, PHẢI dùng function "COUNT" (expression "*" hoặc cột ID) kết hợp với "filters" (ví dụ: field "is_canceled", operator "eq", value true).
"""

_DEDUPE_RULES = """8. Trước khi trả về, so sánh mỗi metric đề xuất với danh sách metric đang tồn tại. Nếu một metric đề xuất **cùng ý nghĩa nghiệp vụ và cùng logic tính toán ≥90%** với một metric đã có (bỏ qua hoa/thường, khoảng trắng, khác biệt cú pháp SQL vô nghĩa): KHÔNG đưa metric đó vào `metrics`; thêm mục vào `duplicates` với `proposed_metric_name` đúng bằng tên metric đề xuất bị coi là trùng (để hệ thống tự loại nếu vẫn lọt vào `metrics`), `user_message` tiếng Việt giải thích và `similarity_reason` nêu điểm giống. Nếu metric đã có ở trạng thái `approved`, nhấn mạnh rằng đã có metric chuẩn và không cần tạo mới. Chỉ xếp vào `duplicates` khi hai metric THAY THẾ ĐƯỢC CHO NHAU HOÀN TOÀN — cùng ý nghĩa VÀ cùng công thức sau chuẩn hóa. Nếu công thức/logic khác nhau (kể cả khi ý nghĩa gần giống hoặc tên gần trùng): đó là `conflicts` theo quy tắc 9, TUYỆT ĐỐI KHÔNG xếp vào `duplicates`.
9. Nếu metric đề xuất **trùng hoặc gần trùng tên** (sau khi bỏ qua hoa/thường và khoảng trắng) với metric đã có nhưng **khác logic tính toán**: vẫn đưa vào `metrics`, đồng thời thêm mục vào `conflicts` với `proposed_metric_name` đúng bằng tên đã đề xuất, `suggested_name` là tên thay thế gợi ý (tiếng Việt, tự nhiên, mô tả rõ sự khác biệt về logic, chưa trùng metric nào), và `clarify_question` là câu hỏi tiếng Việt cho người dùng. TUYỆT ĐỐI KHÔNG bịa metric đã có không nằm trong danh sách được cung cấp."""


def build_metric_system_prompt(
    schema_text: str,
    existing_metrics_text: str | None = None,
    requested_metric: bool = False,
) -> str:
    """Build the metric-generation system prompt, optionally with dedupe context."""
    request_rules = _requested_metric_rules() if requested_metric else ""
    rules = f"{_BASE_RULES}\n{request_rules}".strip()
    if existing_metrics_text is None:
        return _render_prompt(_V1_OUTPUT_FORMAT, rules, "", schema_text)
    return _render_prompt(_V2_OUTPUT_FORMAT, f"{rules}\n{_DEDUPE_RULES}", existing_metrics_text, schema_text)


def _render_prompt(output_format: str, rules: str, existing_block: str, schema_text: str) -> str:
    """Assemble prompt sections: header, output format, rules, existing metrics, schema."""
    sections = [_PROMPT_HEADER, output_format, rules]
    if existing_block:
        sections.append(existing_block)
    sections.append(f"Schema database:\n{schema_text}")
    return "\n\n".join(sections)


def _requested_metric_rules() -> str:
    """Return stricter rules for a user-requested metric proposal."""
    return """8. Đây là một metric được người dùng yêu cầu: chỉ trả đúng 1 Metric Definition.
9. Nếu yêu cầu còn điều kiện nghiệp vụ chưa xác định, tạo baseline không có filter suy diễn,
đặt confidence là \"low\" và ghi từng điều kiện đó vào excluded_notes với tiền tố
\"Giả định cần xác nhận:\"."""


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


def _collect_models(items: Any, model: type[_NoticeT]) -> list[_NoticeT]:
    """Validate dedupe list entries against a model, dropping malformed ones."""
    if not isinstance(items, list):
        return []
    collected: list[_NoticeT] = []
    for item in items:
        try:
            collected.append(model.model_validate(item))
        except Exception as exc:
            logger.debug("Dropping malformed %s entry: %s (%s)", model.__name__, item, exc)
    return collected


def _parse_v2_payload(payload: Any) -> _ParsedSuggestions:
    """Parse an LLM payload into definitions plus dedupe judgments.

    Missing keys yield empty lists; malformed dedupe entries are dropped so a
    bad notice never crashes generation.
    """
    if isinstance(payload, MetricSuggestionsV2):
        return list(payload.metrics), list(payload.duplicates), list(payload.conflicts)
    definitions = _parse_metric_payload(payload)
    raw = payload if isinstance(payload, dict) else {}
    duplicates = _collect_models(raw.get("duplicates"), DuplicateMetricNotice)
    conflicts = _collect_models(raw.get("conflicts"), MetricConflictInfo)
    return definitions, duplicates, conflicts


async def generate_definitions_v2(
    messages: list[Any],
    use_v2: bool,
) -> _ParsedSuggestions:
    """Invoke the LLM with structured output; V2 schema when use_v2 else V1.

    Follows the legacy invocation pattern: structured output first, then an
    ainvoke_json raw-text fallback with its built-in corrective retry.
    """
    raw_llm = get_llm(role="metric")
    structured_cls: type[MetricSuggestionsV2] | type[MetricSuggestions] = (
        MetricSuggestionsV2 if use_v2 else MetricSuggestions
    )
    try:
        structured = raw_llm.with_structured_output(structured_cls)
        response = await structured.ainvoke(messages)
        parsed = _parse_v2_payload(response)
        if any(parsed):
            return parsed
    except Exception as exc:
        logger.info("Structured output fallback triggered: %s", exc)

    try:
        payload = await ainvoke_json(raw_llm, messages)
        return _parse_v2_payload(payload)
    except Exception as exc:
        logger.error("LLM metric extraction failed: %s", exc)
        return [], [], []


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


def validate_metric_definitions(
    definitions: list[MetricDefinition],
    dialect: str,
    schema_dict: dict[str, Any] | None = None,
    target_tables: list[str] | None = None,
) -> list[MetricDefinition]:
    """Filter definitions whose expressions reference schema-known columns."""
    del dialect
    schema = schema_dict or {}
    if target_tables:
        schema = {name: value for name, value in schema.items() if name in target_tables}
    valid, _ = extract_schema_summary(schema)
    return [item for item in definitions if _references_schema(item, valid)]


async def generate_metrics_from_prompt(
    prompt: str,
    dialect: str = "postgres",
    schema_dict: dict[str, Any] | None = None,
    schema_context: dict[str, Any] | None = None,
    target_tables: list[str] | None = None,
    max_retries: int = 1,
    existing_metrics: list[dict[str, Any]] | None = None,
) -> tuple[list[MetricSuggestionItem], list[DuplicateMetricNotice]]:
    """Generate validated metric suggestions merged with dedupe notices."""
    del max_retries
    schema = schema_dict or schema_context or {}
    if target_tables:
        schema = {name: value for name, value in schema.items() if name in target_tables}
    use_v2 = bool(existing_metrics)
    existing_text = format_existing_metrics_context(existing_metrics) if use_v2 else None
    _, schema_text = extract_schema_summary(schema)
    messages = [
        {"role": "system", "content": build_metric_system_prompt(schema_text, existing_text)},
        {"role": "user", "content": normalize_prompt(prompt)},
    ]
    definitions, llm_duplicates, llm_conflicts = await generate_definitions_v2(messages, use_v2)
    valid_defs = validate_metric_definitions(definitions, dialect, schema, target_tables)
    items = [MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()) for item in valid_defs]
    kept, notices = merge_dedupe(items, llm_duplicates, llm_conflicts, existing_metrics)
    if not kept and not notices:
        raise ValueError("LLM failed to generate valid metric definitions")
    return kept[:1], notices
