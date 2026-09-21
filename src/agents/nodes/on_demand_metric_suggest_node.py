"""Generate canonical metric definitions from enriched semantic metadata."""

from __future__ import annotations

import json
import logging
from typing import Any

import sqlglot
from sqlglot import exp

from src.agents.state import AgentState
from src.models.metric_definition import MetricDefinition
from src.models.schemas import MetricSuggestionItem, MetricSuggestions
from src.services.dimension_mapping import normalize_dimension_references
from src.services.metric_dedupe import merge_dedupe
from src.services.metric_definitions import _is_numeric
from src.services.metric_schema_selector import select_metric_schema
from src.services.metrics import (
    MetricGenerationTimeoutError,
    _parse_metric_payload,
    _references_schema,
    build_metric_system_prompt,
    extract_schema_summary,
    invoke_metric_structured,
)

logger = logging.getLogger(__name__)


async def on_demand_metric_suggest_node(state: AgentState) -> dict[str, Any]:
    """Generate canonical metric definition suggestions on demand from user chat request."""
    schema = state.get("enriched_schema") or {}
    user_msg = state.get("user_message", "").strip()
    can_generate = state.get("can_generate_metrics", False)
    existing = state.get("existing_metrics") or []
    dedupe_performed = state.get("dedupe_performed", True)

    try:
        definitions, rejection_reason = await _resolve_metric_definitions(state, schema)
        if not definitions:
            fail_reason = (
                rejection_reason or "Không có metric nào hợp lệ với schema hiện tại (thiếu bảng hoặc cột tương ứng)."
            )
            return _build_error_output(fail_reason, user_msg)
        return _build_suggestion_output(definitions, existing, can_generate, dedupe_performed)
    except Exception as exc:
        logger.warning("On-demand metric suggestion failed: %s", exc)
        return _build_error_output(str(exc), user_msg, exc=exc)


def _build_error_output(fail_reason: str, user_msg: str, exc: Exception | None = None) -> dict[str, Any]:
    """Format structured error payload for agent state."""
    error_obj = exc if exc is not None else RuntimeError(fail_reason)
    return {
        "error": f"on_demand_metric_suggest_node: {fail_reason}",
        "intent": "metric_query",
        "chat_response": _format_failure_response(error_obj, user_msg),
        "suggested_metrics": [],
        "duplicate_notices": [],
        "dedupe_performed": False,
    }


def _format_failure_response(error: Exception, user_msg: str) -> str:
    """Provide a friendly explanation when metric definition fails."""
    if isinstance(error, MetricGenerationTimeoutError):
        return "AI phản hồi quá 45 giây nên yêu cầu đã được dừng. Vui lòng thử lại."
    error_str = str(error)
    if "không phải số" in error_str:
        return (
            f"Không thể tạo chỉ số '{user_msg}' tự động: {error_str}\n\n"
            "💡 Gợi ý: Nếu bạn muốn tính khoảng thời gian (như thời gian giao hàng), "
            "bảng dữ liệu cần có sẵn cột số đo thời lượng (ví dụ: `delivery_hours` hoặc `duration_seconds`)."
        )
    return (
        "Không thể tạo định nghĩa chỉ số do xảy ra sự cố phân tích schema. Vui lòng thử lại với yêu cầu chi tiết hơn."
    )


def _build_suggest_messages(state: AgentState, schema: dict[str, Any]) -> list[tuple[str, str]]:
    """Prune schema and prepare metric LLM prompt messages."""
    user_msg = state.get("user_message", "").strip()
    clarified_dims = state.get("clarified_dimensions")
    candidate_dims = state.get("grounded_candidate_dimensions")
    pruned = select_metric_schema(schema, user_msg, clarified_dims=clarified_dims, candidate_dims=candidate_dims)
    _, schema_text = extract_schema_summary(pruned)
    sys_prompt = build_metric_system_prompt(schema_text, None, requested_metric=True)
    history = _format_history(state.get("chat_history", []))
    current = user_msg or "Hãy đề xuất 3 metric quan trọng nhất từ schema trên."
    return _metric_messages(sys_prompt, history, current, state.get("metric_decision", {}))


async def _resolve_metric_definitions(
    state: AgentState,
    schema: dict[str, Any],
) -> tuple[list[MetricDefinition], str | None]:
    """Prune schema, build prompt, invoke LLM, and validate definitions with self-correction."""
    valid_columns, _ = extract_schema_summary(schema)
    column_types = _extract_column_types(schema)
    decision = state.get("metric_decision", {})
    candidate_dims = state.get("grounded_candidate_dimensions")
    clarified_dims = state.get("clarified_dimensions")

    messages = _build_suggest_messages(state, schema)
    raw_defs = await _generate_definitions(messages)
    valid_defs, reason = _valid_definitions(
        raw_defs, valid_columns, column_types, decision, candidate_dims, clarified_dims
    )
    if valid_defs or not reason:
        return valid_defs, reason

    repaired_defs = await _repair_invalid_definitions(messages, raw_defs, reason)
    return _valid_definitions(repaired_defs, valid_columns, column_types, decision, candidate_dims, clarified_dims)


async def _repair_invalid_definitions(
    messages: list[tuple[str, str]],
    invalid_defs: list[MetricDefinition],
    rejection_reason: str,
) -> list[MetricDefinition]:
    """Attempt a 1-step self-correction when generated definitions fail validation."""
    prev_json = json.dumps(
        {"metrics": [d.model_dump(mode="json") for d in invalid_defs]},
        ensure_ascii=False,
    )
    instruction = (
        f"Định nghĩa metric trước đó không hợp lệ do lỗi: {rejection_reason}.\n"
        "Vui lòng sửa lại định nghĩa: TUYỆT ĐỐI KHÔNG dùng SUM/AVG trên cột không phải kiểu số. "
        "Nếu tính tỷ lệ hoặc cờ hiệu, hãy dùng hàm COUNT trên PK (ví dụ: COUNT(id)) kết hợp bộ lọc (filters) tương ứng. "
        "Chỉ trả về DUY NHẤT 1 JSON theo cấu trúc chuẩn."
    )
    repair_messages = list(messages) + [("assistant", prev_json), ("user", instruction)]
    try:
        return await _generate_definitions(repair_messages)
    except Exception as exc:
        logger.warning("Self-correction metric generation failed: %s", exc)
        return []


def _extract_column_types(schema_dict: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Build a mapping of {table_name: {column_name_lower: data_type}}."""
    result: dict[str, dict[str, str]] = {}
    tables_data = schema_dict.get("tables", schema_dict)
    items = []
    if isinstance(tables_data, list):
        items = [(t.get("table_name") or t.get("name", ""), t) for t in tables_data if isinstance(t, dict)]
    elif isinstance(tables_data, dict):
        items = list(tables_data.items())
    for table_name, table in items:
        if not isinstance(table, dict):
            continue
        t_name = (table.get("table_name") or table.get("name") or table_name or "").strip().lower()
        cols: dict[str, str] = {}
        for col in table.get("columns", []):
            if isinstance(col, dict):
                c_name = col.get("column_name") or col.get("name")
                if c_name:
                    cols[str(c_name).strip().lower()] = str(col.get("data_type") or "")
        result[t_name] = cols
    return result


def _validate_formula_expression_types(
    definition: MetricDefinition,
    column_types: dict[str, dict[str, str]],
) -> tuple[bool, str | None]:
    """Validate that SUM and AVG only operate on numeric columns."""
    formula = definition.metric.formula
    if formula.function not in {"SUM", "AVG"} or formula.expression == "*":
        return True, None
    try:
        parsed = sqlglot.parse_one(formula.expression)
    except Exception:
        return False, f"Biểu thức '{formula.expression}' không đúng cú pháp SQL"

    t_name = definition.metric.base_entity.strip().lower()
    table_cols = column_types.get(t_name, {})
    non_numeric = []
    for col_node in parsed.find_all(exp.Column):
        col_name = col_node.name.strip().lower()
        if col_name in table_cols:
            dt = table_cols[col_name]
            if dt and not _is_numeric(dt):
                non_numeric.append((col_node.name, dt))

    if non_numeric:
        col_desc = ", ".join(f"`{c}` ({dt})" for c, dt in non_numeric)
        return False, f"Hàm {formula.function} yêu cầu cột kiểu số, nhưng các cột sau không phải số: {col_desc}"
    return True, None


def _build_suggestion_output(
    definitions: list[MetricDefinition],
    existing: list[dict[str, Any]],
    can_generate: bool,
    dedupe_performed: bool,
) -> dict[str, Any]:
    """Format and deduplicate generated definitions for agent response."""
    items = [
        MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()).model_dump(mode="json")
        for item in definitions
    ]
    suggestions = [MetricSuggestionItem.model_validate(item) for item in items]
    kept, notices = merge_dedupe(suggestions, [], [], existing)
    action = "save_metric" if can_generate else "submit_metric_request"
    first_metric_name = definitions[0].metric.name if definitions else "Metric"
    dim_str = ", ".join(definitions[0].metric.dimensions) if (definitions and definitions[0].metric.dimensions) else ""
    dim_note = f" (chiều phân tích: {dim_str})" if dim_str else ""
    return {
        "intent": "metric_query",
        "chat_response": f"Dựa trên các tiêu chí đã làm rõ, tôi đề xuất định nghĩa chỉ số '{first_metric_name}'{dim_note}:",
        "suggested_metrics": [item.model_dump(mode="json") for item in kept[:1]],
        "duplicate_notices": [notice.model_dump() for notice in notices],
        "dedupe_performed": dedupe_performed,
        "suggestion_action": action,
    }


def _metric_messages(sys_prompt: str, history: str, current: str, decision: dict[str, Any]) -> list[tuple[str, str]]:
    """Build a bounded request that carries unresolved business assumptions."""
    assumptions = decision.get("assumptions", [])
    assumption_text = "\n".join(f"- {item}" for item in assumptions) or "(không có)"
    content = (
        f"Lịch sử liên quan:\n{history}\n\nYêu cầu mới nhất:\n{current}\n\nGiả định cần xác nhận:\n{assumption_text}"
    )
    return [("system", sys_prompt), ("user", content)]


def _valid_definitions(
    definitions: list[MetricDefinition],
    valid_columns: dict[str, set[str]],
    column_types: dict[str, dict[str, str]],
    decision: dict[str, Any],
    candidate_dims: list[dict[str, Any]] | None = None,
    clarified_dims: list[str] | None = None,
) -> tuple[list[MetricDefinition], str | None]:
    """Keep schema-valid definitions, filter out invalid types, and populate dimensions."""
    first_rejection_reason: str | None = None
    type_checked: list[MetricDefinition] = []
    for item in definitions:
        if not _references_schema(item, valid_columns):
            continue
        is_valid, reason = _validate_formula_expression_types(item, column_types)
        if not is_valid:
            if first_rejection_reason is None:
                first_rejection_reason = reason
            continue
        type_checked.append(item)

    assumptions = [str(item).strip() for item in decision.get("assumptions", []) if str(item).strip()]
    for item in type_checked:
        _apply_assumptions(item, assumptions)
        _populate_dimensions(item, candidate_dims, clarified_dims)

    return type_checked[:1], first_rejection_reason


def _populate_dimensions(
    item: MetricDefinition,
    candidate_dims: list[dict[str, Any]] | None,
    clarified_dims: list[str] | None,
) -> None:
    """Populate dimensions and replace technical keys with display columns."""
    selected = clarified_dims or item.metric.dimensions
    if selected:
        item.metric.dimensions = normalize_dimension_references(selected, item.metric.base_entity, candidate_dims or [])
        return
    if not candidate_dims:
        return
    base_names: list[str] = []
    other_names: list[str] = []
    for d in candidate_dims:
        c_name = d.get("column_name")
        if not c_name or str(c_name).endswith("_id") or c_name == "id":
            continue
        if d.get("table_name") == item.metric.base_entity and str(c_name) not in base_names:
            base_names.append(str(c_name))
        elif str(c_name) not in other_names:
            other_names.append(str(c_name))
    safe_names = base_names if base_names else other_names
    fallback_names = [str(d.get("column_name")) for d in candidate_dims[:2] if d.get("column_name")]
    item.metric.dimensions = safe_names[:3] if safe_names else fallback_names


def _apply_assumptions(definition: MetricDefinition, assumptions: list[str]) -> None:
    """Lower confidence without allowing the LLM to silently infer business rules."""
    if not assumptions:
        return
    note = "Giả định cần xác nhận: " + "; ".join(assumptions)
    existing = definition.metric.excluded_notes.strip()
    definition.metric.excluded_notes = f"{existing}\n{note}".strip()
    definition.metric.confidence = "low"


async def _generate_definitions(prompt: Any) -> list[MetricDefinition]:
    """Run one bounded structured completion and return its definitions."""
    response = await invoke_metric_structured(prompt, MetricSuggestions)
    return _parse_metric_payload(response)


def _format_history(history: list[dict[str, str]]) -> str:
    """Format bounded prior conversation context for metric generation."""
    lines = []
    for item in history[-6:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            lines.append(f"{item['role']}: {item['content'][:1200]}")
    return "\n".join(lines) or "(không có)"
