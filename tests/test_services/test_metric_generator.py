"""Tests for definition-only metric generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.models.metric_definition import MetricDefinition
from src.models.schemas import (
    DuplicateMetricNotice,
    MetricConflictInfo,
    MetricSuggestions,
    MetricSuggestionsV2,
)
from src.services.metrics import generate_metrics_from_prompt, normalize_prompt


def _definition(name: str = "Doanh thu") -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "order_items",
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "Chưa trừ hoàn tiền",
            }
        }
    )


def _existing(metric_id: int = 12) -> dict[str, object]:
    return {
        "id": metric_id,
        "name": "Doanh thu",
        "status": "approved",
        "function": "SUM",
        "expression": "quantity * unit_price",
        "base_entity": "order_items",
        "filters": [],
    }


def test_normalize_prompt_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_prompt("   ")


@pytest.mark.asyncio
async def test_generate_definition_and_yaml_without_sql() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {
        "order_items": {
            "columns": [
                {"column_name": "quantity", "data_type": "INTEGER"},
                {"column_name": "unit_price", "data_type": "NUMERIC"},
            ]
        }
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, notices = await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)
    suggestion = suggestions[0]
    assert suggestion.definition.metric.name == "Doanh thu"
    assert "sql_template" not in suggestion.model_dump_json()
    preview = yaml.safe_load(suggestion.yaml_preview)
    assert preview["metric"]["formula"]["expression"] == "quantity * unit_price"
    assert "filters" not in preview["metric"]
    assert notices == []


@pytest.mark.asyncio
async def test_generation_rejects_unknown_expression_column() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {"order_items": {"columns": [{"column_name": "quantity"}]}}
    with patch("src.services.metrics.get_llm", return_value=llm):
        with pytest.raises(ValueError, match="valid metric definitions"):
            await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)


@pytest.mark.asyncio
async def test_generate_returns_llm_dedupe_flags() -> None:
    duplicate = DuplicateMetricNotice(
        existing_metric_id=12,
        existing_metric_name="Doanh thu",
        existing_metric_status="approved",
        user_message="Metric doanh thu đã tồn tại, không cần tạo mới.",
        similarity_reason="Trùng công thức SUM(quantity * unit_price)",
    )
    conflict = MetricConflictInfo(
        proposed_metric_name="Số đơn hoàn",
        existing_metric_id=12,
        existing_metric_name="Doanh thu",
        existing_metric_status="approved",
        suggested_name="Số đơn hoàn (mới)",
        clarify_question="Tên này chưa trùng metric nào, bạn có muốn dùng tên đề xuất?",
    )
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestionsV2(
        metrics=[_definition("Số đơn hoàn")],
        duplicates=[duplicate],
        conflicts=[conflict],
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {
        "order_items": {
            "columns": [
                {"column_name": "quantity", "data_type": "INTEGER"},
                {"column_name": "unit_price", "data_type": "NUMERIC"},
            ]
        }
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, notices = await generate_metrics_from_prompt(
            "Tính số đơn hoàn", schema_dict=schema, existing_metrics=[_existing()]
        )
    assert [notice.user_message for notice in notices] == [duplicate.user_message]
    assert suggestions[0].definition.metric.name == "Số đơn hoàn"
    assert suggestions[0].conflict is not None
    assert suggestions[0].conflict.suggested_name == "Số đơn hoàn (mới)"


@pytest.mark.asyncio
async def test_generate_safety_net_forces_duplicate() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestionsV2(metrics=[_definition("DOANH  THU")])
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    schema = {
        "order_items": {
            "columns": [
                {"column_name": "quantity", "data_type": "INTEGER"},
                {"column_name": "unit_price", "data_type": "NUMERIC"},
            ]
        }
    }
    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, notices = await generate_metrics_from_prompt(
            "Tính doanh thu", schema_dict=schema, existing_metrics=[_existing()]
        )
    assert suggestions == []
    assert len(notices) == 1
    assert notices[0].existing_metric_id == 12
    assert notices[0].existing_metric_name == "Doanh thu"


def test_extract_schema_summary_includes_column_description_and_allowed_values() -> None:
    schema = {
        "order_header": {
            "business_name": "Đơn hàng",
            "description": "Bảng chứa thông tin đơn hàng",
            "columns": [
                {
                    "column_name": "is_completed",
                    "business_name": "Đã hoàn thành",
                    "description": "Cờ hoàn thành (1: Thành công, 0: Chưa)",
                    "data_type": "VARCHAR(1)",
                    "allowed_values": ["0", "1"],
                },
                {
                    "column_name": "price",
                    "business_name": "Tổng tiền",
                    "description": "Tổng tiền sau thuế",
                    "data_type": "DECIMAL(15,3)",
                },
            ],
        }
    }
    from src.services.metrics import extract_schema_summary

    _, text = extract_schema_summary(schema)
    assert "Entity `order_header` (Đơn hàng): Bảng chứa thông tin đơn hàng" in text
    assert (
        "- `is_completed` (VARCHAR(1); Đã hoàn thành — Cờ hoàn thành (1: Thành công, 0: Chưa); values: ['0', '1'])"
        in text
    )
    assert "- `price` (DECIMAL(15,3); Tổng tiền — Tổng tiền sau thuế)" in text
