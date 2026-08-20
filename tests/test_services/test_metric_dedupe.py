"""Unit tests for the deterministic metric dedupe safety-net."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import SemanticDatabaseModel, SemanticMetricModel
from src.models.metric_definition import MetricDefinition
from src.models.schemas import DuplicateMetricNotice, MetricConflictInfo, MetricSuggestionItem
from src.services.metric_dedupe import (
    _ensure_unique_suggested_name,
    _metric_summary,
    _norm_expression,
    _norm_name,
    _same_logic,
    format_existing_metrics_context,
    list_existing_metric_summaries,
    load_existing_for_dedupe,
    merge_dedupe,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _existing(
    name: str = "Doanh thu",
    expr: str = "quantity * unit_price",
    status: str = "approved",
    fn: str = "SUM",
    entity: str = "order_items",
    mid: int | None = 12,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an existing-metric summary dict."""
    return {
        "id": mid,
        "name": name,
        "status": status,
        "function": fn,
        "expression": expr,
        "base_entity": entity,
        "filters": filters or [],
    }


def _definition(
    name: str = "Doanh thu",
    expr: str = "quantity * unit_price",
    fn: str = "SUM",
    entity: str = "order_items",
    filters: list[dict[str, Any]] | None = None,
) -> MetricDefinition:
    """Build a MetricDefinition for tests."""
    payload: dict[str, Any] = {
        "metric": {
            "name": name,
            "formula": {"function": fn, "expression": expr},
            "base_entity": entity,
            "status": "pending_approval",
            "confidence": "high",
        }
    }
    if filters:
        payload["metric"]["filters"] = filters
    return MetricDefinition.model_validate(payload)


def _suggestion(name: str = "Doanh thu", **kw: Any) -> MetricSuggestionItem:
    """Build a suggestion item with an empty YAML preview."""
    return MetricSuggestionItem(definition=_definition(name, **kw), yaml_preview="")


# ---------------------------------------------------------------------------
# Prompt context + normalization primitives
# ---------------------------------------------------------------------------


def test_format_context_renders_all_fields() -> None:
    ext = _existing(filters=[{"field": "is_completed", "operator": "=", "value": 1}])
    text = format_existing_metrics_context([ext])
    assert "CÁC METRIC ĐANG TỒN TẠI" in text
    assert "[ID 12 | approved]" in text
    assert '"Doanh thu"' in text
    assert "SUM(quantity * unit_price)" in text
    assert "`order_items`" in text
    assert "filter: is_completed = 1" in text


def test_norm_name_case_and_whitespace() -> None:
    assert _norm_name("DOANH  THU") == _norm_name("doanh thu")
    assert _norm_name("doanh thu") != _norm_name("doanhthu")


def test_norm_expression_sqlglot_normalize() -> None:
    assert _norm_expression("SUM( x )") == _norm_expression("sum(x)")


def test_same_logic_ignores_case_and_spacing() -> None:
    definition = _definition(fn="sum", expr="quantity  *  unit_price", entity="ORDER_ITEMS")
    assert _same_logic(definition, _existing(fn="SUM")) is True


def test_same_logic_detects_different_formula() -> None:
    assert _same_logic(_definition(expr="quantity + unit_price"), _existing()) is False


# ---------------------------------------------------------------------------
# merge_dedupe
# ---------------------------------------------------------------------------


def test_merge_pass_through_when_no_match() -> None:
    suggestion = _suggestion("Số đơn hàng")
    kept, notices = merge_dedupe([suggestion], [], [], [_existing()])
    assert len(kept) == 1
    assert kept[0].definition.metric.name == "Số đơn hàng"
    assert kept[0].conflict is None
    assert notices == []


def test_merge_drops_hallucinated_duplicate_notice() -> None:
    notice = DuplicateMetricNotice(existing_metric_name="Không Tồn Tại", user_message="Đã tồn tại")
    _, notices = merge_dedupe([_suggestion("Số đơn hàng")], [notice], [], [_existing()])
    assert notices == []


def test_merge_drops_hallucinated_conflict() -> None:
    conflict = MetricConflictInfo(
        proposed_metric_name="Số đơn hàng",
        existing_metric_name="Không Tồn Tại",
        suggested_name="Số đơn hàng (mới)",
    )
    kept, _ = merge_dedupe([_suggestion("Số đơn hàng")], [], [conflict], [_existing()])
    assert len(kept) == 1
    assert kept[0].conflict is None


def test_safety_net_forces_duplicate_on_exact_name() -> None:
    kept, notices = merge_dedupe([_suggestion("DOANH  THU")], [], [], [_existing()])
    assert kept == []
    assert len(notices) == 1
    assert notices[0].existing_metric_id == 12
    assert "đã duyệt" in notices[0].user_message


def test_safety_net_forces_conflict_on_same_name_diff_formula() -> None:
    suggestion = _suggestion("Doanh thu", expr="quantity + unit_price")
    kept, notices = merge_dedupe([suggestion], [], [], [_existing()])
    assert len(kept) == 1
    assert kept[0].conflict is not None
    assert kept[0].conflict.suggested_name == "Doanh thu (mới)"
    assert kept[0].conflict.existing_metric_id == 12
    assert notices == []


def test_llm_duplicate_verdict_not_reversed() -> None:
    notice = DuplicateMetricNotice(
        existing_metric_id=12,
        existing_metric_name="Doanh thu",
        user_message="Trùng metric đã có",
    )
    kept, notices = merge_dedupe([], [notice], [], [_existing()])
    assert kept == []
    assert len(notices) == 1
    assert notices[0].existing_metric_name == notice.existing_metric_name
    assert notices[0].user_message == notice.user_message
    assert notices[0].existing_definition is not None  # enriched, verdict intact


# ---------------------------------------------------------------------------
# Notice collapse (one existing metric → one notice) + preview enrichment
# ---------------------------------------------------------------------------


def test_merge_collapses_llm_and_forced_notice_for_same_existing() -> None:
    """LLM semantic notice + safety-net forced notice must yield ONE rich notice."""
    llm_notice = DuplicateMetricNotice(
        existing_metric_name="Doanh thu",
        user_message="Trùng metric đã có",
        similarity_reason="Cùng đo tổng doanh thu",
    )
    kept, notices = merge_dedupe([_suggestion("DOANH  THU")], [llm_notice], [], [_existing()])
    assert kept == []
    assert len(notices) == 1
    notice = notices[0]
    assert notice.existing_metric_id == 12
    assert notice.existing_definition is not None
    assert notice.existing_definition.metric.formula.function == "SUM"
    assert notice.existing_definition.metric.formula.expression == "quantity * unit_price"
    assert notice.existing_definition.metric.base_entity == "order_items"
    assert "metric:" in notice.existing_yaml
    assert not hasattr(notice, "proposed")  # save path removed — duplicates are never saveable


def test_merge_collapses_two_llm_notices_for_same_existing() -> None:
    first = DuplicateMetricNotice(existing_metric_name="Doanh thu", user_message="Bản 1", similarity_reason="Lý do 1")
    second = DuplicateMetricNotice(existing_metric_name="doanh thu", user_message="Bản 2")
    _, notices = merge_dedupe([], [first, second], [], [_existing()])
    assert len(notices) == 1
    assert notices[0].user_message == "Bản 1"


def test_llm_notice_enriched_with_existing_preview() -> None:
    notice = DuplicateMetricNotice(existing_metric_name="Doanh thu", user_message="Trùng metric đã có")
    _, notices = merge_dedupe([], [notice], [], [_existing()])
    assert len(notices) == 1
    enriched = notices[0]
    assert enriched.existing_metric_id == 12
    assert enriched.existing_metric_status == "approved"
    assert enriched.existing_definition is not None
    assert enriched.existing_yaml
    assert not hasattr(enriched, "proposed")


def test_llm_notice_id_repaired_from_db() -> None:
    notice = DuplicateMetricNotice(existing_metric_id=999, existing_metric_name="Doanh thu", user_message="x")
    _, notices = merge_dedupe([], [notice], [], [_existing()])
    assert notices[0].existing_metric_id == 12


def test_llm_flagged_duplicate_suggestion_is_dropped() -> None:
    """A suggestion the LLM judged duplicate is dropped — no save path for duplicates."""
    notice = DuplicateMetricNotice(
        existing_metric_name="Doanh thu",
        user_message="Trùng metric đã có",
        similarity_reason="Cùng đo tổng doanh thu",
        proposed_metric_name="Tổng doanh thu",
    )
    kept, notices = merge_dedupe([_suggestion("Tổng doanh thu")], [notice], [], [_existing()])
    assert kept == []
    assert len(notices) == 1
    assert notices[0].existing_metric_name == "Doanh thu"
    assert notices[0].existing_definition is not None


def test_llm_duplicate_with_different_formula_upgrades_to_conflict() -> None:
    """LLM judged duplicate but formulas provably differ → Clarify conflict, notice dropped."""
    notice = DuplicateMetricNotice(
        existing_metric_name="Doanh thu",
        user_message="Trùng metric đã có",
        similarity_reason="Ý nghĩa khác với công thức",
        proposed_metric_name="Tổng doanh thu",
    )
    suggestion = _suggestion("Tổng doanh thu", expr="unit_price * (1 - discount_rate)")
    kept, notices = merge_dedupe([suggestion], [notice], [], [_existing()])
    assert len(kept) == 1
    conflict = kept[0].conflict
    assert conflict is not None
    assert conflict.existing_metric_name == "Doanh thu"
    assert conflict.existing_metric_id == 12
    assert conflict.suggested_name != "Tổng doanh thu"  # rename must actually change the name
    assert conflict.clarify_question  # AI proactively asks the user
    assert notices == []  # the superseded duplicate notice is gone


def test_exact_name_diff_formula_wins_over_llm_duplicate_verdict() -> None:
    """Exact-name + different logic always becomes a conflict, even when LLM said duplicate."""
    notice = DuplicateMetricNotice(
        existing_metric_name="Doanh thu",
        user_message="Trùng metric đã có",
        proposed_metric_name="Doanh thu",
    )
    suggestion = _suggestion("Doanh thu", expr="quantity + unit_price")
    kept, notices = merge_dedupe([suggestion], [notice], [], [_existing()])
    assert len(kept) == 1
    assert kept[0].conflict is not None
    assert kept[0].conflict.suggested_name == "Doanh thu (mới)"
    assert notices == []


def test_flagged_drop_requires_valid_notice() -> None:
    """A flag referencing a non-existent metric drops nothing (no silent loss)."""
    notice = DuplicateMetricNotice(
        existing_metric_name="Không Tồn Tại",
        user_message="Trùng metric đã có",
        proposed_metric_name="Tổng doanh thu",
    )
    kept, notices = merge_dedupe([_suggestion("Tổng doanh thu")], [notice], [], [_existing()])
    assert len(kept) == 1
    assert notices == []


def test_notice_without_proposed_name_keeps_suggestion() -> None:
    """Without a join key the suggestion survives (backwards compatibility)."""
    notice = DuplicateMetricNotice(existing_metric_name="Doanh thu", user_message="Trùng metric đã có")
    kept, notices = merge_dedupe([_suggestion("Tổng doanh thu")], [notice], [], [_existing()])
    assert len(kept) == 1
    assert len(notices) == 1


def test_forced_notice_carries_preview_not_proposal() -> None:
    """Safety-net notices preview the saved metric and never resurrect the dropped one."""
    _, notices = merge_dedupe([_suggestion("DOANH  THU")], [], [], [_existing()])
    assert len(notices) == 1
    notice = notices[0]
    assert notice.existing_definition is not None
    assert notice.existing_definition.metric.name == "Doanh thu"
    assert not hasattr(notice, "proposed")


def test_ensure_unique_suggested_name_suffix_chain() -> None:
    taken = {"Doanh thu", "Doanh thu (mới)"}
    assert _ensure_unique_suggested_name("Doanh thu", taken) == "Doanh thu (mới 2)"


def test_forced_duplicate_message_status_aware() -> None:
    _, draft_notices = merge_dedupe([_suggestion("DOANH  THU")], [], [], [_existing(status="draft")])
    _, approved_notices = merge_dedupe([_suggestion("DOANH  THU")], [], [], [_existing(status="approved")])
    assert "trạng thái: draft" in draft_notices[0].user_message
    assert draft_notices[0].user_message != approved_notices[0].user_message


# ---------------------------------------------------------------------------
# DB loaders (metadata store only — never the Target DB)
# ---------------------------------------------------------------------------


async def _seed_db(session: AsyncSession, db_id: int) -> None:
    """Insert a parent SemanticDatabaseModel row to satisfy the metrics FK."""
    session.add(
        SemanticDatabaseModel(
            id=db_id,
            created_by=1,
            display_name=f"DB {db_id}",
            db_type="postgresql",
            conn_url_enc="encrypted:xxx",
            status="approved",
        )
    )
    await session.flush()


async def _seed_metric(
    session: AsyncSession,
    db_id: int,
    name: str,
    expr: str,
    status: str = "approved",
) -> SemanticMetricModel:
    """Insert a minimal valid SemanticMetricModel row with a definition payload."""
    row = SemanticMetricModel(
        db_id=db_id,
        created_by=1,
        name=name,
        description=f"Chỉ số {name}",
        sql_template="SELECT 1",
        source="manual",
        status=status,
        formula=expr,
        aggregation_type="SUM",
        definition={
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": expr},
                "base_entity": "order_items",
                "filters": [],
            }
        },
    )
    session.add(row)
    await session.flush()
    return row


def test_metric_summary_projects_row() -> None:
    row = SemanticMetricModel(
        id=7,
        name="Doanh thu",
        status="approved",
        definition={
            "metric": {
                "name": "bỏ qua tên trong definition",
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "order_items",
                "filters": [],
            }
        },
    )
    summary = _metric_summary(row)
    assert set(summary) == {"id", "name", "status", "function", "expression", "base_entity", "filters"}
    assert summary["id"] == 7
    assert summary["name"] == "Doanh thu"
    assert summary["status"] == "approved"
    assert summary["function"] == "SUM"
    assert summary["expression"] == "quantity * unit_price"
    assert summary["base_entity"] == "order_items"
    assert summary["filters"] == []


@pytest.mark.asyncio
async def test_list_existing_filters_by_db_id(async_session: AsyncSession) -> None:
    await _seed_db(async_session, 101)
    await _seed_db(async_session, 202)
    await _seed_metric(async_session, 101, "Doanh thu", "quantity * unit_price")
    await _seed_metric(async_session, 101, "Số đơn hàng", "COUNT(order_id)")
    await _seed_metric(async_session, 202, "Khác DB", "COUNT(*)")

    summaries = await list_existing_metric_summaries(async_session, 101)

    assert summaries is not None
    assert len(summaries) == 2
    assert {item["name"] for item in summaries} == {"Doanh thu", "Số đơn hàng"}


@pytest.mark.asyncio
async def test_list_existing_returns_none_on_error(async_session: AsyncSession) -> None:
    async_session.execute = AsyncMock(side_effect=Exception("metadata store down"))

    assert await list_existing_metric_summaries(async_session, 101) is None


@pytest.mark.asyncio
async def test_load_existing_demo_non_numeric(async_session: AsyncSession) -> None:
    spy = AsyncMock(wraps=async_session.execute)
    async_session.execute = spy

    assert await load_existing_for_dedupe(async_session, "demo-retail") == ([], True)
    assert spy.await_count == 0


@pytest.mark.asyncio
async def test_load_existing_low_numeric_id_loads(async_session: AsyncSession) -> None:
    await _seed_db(async_session, 42)
    await _seed_metric(async_session, 42, "Doanh thu", "quantity * unit_price")

    summaries, performed = await load_existing_for_dedupe(async_session, "42")

    assert performed is True
    assert [item["name"] for item in summaries] == ["Doanh thu"]


@pytest.mark.asyncio
async def test_load_existing_unavailable_signal(async_session: AsyncSession) -> None:
    await _seed_db(async_session, 101)
    await _seed_metric(async_session, 101, "Doanh thu", "quantity * unit_price")
    await _seed_metric(async_session, 101, "Số đơn hàng", "COUNT(order_id)")

    summaries, performed = await load_existing_for_dedupe(async_session, "101")

    assert performed is True
    assert len(summaries) == 2

    async_session.execute = AsyncMock(side_effect=Exception("metadata store down"))
    assert await load_existing_for_dedupe(async_session, "101") == ([], False)
