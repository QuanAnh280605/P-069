"""Metric Suggest Node — Flow 1 Step 3.

Dùng LLM (via get_llm()) để phân tích canonical / raw schema và đề xuất
Business Metrics kèm SQL template tham chiếu (không thực thi SQL).

Toàn bộ phân tích ngữ nghĩa (phân loại cột tiền tệ, trạng thái, soft-delete,
phát hiện mối quan hệ ngầm, v.v.) được giao cho LLM thay vì hardcode.
Chỉ có Security Guardrail (chặn SQL nguy hiểm) là deterministic.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# Security guardrail: SQL statements tuyệt đối bị cấm trong sql_template
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Security guardrail: Aggregation types hợp lệ duy nhất
VALID_AGGREGATIONS = frozenset({"sum", "count", "avg", "min", "max", "count_distinct"})


async def metric_suggest_node(state: AgentState) -> dict[str, Any]:
    """Call LLM to propose Business Metrics based on canonical schema.

    Input state fields: enriched_schema | raw_schema
    Output state fields: suggested_metrics | error
    """
    schema_info = state.get("enriched_schema") or state.get("raw_schema")
    if not schema_info:
        return {"error": "metric_suggest_node: schema is empty"}

    schema_text = _format_schema_for_prompt(schema_info)
    prompt = _build_metric_prompt(schema_text, schema_info)

    try:
        llm = get_llm()
        response = await llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        metrics = _parse_and_validate_metrics(raw)
        logger.info("metric_suggest_node: proposed %d metrics", len(metrics))
        return {"suggested_metrics": metrics}
    except Exception as exc:
        logger.warning("metric_suggest_node failed: %s", exc)
        return {"error": f"metric_suggest_node: {exc}"}


# ---------------------------------------------------------------------------
# Schema Formatter — chỉ trích xuất cấu trúc thô, không phân loại ngữ nghĩa
# ---------------------------------------------------------------------------


def _format_schema_for_prompt(schema_info: dict[str, Any]) -> str:
    """Format raw schema structure into readable text for LLM analysis."""
    tables = schema_info.get("tables", [])
    lines = []
    for tbl in tables:
        t_name = _resolve_name(tbl, "table_name")
        pk_list = tbl.get("primary_keys", [])
        pk_note = f" [PK: {', '.join(pk_list)}]" if pk_list else ""
        lines.append(f"Bảng: {t_name}{pk_note}")
        lines.extend(_format_columns(tbl.get("columns", [])))
        lines.extend(_format_foreign_keys(tbl.get("foreign_keys", [])))
    lines.extend(_format_relationships(schema_info.get("relationships", [])))
    return "\n".join(lines)


def _format_columns(columns: list[dict[str, Any]]) -> list[str]:
    """Format column list into indented lines with type and flags."""
    lines = []
    for col in columns:
        c_name = _resolve_name(col, "column_name")
        c_type = str(col.get("data_type") or col.get("raw_data_type", "UNKNOWN")).upper()
        flags = []
        if col.get("is_primary_key"):
            flags.append("PK")
        if col.get("is_foreign_key"):
            flags.append("FK")
        if col.get("is_nullable") is False:
            flags.append("NOT NULL")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"  - {c_name}: {c_type}{flag_str}")
    return lines


def _format_foreign_keys(fks: list[dict[str, Any]]) -> list[str]:
    """Format foreign key constraints into readable lines."""
    lines = []
    for fk in fks:
        local_cols = ", ".join(fk.get("constrained_columns", []))
        ref_table = fk.get("referred_table", "?")
        ref_cols = ", ".join(fk.get("referred_columns", []))
        lines.append(f"  FK: ({local_cols}) → {ref_table}({ref_cols})")
    return lines


def _format_relationships(rels: list[dict[str, Any]]) -> list[str]:
    """Format explicit relationship list into readable lines."""
    if not rels:
        return []
    lines = ["\nQuan hệ giữa các bảng:"]
    for rel in rels:
        lines.append(
            f"  {rel.get('from_table')}.{rel.get('from_column')} → "
            f"{rel.get('to_table')}.{rel.get('to_column')} "
            f"({rel.get('relationship_type', 'unknown')})"
        )
    return lines


def _resolve_name(obj: dict[str, Any], key: str) -> str:
    """Extract name string from dict, handling both flat and nested Identifier formats."""
    val = obj.get(key) or obj.get("name", "unknown")
    if isinstance(val, dict):
        return val.get("raw_name") or val.get("normalized_name", "unknown")
    return str(val)


# ---------------------------------------------------------------------------
# Prompt Builder — giao toàn bộ phân tích ngữ nghĩa cho LLM
# ---------------------------------------------------------------------------


def _build_metric_prompt(schema_text: str, schema_info: dict[str, Any]) -> str:
    """Build Vietnamese prompt delegating ALL semantic analysis to LLM."""
    db_engine = schema_info.get("source", {}).get("db_engine", "postgresql")

    return f"""Bạn là một chuyên gia Data Analyst giàu kinh nghiệm. Hãy phân tích cấu trúc cơ sở dữ liệu (Canonical Schema) dưới đây và tự động đề xuất các Business Metrics quan trọng nhất.

=== CẤU TRÚC DATABASE (Dialect: {db_engine.upper()}) ===
{schema_text}

=== NHIỆM VỤ PHÂN TÍCH CỦA BẠN ===
Bạn PHẢI tự phân tích ngữ nghĩa từng cột dựa trên TÊN CỘT, KIỂU DỮ LIỆU và NGỮ CẢNH:

1. **Nhận diện cột tiền tệ/tài chính**: Tìm các cột lưu giá trị tiền (amount, price, cost, revenue, fee, discount, balance, salary...) → Gợi ý SUM, AVG.
2. **Nhận diện cột số lượng**: Tìm các cột đếm số lượng (quantity, qty, stock, views, clicks...) → Gợi ý SUM, AVG.
3. **Nhận diện cột định danh**: Tìm Primary Key, Foreign Key → Gợi ý COUNT, COUNT_DISTINCT.
4. **Nhận diện cột trạng thái/phân loại**: Tìm cột status, state, is_active... → Tạo điều kiện lọc WHERE phù hợp.
5. **Nhận diện cột thời gian**: Tìm cặp cột thời gian (created_at, delivered_at, resolved_at...) → Gợi ý metric hiệu suất vận hành (thời gian xử lý trung bình).
6. **Phát hiện Soft-Delete**: Nếu bảng có cột is_deleted, deleted_at, is_active... → BẮT BUỘC thêm điều kiện lọc bản ghi chưa xóa vào WHERE của MỌI metric liên quan.
7. **Phát hiện quan hệ ngầm (Inferred FK)**: Nếu cột có tên dạng xxx_id nhưng KHÔNG có FK constraint chính thức → Vẫn có thể sử dụng để tạo metric liên bảng.
8. **Xử lý SQL Reserved Words**: Nếu tên bảng/cột trùng từ khóa SQL (order, group, user, select...) → Phải đặt trong dấu nháy phù hợp với dialect.
9. **Composite Primary Key**: Nếu bảng có nhiều cột PK → Dùng COUNT_DISTINCT với CONCAT khi đếm.
10. **Công thức phức tạp**: Nếu phát hiện cặp cột tính toán trong cùng bảng (quantity × unit_price, v.v.) → Sinh sql_template chứa biểu thức đại số.

=== YÊU CẦU ĐẦU RA ===
Trả về MỘT JSON array hợp lệ gồm từ 3 đến 7 Business Metrics.
Mỗi metric là một object JSON với các trường BẮT BUỘC:

- "name": Tên kỹ thuật snake_case tiếng Anh (VD: "total_revenue")
- "business_name": Tên hiển thị Tiếng Việt rõ nghĩa (VD: "Tổng doanh thu")
- "description": Mô tả chi tiết Tiếng Việt, ghi rõ điều kiện lọc nếu có
- "target_table": Tên bảng chính
- "aggregation": Chỉ dùng 1 trong 6 giá trị: "sum", "count", "avg", "min", "max", "count_distinct"
- "field": Tên cột chính đưa vào hàm tính toán
- "sql_template": Câu SQL SELECT mẫu — TUYỆT ĐỐI CHỈ DÙNG SELECT, KHÔNG INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE

CHỈ trả về JSON array thuần túy, không giải thích, không markdown code fence.
"""


# ---------------------------------------------------------------------------
# Parser & Security Guardrail (deterministic, không giao cho LLM)
# ---------------------------------------------------------------------------


def _parse_and_validate_metrics(
    content: str | list[Any],
) -> list[dict[str, Any]]:
    """Parse JSON from LLM output and apply security guardrail validations."""
    raw_list = _extract_json_list(content)
    valid_metrics = []
    for item in raw_list:
        validated = _validate_single_metric(item)
        if validated is not None:
            valid_metrics.append(validated)
    return valid_metrics


def _extract_json_list(content: str | list[Any]) -> list[Any]:
    """Strip markdown fences and extract JSON array from LLM response.

    Handles cases where LLM adds filler text before/after the JSON block.
    """
    if isinstance(content, list):
        return content
    text = str(content).strip()
    # Strip markdown code fences (```json ... ```)
    fence_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        text = fence_match.group(1).strip()
    # Try direct parse first (happy path)
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Fallback: find first [...] bracket pair via counting
    start = text.find("[")
    if start == -1:
        raise json.JSONDecodeError(
            "No JSON array found in LLM response",
            text,
            0,
        )
    depth, end = 0, start
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
        if depth == 0:
            end = i
            break
    return json.loads(text[start : end + 1])


def _validate_single_metric(item: dict[str, Any]) -> dict[str, Any] | None:
    """Validate one metric for SQL safety and field completeness."""
    name = str(item.get("name", "")).strip()
    sql = str(item.get("sql_template", "")).strip()

    if not name:
        logger.warning("Guardrail reject: metric missing 'name'")
        return None
    if not sql:
        logger.warning("Guardrail reject '%s': missing sql_template", name)
        return None
    if not sql.upper().lstrip().startswith("SELECT"):
        logger.warning("Guardrail reject '%s': must start with SELECT", name)
        return None
    if FORBIDDEN_SQL_PATTERN.search(sql):
        logger.warning("Guardrail reject '%s': forbidden SQL keyword", name)
        return None

    aggregation = str(item.get("aggregation", "count")).lower()
    if aggregation not in VALID_AGGREGATIONS:
        logger.warning("Guardrail reject '%s': invalid aggregation '%s'", name, aggregation)
        return None

    return {
        "name": name,
        "business_name": str(item.get("business_name", "")),
        "description": str(item.get("description", "")),
        "target_table": str(item.get("target_table", "")),
        "aggregation": aggregation,
        "field": str(item.get("field", "")),
        "sql_template": sql,
    }
