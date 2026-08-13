"""Node for resolving Guided Wizard selections into a SemanticQuerySpec."""

from __future__ import annotations

from typing import Any

from src.agents.query_clarifier.state import QueryClarifierState, WizardStepOutput
from src.models.schemas import DimensionSelection, SemanticQuerySpec, TimeGrain


def _parse_dimension_option(option_id: str | None) -> tuple[int | None, TimeGrain | None]:
    """Parse dimension selection option string.

    Examples:
        'dim:none' -> (None, None)
        'dim:45' -> (45, None)
        'dim:45:month' -> (45, 'month')
    """
    if not option_id or option_id == "dim:none":
        return None, None
    parts = option_id.split(":")
    if len(parts) >= 2 and parts[0] == "dim":
        try:
            col_id = int(parts[1])
            time_grain: TimeGrain | None = parts[2] if len(parts) >= 3 else None
            return col_id, time_grain
        except ValueError:
            pass
    return None, None


async def resolve_node(state: QueryClarifierState) -> dict[str, Any]:
    """Resolve metric and dimension selections into canonical SemanticQuerySpec."""
    metric_ids = state.get("selected_metric_ids", [])
    if not metric_ids:
        return {
            "error_message": "Chưa chọn chỉ số nghiệp vụ nào.",
        }

    selected_option = state.get("selected_option_id")
    col_id, time_grain = _parse_dimension_option(selected_option)

    dimensions: list[DimensionSelection] = []
    if col_id is not None:
        dimensions.append(DimensionSelection(column_id=col_id, time_grain=time_grain))

    spec = SemanticQuerySpec(
        metric_ids=metric_ids,
        dimensions=dimensions,
        filters=[],
        limit=100,
    )

    wizard_step = WizardStepOutput(
        step=3,
        title="Hoàn Tất - Xem Trước SQL & Chỉ Số",
        question="Đã tổng hợp thành công cấu hình truy vấn. Bạn có thể áp dụng ngay vào Explorer.",
        options=[],
        is_completed=True,
    )

    return {
        "current_step": 3,
        "resolved_spec": spec,
        "wizard_step": wizard_step,
        "error_message": None,
    }
