"""Natural-language semantic query service for Chat Studio."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import LiveTargetDbModel, SemanticMetricModel
from src.models.schemas import (
    ChatClarificationOption,
    ChatClarificationPayload,
    ChatSemanticQueryResult,
    DimensionSelection,
    SemanticQueryFilter,
    SemanticQueryInterpretation,
    SemanticQuerySpec,
    SemanticTimeRange,
)
from src.services.database import decrypt_conn_url
from src.services.dimension_recommender import (
    get_dimensions_for_metric,
    get_filter_columns_for_metric,
)
from src.services.query_compiler import SemanticQueryCompiler
from src.services.query_execution import execute_compiled_query

logger = logging.getLogger(__name__)
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


async def build_parser_catalog(db: AsyncSession, db_id: int) -> dict[str, Any]:
    """Build a bounded, deduplicated catalog of approved metrics, dimensions, and filter columns."""
    stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.status == "approved",
        SemanticMetricModel.definition.is_not(None),
    )
    approved_metrics = list((await db.execute(stmt)).scalars().all())
    if not approved_metrics:
        return {"metrics": [], "dimensions": [], "filter_columns": []}

    metric_items = [_format_metric_item(m) for m in approved_metrics]
    dim_items, filter_items = await _collect_dims_and_filters(db, db_id, approved_metrics)
    return {
        "metrics": metric_items,
        "dimensions": dim_items,
        "filter_columns": filter_items,
    }


def _format_metric_item(metric: SemanticMetricModel) -> dict[str, Any]:
    """Format an approved metric for the parser catalog."""
    definition = metric.definition or {}
    metric_body = definition.get("metric", {})
    formula_obj = metric_body.get("formula", {})
    func = formula_obj.get("function", "")
    expr = formula_obj.get("expression", "")
    formula_str = f"{func}({expr})" if func and expr else expr or func or "N/A"
    return {
        "id": metric.id,
        "name": metric.name,
        "business_name": metric_body.get("business_name") or metric.name,
        "formula": formula_str,
        "base_entity": metric_body.get("base_entity") or metric.base_entity,
        "filters": metric_body.get("filters", []),
    }


async def _collect_dims_and_filters(
    db: AsyncSession, db_id: int, metrics: list[SemanticMetricModel]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect deduplicated dimensions and filter columns across approved metrics."""
    seen_dims: set[int] = set()
    dim_items: list[dict[str, Any]] = []
    seen_filters: set[int] = set()
    filter_items: list[dict[str, Any]] = []

    for metric in metrics:
        dims = await get_dimensions_for_metric(db, db_id, metric.id, limit=20)
        for d in dims:
            if d.column_id not in seen_dims:
                seen_dims.add(d.column_id)
                dim_items.append(d.model_dump())

        filters = await get_filter_columns_for_metric(db, db_id, metric.id)
        for f in filters:
            if f.column_id not in seen_filters:
                seen_filters.add(f.column_id)
                filter_items.append(f.model_dump())

    return dim_items, filter_items


def normalize_interpretation(
    interpretation: SemanticQueryInterpretation,
    catalog: dict[str, Any],
    now_vn: datetime | None = None,
) -> SemanticQueryInterpretation:
    """Validate IDs against catalog and merge time ranges into runtime filters."""
    if interpretation.status != "resolved" or interpretation.spec is None:
        return interpretation

    spec = interpretation.spec
    valid_metrics = {m["id"]: m for m in catalog.get("metrics", [])}
    if not set(spec.metric_ids).issubset(valid_metrics.keys()):
        return _invalid_selection_clarification("Chỉ số không tồn tại trong danh mục đã duyệt.")

    bases = {valid_metrics[m_id].get("base_entity") for m_id in spec.metric_ids}
    if len(bases) > 1:
        return _incompatible_bases_clarification(spec.metric_ids, valid_metrics)

    normalized_filters = _merge_time_ranges(spec.filters, interpretation.time_ranges)
    updated_spec = SemanticQuerySpec(
        metric_ids=spec.metric_ids,
        dimensions=spec.dimensions,
        filters=normalized_filters,
        limit=min(max(spec.limit, 1), 1000),
    )
    return SemanticQueryInterpretation(
        status="resolved",
        spec=updated_spec,
        time_ranges=interpretation.time_ranges,
        rationale=interpretation.rationale,
    )


def _merge_time_ranges(
    filters: list[SemanticQueryFilter], time_ranges: list[SemanticTimeRange]
) -> list[SemanticQueryFilter]:
    """Convert half-open [start_date, end_date) time ranges to gte and lt filters."""
    merged = list(filters)
    for tr in time_ranges:
        merged.append(SemanticQueryFilter(column_id=tr.column_id, operator="gte", value=tr.start_date))
        merged.append(SemanticQueryFilter(column_id=tr.column_id, operator="lt", value=tr.end_date))
    return merged


def _invalid_selection_clarification(message: str) -> SemanticQueryInterpretation:
    """Build a clarification when selection fails catalog verification."""
    return SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=message, options=[]),
    )


def _incompatible_bases_clarification(
    metric_ids: list[int], valid_metrics: dict[int, dict[str, Any]]
) -> SemanticQueryInterpretation:
    """Build clarification options when selected metrics belong to different base entities."""
    options = [
        ChatClarificationOption(
            id=f"opt_single_{m_id}",
            label=f"Xem {valid_metrics[m_id]['business_name']}",
            description=f"Truy vấn riêng cho bảng {valid_metrics[m_id]['base_entity']}",
            spec=SemanticQuerySpec(metric_ids=[m_id], dimensions=[], filters=[], limit=100),
        )
        for m_id in metric_ids[:3]
    ]
    prompt = (
        "Các chỉ số bạn chọn thuộc các bảng dữ liệu khác nhau nên không thể gom chung vào 1 bảng. "
        "Bạn vui lòng chọn một chỉ số để xem:"
    )
    return SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=prompt, options=options),
    )


async def execute_natural_language_query(
    db: AsyncSession,
    db_id: int,
    live_db: LiveTargetDbModel,
    spec: SemanticQuerySpec,
    catalog: dict[str, Any],
    time_ranges: list[SemanticTimeRange] | None = None,
) -> ChatSemanticQueryResult:
    """Compile and execute a validated query spec on the Live DB."""
    compiled = await SemanticQueryCompiler(db).compile(db_id, spec)
    conn_url = decrypt_conn_url(live_db.conn_url_enc)
    exec_result = await execute_compiled_query(
        conn_url=conn_url,
        dialect=live_db.dialect,
        compiled=compiled,
        timeout_seconds=15,
    )
    explanation = format_deterministic_explanation(
        metric_ids=spec.metric_ids,
        dimensions=spec.dimensions,
        filters=spec.filters,
        time_ranges=time_ranges or [],
        catalog=catalog,
    )
    return ChatSemanticQueryResult(
        spec=spec,
        columns=exec_result.columns,
        rows=exec_result.rows,
        row_count=exec_result.row_count,
        explanation=explanation,
        sql=compiled.sql,
        metadata=compiled.metadata,
    )


def format_deterministic_explanation(
    metric_ids: list[int],
    dimensions: list[DimensionSelection],
    filters: list[SemanticQueryFilter],
    time_ranges: list[SemanticTimeRange],
    catalog: dict[str, Any],
) -> str:
    """Format a deterministic Vietnamese explanation from metadata without LLM."""
    metric_map = {m["id"]: m for m in catalog.get("metrics", [])}
    dim_map = {d["column_id"]: d for d in catalog.get("dimensions", [])}
    filter_map = {f["column_id"]: f for f in catalog.get("filter_columns", [])}

    metric_parts = [
        f"**{metric_map[m_id]['business_name']}** (công thức `{metric_map[m_id]['formula']}`)"
        for m_id in metric_ids
        if m_id in metric_map
    ]
    base_text = "Số liệu được tính từ chỉ số " + ", ".join(metric_parts) if metric_parts else "Số liệu"

    dim_parts = _format_dimension_parts(dimensions, dim_map)
    dim_text = f", gom nhóm theo {', '.join(dim_parts)}" if dim_parts else ""

    filter_parts = _format_filter_parts(filters, time_ranges, filter_map, dim_map)
    filter_text = f", lọc theo {', '.join(filter_parts)}" if filter_parts else ""

    return f"{base_text}{dim_text}{filter_text}."


def _format_dimension_parts(dimensions: list[DimensionSelection], dim_map: dict[int, dict[str, Any]]) -> list[str]:
    """Format dimension labels with time grains."""
    grain_labels = {"day": "ngày", "week": "tuần", "month": "tháng", "quarter": "quý", "year": "năm"}
    parts = []
    for d in dimensions:
        info = dim_map.get(d.column_id)
        name = info.get("business_name") or info.get("column_name", str(d.column_id)) if info else str(d.column_id)
        if d.time_grain and d.time_grain in grain_labels:
            parts.append(f"**{name}** (theo {grain_labels[d.time_grain]})")
        else:
            parts.append(f"**{name}**")
    return parts


def _format_filter_parts(
    filters: list[SemanticQueryFilter],
    time_ranges: list[SemanticTimeRange],
    filter_map: dict[int, dict[str, Any]],
    dim_map: dict[int, dict[str, Any]],
) -> list[str]:
    """Format filter predicates and time ranges into readable explanation phrases."""
    parts = [f"**{tr.label}**" for tr in time_ranges if tr.label]
    cols = {**dim_map, **filter_map}
    for f in filters:
        if any(tr.column_id == f.column_id for tr in time_ranges):
            continue
        info = cols.get(f.column_id)
        col_name = info.get("business_name") or info.get("column_name", str(f.column_id)) if info else str(f.column_id)
        parts.append(f"**{col_name}** {f.operator} `{f.value}`")
    return parts
