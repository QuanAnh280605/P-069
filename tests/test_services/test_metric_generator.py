"""Tests for definition-only metric generation."""

import asyncio
import json
from types import SimpleNamespace
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
from src.services.metrics import (
    MetricGenerationInvalidError,
    MetricGenerationTimeoutError,
    MetricGenerationUnavailableError,
    _metric_bind_kwargs,
    generate_definitions_v2,
    generate_metrics_from_prompt,
    normalize_prompt,
    validate_metric_definitions,
)


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


def _raw_structured_llm(payload: object) -> tuple[MagicMock, AsyncMock]:
    """Build a bound LLM whose structured parser exposes raw JSON."""
    structured = AsyncMock()
    structured.ainvoke.return_value = {
        "raw": SimpleNamespace(content=json.dumps(payload)),
        "parsed": None,
        "parsing_error": ValueError("invalid structured payload"),
    }
    bounded = MagicMock()
    bounded.with_structured_output.return_value = structured
    llm = MagicMock()
    llm.bind.return_value = bounded
    return llm, structured


@pytest.mark.asyncio
async def test_generation_repairs_null_filter_without_retry() -> None:
    """A fixable null filter must be normalized from the first response."""
    payload = _definition().model_dump(mode="json")
    payload["metric"]["filters"] = [{"field": "status", "operator": "is_null", "value": True}]
    llm, structured = _raw_structured_llm({"metrics": [payload]})
    settings = SimpleNamespace(llm_metric_timeout_seconds=45.0, llm_metric_max_output_tokens=1200)

    with (
        patch("src.services.metrics.get_llm", return_value=llm),
        patch("src.services.metrics.get_settings", return_value=settings),
    ):
        definitions, duplicates, conflicts = await generate_definitions_v2([], False)

    assert definitions[0].metric.filters[0].value is None
    assert duplicates == []
    assert conflicts == []
    structured.ainvoke.assert_awaited_once()
    llm.bind.assert_called_once()


@pytest.mark.asyncio
async def test_generation_timeout_does_not_retry() -> None:
    """Metric generation uses one bounded attempt and raises a typed timeout."""
    llm, structured = _raw_structured_llm({})
    structured.ainvoke.side_effect = asyncio.TimeoutError
    settings = SimpleNamespace(llm_metric_timeout_seconds=45.0, llm_metric_max_output_tokens=1200)

    with (
        patch("src.services.metrics.get_llm", return_value=llm),
        patch("src.services.metrics.get_settings", return_value=settings),
        pytest.raises(MetricGenerationTimeoutError),
    ):
        await generate_definitions_v2([], False)

    structured.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_generation_rejects_unrepairable_raw_output_without_retry() -> None:
    """Unsafe or malformed model output fails without a second completion."""
    llm, structured = _raw_structured_llm({"metrics": [{"metric": {"name": "Broken"}}]})
    settings = SimpleNamespace(llm_metric_timeout_seconds=45.0, llm_metric_max_output_tokens=1200)

    with (
        patch("src.services.metrics.get_llm", return_value=llm),
        patch("src.services.metrics.get_settings", return_value=settings),
        pytest.raises(MetricGenerationInvalidError),
    ):
        await generate_definitions_v2([], False)

    structured.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_generation_wraps_provider_failure_without_retry() -> None:
    """Provider failures become a typed upstream error after one request."""
    llm, structured = _raw_structured_llm({})
    structured.ainvoke.side_effect = RuntimeError("provider unavailable")
    settings = SimpleNamespace(llm_metric_timeout_seconds=45.0, llm_metric_max_output_tokens=1200)

    with (
        patch("src.services.metrics.get_llm", return_value=llm),
        patch("src.services.metrics.get_settings", return_value=settings),
        pytest.raises(MetricGenerationUnavailableError),
    ):
        await generate_definitions_v2([], False)

    structured.ainvoke.assert_awaited_once()


def test_openrouter_metric_call_disables_reasoning_and_caps_output() -> None:
    """OpenRouter Metric calls disable reasoning and use its native output cap."""
    llm = SimpleNamespace(openai_api_base="https://openrouter.ai/api/v1")

    kwargs = _metric_bind_kwargs(llm, 1200)

    assert kwargs["max_tokens"] == 1200
    assert kwargs["extra_body"] == {
        "provider": {"sort": "throughput", "require_parameters": True},
        "reasoning": {"enabled": False},
    }


def test_normalize_prompt_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_prompt("   ")


def test_validation_maps_key_dimensions_for_direct_generation() -> None:
    """The direct generate endpoint maps technical keys to display columns."""
    definition = _definition()
    definition.metric.dimensions = ["store_id"]
    schema = {
        "tables": [
            {
                "table_name": "order_items",
                "columns": [
                    {"column_name": "quantity", "data_type": "INTEGER"},
                    {"column_name": "unit_price", "data_type": "NUMERIC"},
                    {"column_name": "store_id", "data_type": "INTEGER", "is_foreign_key": True},
                ],
            },
            {
                "table_name": "stores",
                "columns": [{"column_name": "store_name", "data_type": "VARCHAR", "business_name": "Tên cửa hàng"}],
            },
        ]
    }

    definitions = validate_metric_definitions([definition], "postgres", schema)

    assert definitions[0].metric.dimensions == ["stores.store_name"]


@pytest.mark.asyncio
async def test_generate_definition_and_yaml_without_sql() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.bind.return_value = llm
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
async def test_generation_returns_one_definition_for_one_request() -> None:
    """The custom generation endpoint must match the one-metric chat contract."""
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition(), _definition(), _definition()])
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.with_structured_output.return_value = structured
    schema = {"order_items": {"columns": [{"column_name": "quantity"}, {"column_name": "unit_price"}]}}

    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, duplicates = await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_generation_keeps_target_from_list_shaped_schema() -> None:
    """Explicit targets must not erase the compact list-shaped schema."""
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.with_structured_output.return_value = structured
    schema = {
        "tables": [
            {"table_name": "order_items", "columns": [{"column_name": "quantity"}, {"column_name": "unit_price"}]}
        ]
    }

    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, _ = await generate_metrics_from_prompt(
            "Tính doanh thu", schema_context=schema, target_tables=["order_items"]
        )

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_generation_rejects_unknown_expression_column() -> None:
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(metrics=[_definition()])
    llm = MagicMock()
    llm.bind.return_value = llm
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
    llm.bind.return_value = llm
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
    llm.bind.return_value = llm
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


@pytest.mark.asyncio
async def test_regression_on_demand_generation_caps_single() -> None:
    """Regression: the on-demand /metrics/generate path must keep returning exactly one suggestion."""
    structured = AsyncMock()
    structured.ainvoke.return_value = MetricSuggestions(
        metrics=[_definition(), _definition("Số lượng"), _definition("Giá trị")]
    )
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.with_structured_output.return_value = structured
    schema = {"order_items": {"columns": [{"column_name": "quantity"}, {"column_name": "unit_price"}]}}
    with patch("src.services.metrics.get_llm", return_value=llm):
        suggestions, _ = await generate_metrics_from_prompt("Tính doanh thu", schema_dict=schema)
    assert len(suggestions) == 1


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
