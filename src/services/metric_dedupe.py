"""Deterministic dedupe safety-net for on-demand metric generation."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import SemanticMetricModel
from src.models.metric_definition import MetricDefinition
from src.models.schemas import (
    DuplicateMetricNotice,
    MetricConflictInfo,
    MetricSuggestionItem,
)


def format_existing_metrics_context(existing: list[dict[str, Any]]) -> str:
    """Render existing-metric summaries as Vietnamese prompt context."""
    lines = ["CÁC METRIC ĐANG TỒN TẠI TRONG HỆ THỐNG:"]
    for item in existing:
        status = item.get("status") or "draft"
        filter_text = _render_filters(item.get("filters"))
        lines.append(
            f'- [ID {item.get("id")} | {status}] "{item.get("name")}" '
            f"= {(item.get('function') or '').upper()}({item.get('expression')}) "
            f"trên `{item.get('base_entity')}`{filter_text}"
        )
    return "\n".join(lines)


def _filter_dict(item: Any) -> dict[str, Any]:
    """Coerce a filter entry (pydantic model or dict) into a plain dict."""
    if hasattr(item, "model_dump"):
        return dict(item.model_dump())
    return dict(item)


def _render_filters(filters: list[Any] | None) -> str:
    """Render filters as a compact comparison string (empty when none)."""
    if not filters:
        return ""
    parts = []
    for item in filters:
        data = _filter_dict(item)
        parts.append(f"{data.get('field')} {data.get('operator')} {data.get('value')}")
    return f", filter: {'; '.join(parts)}"


def _norm_name(name: str) -> str:
    """Casefold and collapse whitespace for name comparison."""
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def _norm_expression(expression: str) -> str:
    """Normalize a SQL expression via sqlglot for comparison."""
    try:
        return sqlglot.parse_one(expression).sql(dialect="postgres", normalize=True).casefold()
    except Exception:  # noqa: BLE001 — dedupe must never crash generation
        return re.sub(r"\s+", " ", expression).casefold()


def _norm_filters(filters: list[Any] | None) -> list[tuple[str, str, str]]:
    """Canonical sorted filter tuples (field, operator, stringified value)."""

    def to_tuple(item: Any) -> tuple[str, str, str]:
        data = _filter_dict(item)
        return (
            str(data.get("field", "")).casefold(),
            str(data.get("operator", "")).casefold(),
            str(data.get("value")).casefold(),
        )

    return sorted(to_tuple(item) for item in (filters or []))


def _same_logic(definition: MetricDefinition, existing: dict[str, Any]) -> bool:
    """True when function, expression, entity, and filters match after normalize."""
    metric = definition.metric
    if (metric.formula.function or "").upper() != (existing.get("function") or "").upper():
        return False
    if _norm_expression(metric.formula.expression or "") != _norm_expression(existing.get("expression") or ""):
        return False
    if (metric.base_entity or "").casefold() != (existing.get("base_entity") or "").casefold():
        return False
    return _norm_filters(metric.filters) == _norm_filters(existing.get("filters"))


def merge_dedupe(
    suggestions: list[MetricSuggestionItem],
    llm_duplicates: list[DuplicateMetricNotice],
    llm_conflicts: list[MetricConflictInfo],
    existing: list[dict[str, Any]] | None,
) -> tuple[list[MetricSuggestionItem], list[DuplicateMetricNotice]]:
    """Merge LLM dedupe judgments with the deterministic safety-net.

    - Drop LLM notices/conflicts that reference non-existent existing metrics.
    - Enrich valid notices with the DB metric preview (id, status, definition, YAML).
    - Suggestions named by a valid LLM duplicate notice are REMOVED — a metric
      the LLM judged a duplicate has no save path, even under a different name.
    - Safety-net only inspects suggestions whose normalized name exactly
      matches an existing metric the LLM did not already flag as conflict.
    - Exact name match + same logic → suggestion REMOVED + forced duplicate notice
      previewing the saved metric (the dropped proposal is never resurrected).
    - Exact name match + different logic → suggestion KEPT + forced conflict attached.
    - Never reverses an LLM duplicate verdict into a conflict.
    - Collapse notices so one existing metric yields at most one notice.
    """
    by_name = {_norm_name(item["name"]): item for item in (existing or [])}
    valid_notices = _valid_notices(llm_duplicates, by_name)
    notices = list(valid_notices)
    valid_conflicts = _valid_conflicts(llm_conflicts, by_name)
    flagged = {_norm_name(c.proposed_metric_name) for c in valid_conflicts}
    dup_flagged = {_norm_name(n.proposed_metric_name) for n in valid_notices if n.proposed_metric_name}
    kept: list[MetricSuggestionItem] = []
    for item in suggestions:
        result, notice = _process_suggestion(item, by_name, flagged, dup_flagged, valid_conflicts)
        if result is not None:
            kept.append(result)
        if notice is not None:
            notices.append(notice)
    return kept, _collapse_notices(notices)


def _process_suggestion(
    item: MetricSuggestionItem,
    by_name: dict[str, dict[str, Any]],
    flagged: set[str],
    dup_flagged: set[str],
    conflicts: list[MetricConflictInfo],
) -> tuple[MetricSuggestionItem | None, DuplicateMetricNotice | None]:
    """Apply LLM flags then the deterministic safety-net to one suggestion."""
    name_key = _norm_name(item.definition.metric.name)
    match = by_name.get(name_key)
    if name_key in flagged:
        return _attach_conflict(item, _find_conflict(conflicts, name_key, by_name)), None
    if name_key in dup_flagged:
        # LLM judged this proposal a duplicate — drop it; the notice above
        # already previews the existing metric it duplicates.
        return None, None
    if match is None:
        return item, None
    if _same_logic(item.definition, match):
        return None, _forced_duplicate(match)
    return _attach_conflict(item, _forced_conflict(item, match, by_name)), None


def _valid_notices(
    notices: list[DuplicateMetricNotice],
    by_name: dict[str, dict[str, Any]],
) -> list[DuplicateMetricNotice]:
    """Keep LLM notices referencing a real existing metric, enriched from DB truth."""
    valid: list[DuplicateMetricNotice] = []
    for notice in notices:
        match = by_name.get(_norm_name(notice.existing_metric_name))
        if match is not None:
            valid.append(_enrich_with_existing_preview(notice, match))
    return valid


def _valid_conflicts(
    conflicts: list[MetricConflictInfo],
    by_name: dict[str, dict[str, Any]],
) -> list[MetricConflictInfo]:
    """Keep only conflicts that reference an existing metric by name or id."""
    existing_ids = {item.get("id") for item in by_name.values()}
    valid: list[MetricConflictInfo] = []
    for conflict in conflicts:
        name_ok = _norm_name(conflict.existing_metric_name) in by_name
        id_ok = conflict.existing_metric_id is not None and conflict.existing_metric_id in existing_ids
        if name_ok or id_ok:
            valid.append(conflict)
    return valid


def _find_conflict(
    conflicts: list[MetricConflictInfo],
    name_key: str,
    by_name: dict[str, dict[str, Any]],
) -> MetricConflictInfo:
    """Locate the LLM conflict for a suggestion, repairing its suggested name."""
    conflict = next(c for c in conflicts if _norm_name(c.proposed_metric_name) == name_key)
    taken = {item["name"] for item in by_name.values()}
    taken_norm = {_norm_name(name) for name in taken}
    suggested = conflict.suggested_name
    if suggested and _norm_name(suggested) not in taken_norm:
        return conflict
    fixed = _ensure_unique_suggested_name(suggested or conflict.proposed_metric_name, taken)
    if fixed == suggested:
        return conflict
    return conflict.model_copy(update={"suggested_name": fixed})


def _attach_conflict(
    item: MetricSuggestionItem,
    conflict: MetricConflictInfo | None,
) -> MetricSuggestionItem:
    """Return a copy of the suggestion with the conflict attached."""
    return item.model_copy(update={"conflict": conflict})


def _forced_duplicate(existing: dict[str, Any]) -> DuplicateMetricNotice:
    """Build a status-aware duplicate notice with the saved-metric preview."""
    status = existing.get("status") or "draft"
    notice = DuplicateMetricNotice(
        existing_metric_id=existing.get("id"),
        existing_metric_name=existing["name"],
        existing_metric_status=status,
        user_message=_duplicate_message(existing["name"], status),
        similarity_reason="Trùng tên (bỏ qua hoa/thường, khoảng trắng) và trùng công thức sau chuẩn hóa.",
    )
    return _enrich_with_existing_preview(notice, existing)


def _duplicate_message(name: str, status: str) -> str:
    """Render the advisory message with the saved metric's approval status."""
    if status == "approved":
        return (
            f'Metric "{name}" đã tồn tại ở dạng chuẩn (đã duyệt) với cùng công thức '
            "— không cần tạo mới, hãy dùng metric có sẵn."
        )
    return (
        f'Metric "{name}" đã có trong hệ thống (trạng thái: {status}) '
        "với cùng tên và cùng công thức. Cân nhắc dùng metric có sẵn thay vì tạo mới."
    )


def _enrich_with_existing_preview(
    notice: DuplicateMetricNotice,
    match: dict[str, Any],
) -> DuplicateMetricNotice:
    """Attach DB-truth identity and a read-only definition preview to a notice."""
    update: dict[str, Any] = {}
    db_id = match.get("id")
    if db_id is not None:
        update["existing_metric_id"] = db_id
    if match.get("status"):
        update["existing_metric_status"] = match["status"]
    definition = _definition_from_summary(match)
    if definition is not None:
        update["existing_definition"] = definition
        update["existing_yaml"] = definition.to_yaml()
    return notice.model_copy(update=update)


def _definition_from_summary(summary: dict[str, Any]) -> MetricDefinition | None:
    """Rebuild a read-only preview definition from an existing-metric summary."""
    name = (summary.get("name") or "").strip()
    function = (summary.get("function") or "").strip().upper()
    expression = (summary.get("expression") or "").strip()
    entity = (summary.get("base_entity") or "").strip()
    if not (name and function and expression and entity):
        return None
    try:
        return MetricDefinition(
            metric={
                "name": name,
                "formula": {"function": function, "expression": expression},
                "base_entity": entity,
                "filters": summary.get("filters") or [],
                "status": summary.get("status") or None,
            }
        )
    except Exception:  # noqa: BLE001 — preview is optional, never break dedupe
        return None


def _notice_key(notice: DuplicateMetricNotice) -> int | str:
    """Stable per-existing-metric key (prefer DB id, fall back to normalized name)."""
    if notice.existing_metric_id is not None:
        return notice.existing_metric_id
    return _norm_name(notice.existing_metric_name)


def _notice_richer(candidate: DuplicateMetricNotice, current: DuplicateMetricNotice) -> bool:
    """True when candidate carries a preview the current notice lacks."""
    return candidate.existing_definition is not None and current.existing_definition is None


def _collapse_notices(notices: list[DuplicateMetricNotice]) -> list[DuplicateMetricNotice]:
    """Keep at most one notice per existing metric, preferring the richest payload."""
    best: dict[int | str, DuplicateMetricNotice] = {}
    for notice in notices:
        key = _notice_key(notice)
        current = best.get(key)
        if current is None or _notice_richer(notice, current):
            best[key] = notice
    return list(best.values())


def _forced_conflict(
    item: MetricSuggestionItem,
    existing: dict[str, Any],
    by_name: dict[str, dict[str, Any]],
) -> MetricConflictInfo:
    """Build a clarify request for a same-name different-logic suggestion."""
    status = existing.get("status") or "draft"
    name = item.definition.metric.name
    taken = {entry["name"] for entry in by_name.values()}
    return MetricConflictInfo(
        proposed_metric_name=name,
        existing_metric_id=existing.get("id"),
        existing_metric_name=existing["name"],
        existing_metric_status=status,
        suggested_name=_ensure_unique_suggested_name(name, taken),
        clarify_question=(f'Tên "{name}" đã được dùng cho một metric khác công thức. Bạn muốn đổi tên hay giữ nguyên?'),
    )


def _ensure_unique_suggested_name(base: str, taken: set[str]) -> str:
    """Return base unchanged when unique, else append a "(mới)" suffix chain."""
    taken_norm = {_norm_name(name) for name in taken}
    if _norm_name(base) not in taken_norm:
        return base
    candidate = f"{base} (mới)"
    counter = 2
    while _norm_name(candidate) in taken_norm:
        candidate = f"{base} (mới {counter})"
        counter += 1
    return candidate


def _summary_from_definition(
    definition: MetricDefinition,
    metric_id: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Project a MetricDefinition into the existing-metric summary dict shape."""
    metric = definition.metric
    return {
        "id": metric_id,
        "name": metric.name,
        "status": status,
        "function": metric.formula.function,
        "expression": metric.formula.expression,
        "base_entity": metric.base_entity,
        "filters": [f.model_dump() for f in (metric.filters or [])],
    }


# ---------------------------------------------------------------------------
# DB loaders (metadata store only — never the Target DB)
# ---------------------------------------------------------------------------


def _metric_summary(row: SemanticMetricModel) -> dict[str, Any]:
    """Project a SemanticMetricModel row into a comparison-friendly dict."""
    definition = row.definition or {}
    metric = definition.get("metric", definition)  # tolerate both shapes, prefer {"metric": ...}
    formula = metric.get("formula", {})
    return {
        "id": row.id,
        "name": row.name or metric.get("name", ""),
        "status": row.status,
        "function": formula.get("function", ""),
        "expression": formula.get("expression", ""),
        "base_entity": metric.get("base_entity", ""),
        "filters": metric.get("filters", []),
    }


async def list_existing_metric_summaries(
    db: AsyncSession,
    db_id: int,
) -> list[dict[str, Any]] | None:
    """Load saved metric summaries for dedupe; None when unavailable."""
    try:
        result = await db.execute(select(SemanticMetricModel).where(SemanticMetricModel.db_id == db_id))
        return [_metric_summary(row) for row in result.scalars().all()]
    except Exception:  # noqa: BLE001 — dedupe is advisory, never block generation
        return None


async def load_existing_for_dedupe(
    db: AsyncSession,
    db_id: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Resolve API-layer db_id string to (summaries, dedupe_performed)."""
    if not db_id.isdigit():  # non-numeric demo ids have no DB row to compare against
        return [], True
    summaries = await list_existing_metric_summaries(db, int(db_id))
    if summaries is None:
        return [], False
    return summaries, True
