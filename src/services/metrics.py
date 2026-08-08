"""Business Metric generation and SQL validation service.

Generates draft business metrics using LLM structured output and validates
each metric SQL template with sqlglot for read-only safety.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import sqlglot
from sqlglot import exp

from src.models.schemas import (
    GeneratedMetric,
    MetricSuggestionItem,
    MetricSuggestions,
)
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

DANGEROUS_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Transaction,
    exp.Pragma,
    exp.Commit,
    exp.Rollback,
)


def normalize_prompt(prompt: str) -> str:
    """Trim whitespace and validate prompt length between 1 and 2000 chars."""
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty")
    if len(cleaned) > 2000:
        raise ValueError("Prompt exceeds maximum length of 2000 characters")
    return cleaned


def extract_schema_summary(schema_dict: dict[str, Any]) -> tuple[dict[str, set[str]], str]:
    """Extract valid table/column map and format a text summary for LLM prompt."""
    valid_tables: dict[str, set[str]] = {}
    lines: list[str] = []

    for tbl_name, tbl_info in schema_dict.items():
        b_tbl = tbl_info.get("business_name") or tbl_name
        desc_tbl = tbl_info.get("description") or ""
        lines.append(f"Table `{tbl_name}` (Tên nghiệp vụ: {b_tbl}, Mô tả: {desc_tbl}):")

        cols = tbl_info.get("columns", [])
        col_names: set[str] = set()
        for col in cols:
            c_name = col.get("column_name") or col.get("name", "")
            if not c_name:
                continue
            col_names.add(c_name.lower())
            b_col = col.get("business_name") or c_name
            d_type = col.get("data_type") or "TEXT"
            pk_str = " [PK]" if col.get("is_primary_key") else ""
            fk_str = f" [FK->{col.get('fk_target_table')}]" if col.get("is_foreign_key") else ""
            lines.append(f"  - `{c_name}` ({d_type}){pk_str}{fk_str}: {b_col}")

        valid_tables[tbl_name.lower()] = col_names

    return valid_tables, "\n".join(lines)


def _find_cte_names(ast: exp.Expression) -> set[str]:
    """Return all CTE alias names defined in the AST."""
    cte_names: set[str] = set()
    for cte in ast.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())
    return cte_names


def _check_dangerous_expressions(ast: exp.Expression) -> bool:
    """Return True if AST contains any data modification or DDL statements."""
    for expr_type in DANGEROUS_EXPRESSIONS:
        if ast.find(expr_type):
            return True
    return False


def _check_table_identifiers(ast: exp.Expression, valid_tables: dict[str, set[str]]) -> bool:
    """Verify that all referenced tables exist in the schema metadata."""
    if not valid_tables:
        return True
    cte_names = _find_cte_names(ast)
    valid_set = set(valid_tables.keys()) | cte_names

    for tbl in ast.find_all(exp.Table):
        t_name = tbl.name.lower()
        if t_name and t_name not in valid_set:
            return False
    return True


def validate_sql_template(
    sql: str,
    dialect: str = "postgres",
    valid_tables: dict[str, set[str]] | None = None,
) -> tuple[bool, str]:
    """Validate that SQL is a single, valid read-only SELECT statement."""
    cleaned_sql = sql.strip().rstrip(";")
    if not cleaned_sql:
        return False, "SQL statement is empty"

    try:
        parsed_list = sqlglot.parse(cleaned_sql, read=dialect)
    except Exception as exc:
        return False, f"SQL syntax error under dialect '{dialect}': {exc}"

    if not parsed_list or len(parsed_list) != 1:
        return False, "SQL must contain exactly one statement"

    ast = parsed_list[0]
    if not isinstance(ast, (exp.Select, exp.Union)):
        return False, "SQL root statement must be a read-only SELECT query"

    if _check_dangerous_expressions(ast):
        return False, "SQL contains modifying or DDL operations"

    if valid_tables and not _check_table_identifiers(ast, valid_tables):
        return False, "SQL references tables not present in schema"

    return True, "Valid SELECT query"


def format_sql(sql: str, dialect: str = "postgres") -> str:
    """Format and pretty-print SQL with multi-line indentation and clause breaks."""
    cleaned = sql.strip().rstrip(";")
    try:
        parsed = sqlglot.parse_one(cleaned, read=dialect)
        return parsed.sql(dialect=dialect, pretty=True)
    except Exception:
        for kw in ("FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "LEFT JOIN", "INNER JOIN", "JOIN"):
            cleaned = cleaned.replace(f" {kw} ", f"\n{kw} ")
        return cleaned


def build_metric_system_prompt(dialect: str, schema_text: str) -> str:
    """Construct LLM system prompt for structured metric generation in Vietnamese."""
    return (
        f"Bạn là chuyên gia phân tích dữ liệu (Data Analyst).\n"
        f"Nhiệm vụ của bạn là đề xuất từ 1 đến 3 chỉ số kinh doanh (Business Metrics) "
        f"chuẩn xác dựa trên yêu cầu và trả về kết quả dưới định dạng JSON (JSON object) hợp lệ:\n"
        f'{{"metrics": [{{"name": "...", "description": "...", "sql_template": "..."}}]}}\n\n'
        f"### Dialect: {dialect}\n"
        f"### Schema Metadata:\n{schema_text}\n\n"
        f"### Quy tắc BẮT BUỘC:\n"
        f"1. Trả về đúng định dạng JSON chứa danh sách `metrics`.\n"
        f"2. `name` và `description` của mỗi metric PHẢI viết bằng tiếng Việt.\n"
        f"3. Mỗi `sql_template` PHẢI là đúng một câu lệnh `SELECT` duy nhất, không dùng multi-statement.\n"
        f"4. TUYỆT ĐỐI KHÔNG sinh câu lệnh `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`.\n"
        f"5. CHỈ ĐƯỢC PHÉP tham chiếu các bảng và cột thực sự tồn tại trong Schema Metadata ở trên.\n"
        f"6. Đảm bảo cú pháp SQL tương thích hoàn toàn với dialect `{dialect}`.\n"
        f"7. Trả về đúng từ 1 đến 3 metrics liên quan trực tiếp đến yêu cầu."
    )


async def _invoke_llm_for_metrics(
    prompt: str,
    dialect: str,
    schema_text: str,
) -> list[GeneratedMetric]:
    """Invoke LLM with structured output schema for MetricSuggestions with multi-fallback."""
    system_prompt = build_metric_system_prompt(dialect, schema_text)
    llm = get_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Yêu cầu chỉ số kinh doanh (trả về kết quả JSON): {prompt}"},
    ]

    # Attempt 1: Standard structured output
    try:
        structured_llm = llm.with_structured_output(MetricSuggestions)
        res = await structured_llm.ainvoke(messages)
        if isinstance(res, MetricSuggestions) and res.metrics:
            return res.metrics
        if isinstance(res, dict) and "metrics" in res:
            return [GeneratedMetric(**m) for m in res["metrics"]]
    except Exception as exc:
        logger.info("Standard structured output failed: %s", exc)

    # Attempt 2: json_mode fallback (Groq / Gemini)
    try:
        structured_llm = llm.with_structured_output(MetricSuggestions, method="json_mode")
        res = await structured_llm.ainvoke(messages)
        if isinstance(res, MetricSuggestions) and res.metrics:
            return res.metrics
        if isinstance(res, dict) and "metrics" in res:
            return [GeneratedMetric(**m) for m in res["metrics"]]
    except Exception as exc:
        logger.info("json_mode fallback failed: %s", exc)

    # Attempt 3: Raw response with JSON parsing
    try:
        raw_msg = await llm.ainvoke(messages)
        content = str(raw_msg.content)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "metrics" in parsed:
            return [GeneratedMetric(**m) for m in parsed["metrics"]]
        if isinstance(parsed, list):
            return [GeneratedMetric(**m) for m in parsed]
    except Exception as exc:
        logger.warning("Raw JSON parsing fallback failed: %s", exc)

    return []


async def generate_metrics_from_prompt(
    prompt: str,
    dialect: str = "postgres",
    schema_dict: dict[str, Any] | None = None,
    schema_context: dict[str, Any] | None = None,
    target_tables: list[str] | None = None,
    max_retries: int = 1,
) -> list[MetricSuggestionItem]:
    """Generate and validate 1 to 3 business metrics matching user prompt."""
    cleaned_prompt = normalize_prompt(prompt)
    schema_data = schema_dict or schema_context or {}
    if target_tables:
        schema_data = {k: v for k, v in schema_data.items() if k in target_tables} or schema_data
    valid_tables, schema_text = extract_schema_summary(schema_data)

    current_attempt = 0
    while current_attempt <= max_retries:
        try:
            raw_metrics = await _invoke_llm_for_metrics(cleaned_prompt, dialect, schema_text)
        except Exception as exc:
            logger.warning("LLM generation attempt %d failed: %s", current_attempt + 1, exc)
            current_attempt += 1
            if current_attempt > max_retries:
                raise RuntimeError(f"LLM provider error during metric generation: {exc}") from exc
            continue

        valid_suggestions: list[MetricSuggestionItem] = []
        for metric in raw_metrics:
            is_valid, reason = validate_sql_template(metric.sql_template, dialect, valid_tables)
            if is_valid:
                pretty_sql = format_sql(metric.sql_template, dialect)
                valid_suggestions.append(
                    MetricSuggestionItem(
                        name=metric.name.strip(),
                        description=metric.description.strip(),
                        sql_template=pretty_sql,
                        source="ai",
                    )
                )
            else:
                logger.info("Discarding invalid generated metric SQL: %s (%s)", metric.name, reason)

        if valid_suggestions:
            return valid_suggestions[:3]

        current_attempt += 1

    raise ValueError("LLM failed to generate valid business metrics conforming to schema")
