"""Generate canonical metric definitions without asking the LLM for SQL."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any, TypeVar
from urllib.parse import urlparse

import sqlglot
from pydantic import BaseModel
from sqlglot import exp

from src.config import get_settings
from src.models.metric_definition import MetricDefinition
from src.models.schemas import (
    DuplicateMetricNotice,
    MetricConflictInfo,
    MetricSuggestionItem,
    MetricSuggestions,
    MetricSuggestionsV2,
)
from src.services.dimension_mapping import dimension_candidates_from_schema, normalize_dimension_references
from src.services.llm import get_llm
from src.services.llm_json import extract_json
from src.services.metric_dedupe import format_existing_metrics_context, merge_dedupe

logger = logging.getLogger(__name__)

_NoticeT = TypeVar("_NoticeT", bound=BaseModel)

_ParsedSuggestions = tuple[list[MetricDefinition], list[DuplicateMetricNotice], list[MetricConflictInfo]]
_ResponseT = TypeVar("_ResponseT", bound=BaseModel)
_NULL_FILTER_OPERATORS = {"is_null", "is_not_null"}


class MetricGenerationError(RuntimeError):
    """Base error for one bounded Metric LLM completion."""


class MetricGenerationTimeoutError(MetricGenerationError):
    """Raised when Metric LLM generation exceeds its configured deadline."""


class MetricGenerationInvalidError(MetricGenerationError, ValueError):
    """Raised when Metric LLM output cannot pass canonical validation."""


class MetricGenerationUnavailableError(MetricGenerationError):
    """Raised when the Metric LLM provider fails before returning output."""


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
        flags = []
        if column.get("is_primary_key"):
            flags.append("PK/grain")
        if column.get("is_foreign_key"):
            flags.append("FK")
        if column.get("is_nullable"):
            flags.append("nullable")
        business = column.get("business_name") or name
        desc = (column.get("description") or "").strip()[:80]
        desc_str = f" — {desc}" if desc and desc.lower() != business.lower() else ""
        suffix = f"; {', '.join(flags)}" if flags else ""
        default_val = column.get("default_value")
        if default_val is not None:
            suffix += f"; default: {default_val}"
        sample_vals = column.get("sample_values") or column.get("allowed_values")
        if sample_vals:
            if isinstance(sample_vals, list):
                sample_str = ", ".join(repr(v) for v in sample_vals[:3])
            else:
                sample_str = str(sample_vals)[:40]
            suffix += f"; values: [{sample_str}]"
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
        "dimensions": ["chiều_phân_tích_1", "chiều_phân_tích_2"],
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
        "dimensions": ["chiều_phân_tích_1", "chiều_phân_tích_2"],
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
8. formula.function SUM và AVG CHỈ áp dụng cho các cột kiểu số (INT, DECIMAL, FLOAT, NUMERIC,...). TUYỆT ĐỐI KHÔNG dùng SUM/AVG cho cột kiểu BOOLEAN (ví dụ: is_canceled, is_active), TEXT, VARCHAR, hoặc các cột thời gian/ngày tháng (TIMESTAMP, DATETIME, DATE). Khi người dùng yêu cầu tính Tỷ lệ (như tỷ lệ hủy đơn, tỷ lệ hoàn trả) mà cờ hiệu trạng thái là kiểu VARCHAR/BOOLEAN/TEXT: TUYỆT ĐỐI KHÔNG dùng AVG trên cột đó; thay vào đó, hãy dùng hàm COUNT trên PK (ví dụ: COUNT(id)) kết hợp bộ lọc filter tương ứng (ví dụ: is_canceled = '1' hoặc 'Y'). TUYỆT ĐỐI KHÔNG viết các biểu thức trừ ngày tháng (ví dụ: delivered_time - created_time) vì hệ thống yêu cầu mọi cột trong SUM/AVG phải là kiểu số (INT, FLOAT, DECIMAL). Nếu người dùng yêu cầu tính thời gian (như thời gian giao hàng, thời gian xử lý) mà schema KHÔNG có cột số đo thời gian (như delivery_hours, duration_seconds), TUYỆT ĐỐI KHÔNG tự tạo phép trừ giữa hai cột TIMESTAMP; thay vào đó, hãy tìm cột số đo thời gian khả dụng hoặc ghi rõ vào excluded_notes rằng schema chưa có cột đo thời lượng dạng số.
9. Tự động thêm dimensions: Luôn điền trường "dimensions" với danh sách tên các cột chiều phân tích phù hợp (ví dụ: ngày đặt hàng, kênh bán, khu vực, cửa hàng...) dựa trên schema hoặc các chiều đã được làm rõ với người dùng. ƯU TIÊN dùng tên thực thể/mô tả nghiệp vụ (ví dụ: store.name, sales_channel.name) thay vì cột khóa ngoại ID (store_id, sales_channel_id).
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
9. Nếu yêu cầu còn điều kiện nghiệp vụ chưa xác định hoặc schema chưa hỗ trợ đầy đủ để tính đúng công thức (ví dụ: đòi tính tỷ lệ khách mua lại nhưng schema không có bảng/cột đo số lần mua), hãy tạo baseline khả thi từ schema, đặt tên metric TRUNG THỰC với bản chất công thức (ví dụ 'Tổng số khách hàng đặt đơn (Baseline)' thay vì 'Tỷ lệ khách quay lại'), đặt confidence là "low" và ghi rõ lý do vào excluded_notes với tiền tố "Giả định cần xác nhận:"."""


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
            if isinstance(item, dict) and isinstance(item.get("metric"), dict):
                pjp = item["metric"].get("preferred_join_paths")
                if isinstance(pjp, dict):
                    clean_pjp = {}
                    for k, v in pjp.items():
                        try:
                            clean_pjp[int(k)] = [int(x) for x in v]
                        except (ValueError, TypeError):
                            pass
                    item["metric"]["preferred_join_paths"] = clean_pjp
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


def _metric_bind_kwargs(llm: Any, max_output_tokens: int) -> dict[str, Any]:
    """Build provider-safe per-call limits for Metric generation."""
    kwargs: dict[str, Any] = {}
    base_llm = getattr(llm, "first", llm)
    hostname = urlparse(str(getattr(base_llm, "openai_api_base", getattr(llm, "openai_api_base", "")))).hostname
    if hostname == "openrouter.ai":
        kwargs["max_tokens"] = max_output_tokens
        extra_body: dict[str, Any] = {
            "provider": {"sort": "throughput", "require_parameters": True},
        }
        model_name = str(getattr(base_llm, "model_name", getattr(llm, "model_name", getattr(base_llm, "model", ""))))
        mandatory_prefixes = ("google/gemini", "z-ai/glm", "openai/o1", "openai/o3", "openai/o4")
        if not any(prefix in model_name.lower() for prefix in mandatory_prefixes):
            extra_body["reasoning"] = {"enabled": False}
        kwargs["extra_body"] = extra_body
    elif hasattr(llm, "openai_api_base"):
        kwargs["max_completion_tokens"] = max_output_tokens
    else:
        kwargs["max_tokens"] = max_output_tokens
    return kwargs


def _structured_metric_runner(llm: Any, response_model: type[_ResponseT], max_output_tokens: int) -> Any:
    """Create a strict structured runner while retaining raw output for repair."""
    bounded = llm.bind(**_metric_bind_kwargs(llm, max_output_tokens))
    try:
        return bounded.with_structured_output(response_model, strict=True, include_raw=True)
    except (TypeError, ValueError):
        return bounded.with_structured_output(response_model, include_raw=True)


def _normalize_llm_metric_payload(payload: Any) -> Any:
    """Repair only deterministic, semantics-preserving LLM transport defects."""
    normalized = copy.deepcopy(payload)
    if not isinstance(normalized, dict) or not isinstance(normalized.get("metrics"), list):
        return normalized
    for item in normalized["metrics"]:
        metric = item.get("metric") if isinstance(item, dict) else None
        filters = metric.get("filters") if isinstance(metric, dict) else None
        for filter_item in filters if isinstance(filters, list) else []:
            if isinstance(filter_item, dict) and filter_item.get("operator") in _NULL_FILTER_OPERATORS:
                filter_item["value"] = None
    return normalized


def _raw_metric_payload(raw: Any) -> Any:
    """Extract a JSON-compatible payload from a raw structured response."""
    content = getattr(raw, "content", raw)
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        return extract_json(content)
    raise ValueError("Metric LLM raw response has no JSON content")


def _validated_metric_response(result: Any, response_model: type[_ResponseT]) -> tuple[_ResponseT, bool]:
    """Return parsed output or locally repair and validate its raw JSON."""
    if isinstance(result, response_model):
        return result, False
    if not isinstance(result, dict):
        raise MetricGenerationInvalidError("Metric LLM returned an unsupported response shape")
    parsed = result.get("parsed")
    if isinstance(parsed, response_model):
        return parsed, False
    try:
        payload = _normalize_llm_metric_payload(_raw_metric_payload(result.get("raw")))
        return response_model.model_validate(payload), True
    except Exception as exc:
        raise MetricGenerationInvalidError("Metric LLM returned an invalid canonical definition") from exc


def _metric_usage(result: Any) -> dict[str, Any]:
    """Extract token counts from a raw LangChain response when available."""
    raw = result.get("raw") if isinstance(result, dict) else None
    usage = getattr(raw, "usage_metadata", None)
    if not isinstance(usage, dict):
        metadata = getattr(raw, "response_metadata", None)
        usage = metadata.get("token_usage", {}) if isinstance(metadata, dict) else {}
    return {
        "input": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output": usage.get("output_tokens", usage.get("completion_tokens")),
        "total": usage.get("total_tokens"),
    }


def _log_metric_completion(llm: Any, started: float, outcome: str, repaired: bool = False, result: Any = None) -> None:
    """Log non-sensitive latency telemetry for one Metric completion."""
    usage = _metric_usage(result)
    logger.info(
        "Metric LLM completion outcome=%s elapsed_ms=%d repaired=%s model=%s "
        "input_tokens=%s output_tokens=%s total_tokens=%s",
        outcome,
        round((time.perf_counter() - started) * 1000),
        repaired,
        getattr(llm, "model_name", getattr(llm, "model", "unknown")),
        usage["input"],
        usage["output"],
        usage["total"],
    )


async def invoke_metric_structured(messages: list[Any], response_model: type[_ResponseT]) -> _ResponseT:
    """Run exactly one bounded Metric LLM completion and validate its output."""
    llm = get_llm(role="metric")
    settings = get_settings()
    runner = _structured_metric_runner(llm, response_model, settings.llm_metric_max_output_tokens)
    started = time.perf_counter()
    try:
        timeout_sec = settings.llm_metric_timeout_seconds
        if timeout_sec and timeout_sec > 0:
            result = await asyncio.wait_for(runner.ainvoke(messages), timeout=timeout_sec)
        else:
            result = await runner.ainvoke(messages)
        response, repaired = _validated_metric_response(result, response_model)
    except TimeoutError as exc:
        _log_metric_completion(llm, started, "timeout")
        raise MetricGenerationTimeoutError(
            f"Metric LLM exceeded the {settings.llm_metric_timeout_seconds:g}-second deadline"
        ) from exc
    except MetricGenerationInvalidError:
        _log_metric_completion(llm, started, "invalid")
        raise
    except Exception as exc:
        _log_metric_completion(llm, started, "upstream_error")
        raise MetricGenerationUnavailableError("Metric LLM provider request failed") from exc
    _log_metric_completion(llm, started, "success", repaired, result)
    return response


async def generate_definitions_v2(
    messages: list[Any],
    use_v2: bool,
) -> _ParsedSuggestions:
    """Invoke one bounded structured Metric completion and parse dedupe judgments."""
    structured_cls: type[MetricSuggestionsV2] | type[MetricSuggestions] = (
        MetricSuggestionsV2 if use_v2 else MetricSuggestions
    )
    response = await invoke_metric_structured(messages, structured_cls)
    return _parse_v2_payload(response)


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


def _filter_target_tables(schema: dict[str, Any], target_tables: list[str] | None) -> dict[str, Any]:
    """Filter both supported schema shapes to explicitly requested tables."""
    if not target_tables:
        return schema
    wanted = set(target_tables)
    tables = schema.get("tables")
    if isinstance(tables, list):
        selected = [table for table in tables if table.get("table_name") in wanted]
        return {**schema, "tables": selected}
    return {name: value for name, value in schema.items() if name in wanted}


def validate_metric_definitions(
    definitions: list[MetricDefinition],
    dialect: str,
    schema_dict: dict[str, Any] | None = None,
    target_tables: list[str] | None = None,
) -> list[MetricDefinition]:
    """Filter definitions whose expressions reference schema-known columns."""
    del dialect
    schema = _filter_target_tables(schema_dict or {}, target_tables)
    valid, _ = extract_schema_summary(schema)
    valid_definitions = [item for item in definitions if _references_schema(item, valid)]
    candidates = dimension_candidates_from_schema(schema)
    for item in valid_definitions:
        item.metric.dimensions = normalize_dimension_references(
            item.metric.dimensions,
            item.metric.base_entity,
            candidates,
        )
    return valid_definitions


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
    schema = _filter_target_tables(schema_dict or schema_context or {}, target_tables)
    use_v2 = bool(existing_metrics)
    existing_text = format_existing_metrics_context(existing_metrics) if use_v2 else None
    _, schema_text = extract_schema_summary(schema)
    messages = [
        {"role": "system", "content": build_metric_system_prompt(schema_text, existing_text, requested_metric=True)},
        {"role": "user", "content": normalize_prompt(prompt)},
    ]
    definitions, llm_duplicates, llm_conflicts = await generate_definitions_v2(messages, use_v2)
    valid_defs = validate_metric_definitions(definitions, dialect, schema, target_tables)
    items = [MetricSuggestionItem(definition=item, yaml_preview=item.to_yaml()) for item in valid_defs]
    kept, notices = merge_dedupe(items, llm_duplicates, llm_conflicts, existing_metrics)
    if not kept and not notices:
        raise MetricGenerationInvalidError("LLM failed to generate valid metric definitions")
    return kept[:1], notices
