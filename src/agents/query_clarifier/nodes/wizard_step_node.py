"""Node for building Step 2 of Guided Wizard (Smart Dimension Chips)."""

from __future__ import annotations

from typing import Any

from src.agents.query_clarifier.state import QueryClarifierState, QueryClarifyOption, WizardStepOutput


def _extract_metric_id(selected_option_id: str | None, current_selected: list[int]) -> int | None:
    """Extract numeric metric ID from option string or current state."""
    if selected_option_id and selected_option_id.startswith("metric:"):
        try:
            return int(selected_option_id.split(":")[1])
        except (ValueError, IndexError):
            pass
    if current_selected:
        return current_selected[0]
    return None


def _find_smart_dimensions(
    metric_id: int,
    catalog: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> list[QueryClarifyOption]:
    """Find reachable smart dimension options prioritizing base table columns."""
    options: list[QueryClarifyOption] = [
        QueryClarifyOption(
            id="dim:none",
            label="Tổng hợp toàn bộ (Không chia theo chiều nào)",
            description="Tính tổng giá trị chỉ số trên toàn bộ dữ liệu",
        )
    ]

    tables = catalog.get("tables", [])
    if not tables:
        return options

    # Find base entity for this metric
    base_entity: str | None = None
    for m in metrics:
        if m.get("metric_id") == metric_id:
            base_entity = m.get("base_entity")
            break

    # Sort tables so the metric's base table comes first
    sorted_tables = sorted(
        tables,
        key=lambda t: 0 if base_entity and t.get("table_name", "").lower() == base_entity.lower() else 1,
    )

    # Collect time dimensions and key business columns
    time_options: list[QueryClarifyOption] = []
    category_options: list[QueryClarifyOption] = []

    for table in sorted_tables:
        t_name = table.get("business_name") or table.get("table_name", "")
        for col in table.get("columns", []):
            col_id = col.get("column_id")
            c_name = col.get("business_name") or col.get("column_name", "")
            is_time = col.get("is_time_dimension", False) or "date" in col.get("data_type", "").lower()

            if not col_id:
                continue

            if is_time and len(time_options) < 2:
                time_options.append(
                    QueryClarifyOption(
                        id=f"dim:{col_id}:month",
                        label=f"Theo Tháng ({c_name} - {t_name})",
                        description=f"Gom nhóm và tổng hợp dữ liệu theo từng tháng qua cột {c_name}",
                    )
                )
            elif not is_time and len(category_options) < 4:
                category_options.append(
                    QueryClarifyOption(
                        id=f"dim:{col_id}",
                        label=f"Theo {c_name} ({t_name})",
                        description=f"Gom nhóm chỉ số theo {c_name}",
                    )
                )

    options.extend(time_options)
    options.extend(category_options)
    return options


async def wizard_step_node(state: QueryClarifierState) -> dict[str, Any]:
    """Build Step 2 with smart dimension chips based on selected metric."""
    selected_option = state.get("selected_option_id")
    selected_metric_ids = state.get("selected_metric_ids", [])
    catalog = state.get("catalog_context", {})
    metrics = state.get("approved_metrics", [])

    metric_id = _extract_metric_id(selected_option, selected_metric_ids)
    if not metric_id:
        return {
            "error_message": "Vui lòng chọn một chỉ số nghiệp vụ hợp lệ.",
        }

    updated_metrics = [metric_id]
    smart_options = _find_smart_dimensions(metric_id, catalog, metrics)

    wizard_step = WizardStepOutput(
        step=2,
        title="Bước 2: Chọn Chiều Phân Tích",
        question="Bạn muốn tổng hợp chỉ số theo chiều phân tích nào?",
        options=smart_options,
        is_completed=False,
    )

    return {
        "current_step": 2,
        "selected_metric_ids": updated_metrics,
        "wizard_step": wizard_step,
        "error_message": None,
    }
