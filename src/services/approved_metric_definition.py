"""Render approved metric definitions without a generative model."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from src.models.metric_definition import MetricDefinition

_DEFINITION_MARKERS = ("dinh nghia", "cong thuc", "cach tinh", "duoc tinh nhu the nao")
_METRIC_SUBJECTS = ("metric", "chi so", "kpi")
_QUESTION_WORDS = {
    "dinh",
    "nghia",
    "cong",
    "thuc",
    "cach",
    "tinh",
    "duoc",
    "nhu",
    "the",
    "nao",
    "metric",
    "chi",
    "so",
    "kpi",
}
_OPERATORS = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "in": "IN",
    "not_in": "NOT IN",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
}


def is_approved_metric_definition_request(question: str, metrics: Any) -> bool:
    """Return whether a definition question has one or more approved metric matches."""
    return _is_definition_question(question) and bool(_matching_metrics(question, metrics))


def build_approved_metric_definition_response(question: str, metrics: Any) -> str | None:
    """Return a deterministic approved-metric definition response when applicable."""
    if not _is_definition_question(question):
        return None
    matches = _matching_metrics(question, metrics)
    if len(matches) == 1:
        return _render_definition(matches[0])
    if len(matches) > 1:
        names = "\n".join(f"- **{item['name']}**" for item in matches)
        return f"Tôi tìm thấy nhiều metric phù hợp. Bạn muốn xem định nghĩa của metric nào?\n\n{names}"
    return None


def _is_definition_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(marker in normalized for marker in _DEFINITION_MARKERS) and any(
        subject in normalized for subject in _METRIC_SUBJECTS
    )


def _matching_metrics(question: str, metrics: Any) -> list[dict[str, Any]]:
    if not isinstance(metrics, list):
        return []
    question_tokens = _content_tokens(question)
    matches = [item for item in metrics if isinstance(item, dict) and _matches(question_tokens, item.get("name"))]
    return sorted(matches, key=lambda item: (str(item.get("name", "")).casefold(), int(item.get("id", 0))))


def _matches(question_tokens: set[str], name: Any) -> bool:
    metric_tokens = _content_tokens(_without_parentheses(str(name or "")))
    overlap = question_tokens & metric_tokens
    return bool(metric_tokens) and (
        metric_tokens <= question_tokens or (len(overlap) >= 2 and len(overlap) / len(metric_tokens) >= 0.6)
    )


def _content_tokens(value: str) -> set[str]:
    return {token for token in _normalize(value).split() if token not in _QUESTION_WORDS}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def _without_parentheses(value: str) -> str:
    return re.sub(r"\([^)]*\)", "", value).strip()


def _render_definition(metric: dict[str, Any]) -> str:
    definition = _metric_definition(metric.get("definition"))
    if definition is None:
        return f"**Metric đã được phê duyệt:** **{metric['name']}**\n\nChi tiết công thức chưa ở định dạng chuẩn để hiển thị."
    spec = definition.metric
    lines = [
        f"**Metric đã được phê duyệt:** **{metric['name']}**",
        "",
        f"- **Công thức:** `{spec.formula.function}({spec.formula.expression})`",
        f"- **Thực thể cơ sở:** `{spec.base_entity}`",
    ]
    if spec.filters:
        lines.append(f"- **Bộ lọc cố định:** {_filter_text(spec.filters)}")
    if spec.confidence:
        lines.append(f"- **Mức độ tin cậy:** `{spec.confidence}`")
    if spec.excluded_notes:
        lines.append(f"- **Lưu ý:** {spec.excluded_notes}")
    return "\n".join(lines)


def _metric_definition(value: Any) -> MetricDefinition | None:
    if isinstance(value, MetricDefinition):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        return MetricDefinition.model_validate(value)
    except (TypeError, ValueError):
        return None


def _filter_text(filters: list[Any]) -> str:
    return ", ".join(_one_filter_text(item) for item in filters)


def _one_filter_text(filter_item: Any) -> str:
    operator = _OPERATORS.get(filter_item.operator, filter_item.operator)
    if filter_item.operator in {"is_null", "is_not_null"}:
        return f"`{filter_item.field} {operator}`"
    value = repr(filter_item.value) if isinstance(filter_item.value, str) else str(filter_item.value)
    return f"`{filter_item.field} {operator} {value}`"
